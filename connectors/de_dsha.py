"""Delaware State Housing Authority (Housing Delaware) connector: the "Build & Develop" program pages.

Source: https://www.destatehousing.com (WordPress, no robots restrictions). Six hand-listed pages in two shapes: a
one-program page (a header card with status lines and "Who applies") or a sections page (one program per
`h2.hd-sec-h2`, each with its paragraphs, eligibility panel and Important dates list). The header meta is the status
of record where its key names the program. Contact cards are never read. On the hand-list base
(`connectors/hand_list.py`) since 12.1, with its own page reader, dates and status table. See docs/connectors/de_dsha.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from bs4 import Tag

from connectors.grants_gov import parse_date
from connectors.hand_list import Blocks, HandListConnector, applicant_tags, first_p, soup
from connectors.maryland_drupal import sentences
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for
from pipeline.models import RawRecord

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

ELIGIBILITY_HEADING_RE = re.compile(r"eligibility|eligible applicants|who applies|applicant qualifications", re.I)   # not "Eligible activities"
APPLICANT_RE = re.compile(r"\b(?:eligible to apply|may apply|who applies|apply to housing delaware|are eligible)\b", re.I)
STATUS_RE = re.compile(r"\b(?:closed|not currently accepting|rolling|applications? open|current round|accepting applications|due|deadline|round opens|opens)\b", re.I)
CLOSED_RE = re.compile(r"\b(?:closed|not currently accepting)\b", re.I)
OPEN_RE = re.compile(r"\b(?:rolling|applications? open|current round|accepting applications|now open|round opens|now accepting)\b", re.I)
RANGE_RE = re.compile(r"\b(?:from|open)\b.*\b(?:through|to|until)\b", re.I)
DUE_RE = re.compile(r"\b(?:due|deadline|through|until|by|closed|closes)\b", re.I)
OPENS_RE = re.compile(r"\bopens?\b", re.I)
# This site abbreviates months ("Sept. 30, 2026"), so the base's date regexes do not fit it.
FULL_DATE_RE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b")
FEDERAL_RE = re.compile(r"\bfederal (?:grant|funding|funds|program)\b|\bHUD\b|\bU\.S\. Department of Housing\b", re.I)
REBATE_RE = re.compile(r"\brebate", re.I)


# ---------- parsing (no I/O) ----------

def _text(el: Tag) -> str:
    return clean(el.get_text(" "))


def _block_lines(el: Tag) -> Blocks:
    """(kind, text) for one element: a heading, a paragraph, each list item, or a panel's heading and paragraphs."""
    if el.name in ("h2", "h3", "h4"):
        return [("heading", _text(el))]
    if el.name == "p":
        return [("p", _text(el))] if _text(el) else []
    if el.name in ("ul", "ol"):
        return [("li", clean(li.get_text(" "))) for li in el.find_all("li") if clean(li.get_text(" "))]
    out: Blocks = []
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
    doc = soup(page_html)
    for card in doc.select(".hd-contact-card, script, style, nav, header, footer"):
        card.decompose()
    title = doc.select_one("h1.hd-hdr-title") or doc.find("h1")
    lede = doc.select_one("p.hd-hdr-lede")
    meta = []
    for row in doc.select(".hd-hdr-meta > div"):
        k, v = row.select_one(".hd-hdr-meta-k"), row.select_one(".hd-hdr-meta-v")
        if k and v and not SKIP_META.match(_text(k)):
            meta.append((_text(k), _text(v)))
    content = doc.find("main") or doc
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
    body_blocks: Blocks = []
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


# ---------- status and applicants (no I/O) ----------

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


# ---------- the connector ----------

class Dsha(HandListConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = JURISDICTION
    PAGES = PAGES

    def urls_for(self, slug: str, spec: str) -> list[str]:
        return [f"{BASE}/{slug}/"]

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        """One record for a one-program page; one per section otherwise, keyed by the heading's id or, without one,
        by the record count so far."""
        page = pages[0]
        if spec == "page":
            return [(slug, {"slug": slug, "mode": spec, "page": page, "section": None})]
        out: list[tuple[str, dict[str, Any]]] = []
        for section in page["sections"]:
            sid = f"{slug}#{section['id']}" if section["id"] else f"{slug}#{count + len(out)}"
            out.append((sid, {"slug": slug, "mode": spec, "page": {k: v for k, v in page.items() if k != "sections"},
                              "section": section}))
        return out

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        page, section, slug = raw.payload["page"], raw.payload.get("section"), raw.payload["slug"]
        name = clean(section["name"]) if section else (clean(page.get("title", "")) or slug)
        blocks = section["blocks"] if section else page.get("body", [])
        text = " ".join(t for _, t in blocks)
        sentence = status_sentence(page, section)
        opens_at, closes_at = program_dates(page, section)
        lines = eligibility_lines(page, section)
        summary = first_p(blocks) if section else (page.get("lede") or first_p(blocks))
        metas = status_lines(page, section)
        structured = {"status_lines": dict(metas)} if len(metas) > 1 else None
        return dict(
            source_url=f"{BASE}/{slug}/" + (f"#{section['id']}" if section and section.get("id") else ""),
            name=name,
            funding_type=funding_type_for(name) or ("rebate" if REBATE_RE.search(summary or "") else None),
            funding_source="pass_through" if FEDERAL_RE.search(text) else "direct",
            match_required=None,
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
        )


SITE = Dsha()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
