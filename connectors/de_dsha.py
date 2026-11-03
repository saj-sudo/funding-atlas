"""Delaware State Housing Authority (Housing Delaware) connector: the "Build & Develop" program pages.

Source: https://www.destatehousing.com (WordPress, no robots restrictions). Six hand-listed pages in two shapes: a
one-program page (a header card with status lines and "Who applies") or a sections page (one program per
`h2.hd-sec-h2`, each with its paragraphs, eligibility panel and Important dates list). The header meta is the status
of record where its key names the program. Contact cards are never read. See docs/connectors/de_dsha.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup, Comment, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for
from pipeline.models import ApplicantTag, Program, RawRecord

CONNECTOR = "de_dsha"
BASE = "https://www.destatehousing.com"
# slug -> "sections" (one program per h2) or "page" (one program)
PAGES: dict[str, str] = {
    "community-benefit": "sections", "arpa-programs": "sections", "supportive-housing": "sections",
    "ddd-program": "page", "homeownership-production": "page", "lihtc": "page",
}
SKIP_SECTIONS = re.compile(r"^(?:on this page|questions|archived)", re.I)
SKIP_META = re.compile(r"^questions", re.I)
WHO_APPLIES = "who applies"
AGENCY = "Delaware State Housing Authority"
AGENCY_CODE = "DE-DSHA"
JURISDICTION = "DE"
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

ELIGIBILITY_HEADING_RE = re.compile(r"eligibility|eligible applicants|who applies|applicant qualifications", re.I)   # not "Eligible activities"
APPLICANT_RE = re.compile(r"\b(?:eligible to apply|may apply|who applies|apply to housing delaware|are eligible)\b", re.I)
STATUS_RE = re.compile(r"\b(?:closed|not currently accepting|rolling|applications? open|current round|accepting applications|due|deadline|round opens|opens)\b", re.I)
CLOSED_RE = re.compile(r"\b(?:closed|not currently accepting)\b", re.I)
OPEN_RE = re.compile(r"\b(?:rolling|applications? open|current round|accepting applications|now open|round opens|now accepting)\b", re.I)
RANGE_RE = re.compile(r"\b(?:from|open)\b.*\b(?:through|to|until)\b", re.I)
DUE_RE = re.compile(r"\b(?:due|deadline|through|until|by|closed|closes)\b", re.I)
OPENS_RE = re.compile(r"\bopens?\b", re.I)
FULL_DATE_RE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b")
FEDERAL_RE = re.compile(r"\bfederal (?:grant|funding|funds|program)\b|\bHUD\b|\bU\.S\. Department of Housing\b", re.I)
REBATE_RE = re.compile(r"\brebate", re.I)


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


# ---------- parsing (no I/O) ----------

def _text(el: Tag) -> str:
    return clean(el.get_text(" "))


def _block_lines(el: Tag) -> list[tuple[str, str]]:
    """(kind, text) for one element: a heading, a paragraph, each list item, or a panel's heading and paragraphs."""
    if el.name in ("h2", "h3", "h4"):
        return [("heading", _text(el))]
    if el.name == "p":
        return [("p", _text(el))] if _text(el) else []
    if el.name in ("ul", "ol"):
        return [("li", clean(li.get_text(" "))) for li in el.find_all("li") if clean(li.get_text(" "))]
    out: list[tuple[str, str]] = []
    for child in el.find_all(["h2", "h3", "h4", "p", "li"]):
        if child.name == "li" and child.find_parent("li") is not None:
            continue
        kind = "heading" if child.name.startswith("h") else child.name
        text = _text(child)
        if text:
            out.append((kind, text))
    return out


def parse_page(page_html: str) -> dict[str, Any]:
    """title, lede, meta [(key, value)], sections [{id, name, blocks}] (the whole page as one section for a
    one-program page is built by the caller)."""
    soup = BeautifulSoup(page_html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for card in soup.select(".hd-contact-card, script, style, nav, header, footer"):
        card.decompose()
    title = soup.select_one("h1.hd-hdr-title") or soup.find("h1")
    lede = soup.select_one("p.hd-hdr-lede")
    meta = []
    for row in soup.select(".hd-hdr-meta > div"):
        k, v = row.select_one(".hd-hdr-meta-k"), row.select_one(".hd-hdr-meta-v")
        if k and v and not SKIP_META.match(_text(k)):
            meta.append((_text(k), _text(v)))
    content = soup.find("main") or soup
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for el in content.find_all(["h2", "h3", "h4", "p", "ul", "ol", "div"]):
        if el.name == "h2" and "hd-sec-h2" in (el.get("class") or []):
            badges = [_text(b) for b in el.select(".hd-badge")]
            for b in el.select(".hd-badge"):
                b.decompose()
            name = _text(el)
            current = None if SKIP_SECTIONS.match(name) else {"id": el.get("id", ""), "name": name, "badges": badges, "blocks": []}
            if current:
                sections.append(current)
            continue
        if current is None or el.name == "div":
            continue
        if el.find_parent(["li", "ul", "ol"]) is not None and el.name != "ul":
            continue
        if el.name in ("ul", "ol") and el.find_parent(["ul", "ol"]) is not None:
            continue
        current["blocks"] += _block_lines(el)
    # one-program pages: everything that is not a section heading
    body_blocks: list[tuple[str, str]] = []
    for el in content.find_all(["h2", "h3", "h4", "p", "ul", "ol"]):
        if el.find_parent(["ul", "ol"]) is not None and el.name not in ("ul", "ol"):
            continue
        if el.name in ("ul", "ol") and el.find_parent(["ul", "ol"]) is not None:
            continue
        if el.name == "h2" and SKIP_SECTIONS.match(_text(el)):
            continue
        body_blocks += _block_lines(el)
    return {"title": _text(title) if title else "", "lede": _text(lede) if lede else "", "meta": meta,
            "sections": sections, "body": body_blocks}


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    prior = prior or {}
    records: list[RawRecord] = []
    with _client() as client:
        for i, (slug, mode) in enumerate(PAGES.items()):
            if i:
                time.sleep(DELAY_S)
            try:
                page = parse_page(_get(client, f"{BASE}/{slug}/"))
            except httpx.HTTPError:
                records += [RawRecord(source_connector=CONNECTOR, source_id=sid, payload=p)
                            for sid, p in prior.items() if sid == slug or sid.startswith(slug + "#")]
                continue
            if mode == "page":
                records.append(RawRecord(source_connector=CONNECTOR, source_id=slug,
                                         payload={"slug": slug, "mode": mode, "page": page, "section": None}))
            else:
                for section in page["sections"]:
                    sid = f"{slug}#{section['id']}" if section["id"] else f"{slug}#{len(records)}"
                    records.append(RawRecord(source_connector=CONNECTOR, source_id=sid,
                                             payload={"slug": slug, "mode": mode, "page": {k: v for k, v in page.items() if k != "sections"},
                                                      "section": section}))
            if limit and len(records) >= limit:
                break
    return records[:limit] if limit else records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    return {"status": "unknown"}


# ---------- normalize ----------

def status_lines(page: dict[str, Any], section: dict[str, Any] | None) -> list[tuple[str, str]]:
    """The header meta lines that belong to this program: all but Who applies on a one-program page; on a sections
    page the lines whose key begins with the section's first word."""
    lines = [(k, v) for k, v in page.get("meta", []) if k.lower() != WHO_APPLIES]
    if section is None:
        return lines
    first = section["name"].split(" ")[0].lower().rstrip(":")
    return [(k, v) for k, v in lines if k.lower().startswith(first)]


def status_sentence(page: dict[str, Any], section: dict[str, Any] | None) -> str | None:
    """The program's status line: a header meta line (`key: value`, the open one first), else a badge on its
    heading, else the first sentence or dated list line in its text that states a round's position."""
    metas = status_lines(page, section)
    if metas:
        lines = [f"{k}: {v}" for k, v in metas]
        open_ones = [line for line in lines if OPEN_RE.search(line) and not CLOSED_RE.search(line)]
        return open_ones[0] if open_ones else lines[0]
    if section and section.get("badges"):
        return section["badges"][0]
    blocks = section["blocks"] if section else page.get("body", [])
    for _kind, text in blocks:
        for s in sentences(text):
            if STATUS_RE.search(s):
                return s
    return None


def _dates_in(text: str) -> list[date]:
    return [d for d in (parse_date(m.replace(".", "")) for m in FULL_DATE_RE.findall(text)) if d]


def program_dates(page: dict[str, Any], section: dict[str, Any] | None) -> tuple[date | None, date | None]:
    """(opens_at, closes_at) from the program's status lines and dated list lines only, never from prose: a
    `from X through Y` range gives both, an `opens` line the open, a `due`/`closed` line the close."""
    blocks = section["blocks"] if section else page.get("body", [])
    metas = [f"{k}: {v}" for k, v in status_lines(page, section)]
    # the status card is the record of the current round; dated list lines are read only when there is no card
    lines = metas if metas else [t for k, t in blocks if k == "li"]
    opens = closes = None
    for line in lines:
        dates = _dates_in(line)
        if not dates:
            continue
        if RANGE_RE.search(line) and len(dates) >= 2:
            return dates[0], dates[-1]
        if OPENS_RE.search(line) and opens is None:
            opens = dates[0]
        elif DUE_RE.search(line) and closes is None:
            closes = dates[-1]
    return opens, closes


def status_for(sentence: str | None, opens_at: date | None, closes_at: date | None, today: date) -> str:
    if not sentence:
        return "unknown"
    if CLOSED_RE.search(sentence):
        return "closed"
    if closes_at and closes_at < today:
        return "unknown"
    if opens_at and opens_at > today:
        return "forecasted"
    if OPEN_RE.search(sentence) or closes_at or opens_at:
        return "open"
    return "unknown"


def eligibility_lines(page: dict[str, Any], section: dict[str, Any] | None) -> list[str]:
    """The Who applies card (the page's own on a one-program page; on a sections page it belongs to the program the
    status card names), the paragraphs under an eligibility heading, and the sentences that say who may apply."""
    out: list[str] = []
    if section is None or status_lines(page, section):
        out += [v for k, v in page.get("meta", []) if k.lower() == WHO_APPLIES]
    blocks = section["blocks"] if section else page.get("body", [])
    on = False
    for kind, text in blocks:
        if kind == "heading":
            on = bool(ELIGIBILITY_HEADING_RE.search(text))
            continue
        if on:
            if text not in out:
                out.append(text)
            continue
        for s in sentences(text):
            if APPLICANT_RE.search(s) and s not in out:
                out.append(s)
    return out


def applicant_tags(lines: list[str]) -> list[ApplicantTag]:
    kept = [s for line in lines for s in sentences(line) if not NEGATION_RE.search(s)]
    return applicant_types_for(kept or None)


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    page, section, slug = raw.payload["page"], raw.payload.get("section"), raw.payload["slug"]
    today = today or date.today()
    name = clean(section["name"]) if section else (clean(page.get("title", "")) or slug)
    blocks = section["blocks"] if section else page.get("body", [])
    text = " ".join(t for _, t in blocks)
    sentence = status_sentence(page, section)
    opens_at, closes_at = program_dates(page, section)
    lines = eligibility_lines(page, section)
    summary = next((t for k, t in blocks if k == "p"), None) if section else (page.get("lede") or next((t for k, t in blocks if k == "p"), None))
    metas = status_lines(page, section)
    structured = {"status_lines": dict(metas)} if len(metas) > 1 else None
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=f"{BASE}/{slug}/" + (f"#{section['id']}" if section and section.get("id") else ""),
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(name) or ("rebate" if REBATE_RE.search(summary or "") else None),
        funding_source="pass_through" if FEDERAL_RE.search(text) else "direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status=status_for(sentence, opens_at, closes_at, today),
        opens_at=opens_at,
        closes_at=closes_at,
        closes_at_text=sentence,
        rolling=True if sentence and re.search(r"\brolling\b", sentence, re.I) else None,
        summary=summary,
        eligibility_text="\n".join(lines) or None,
        eligibility_structured=structured,
        applicant_types=applicant_tags(lines),
        categories=[],
        alns=[],
    )
