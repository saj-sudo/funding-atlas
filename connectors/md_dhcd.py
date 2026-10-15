"""Maryland DHCD connector: state housing, energy, and neighborhood-revitalization programs.

Source: https://dhcd.maryland.gov (Drupal). No API. Enumerate from sitemap.xml, fetch each candidate
page, read the themed "Application" box (`div.maryland-summary-box`) that program pages carry:

    <li><p><strong>Application status:</strong> Open</p></li>
    <li><p><strong>Application opens:</strong> September 22, 2026</p></li>
    <li><p><strong>Application closes:</strong> November 2, 2026</p></li>

A page becomes a record only if its box has a status-type label (Application / Registration / Funding /
Waitlist status). Pages without one are never records: a listing that doesn't know it's closed is worse
than none. The box's label and date wording varies page to page; `LABEL_KINDS` and `parse_box_date`
hold the whole normalization problem. See docs/connectors/md_dhcd.md for the live survey and mapping.

fetch(prior=...) skips a record page whose sitemap `lastmod` has not moved since the stored payload. Only
record pages are stored, so the ~170 box-less pages are refetched every run: a cold run is ~200 requests
and a warm run ~170 (about two minutes and 75 seconds at 0.3 s each). Fine for one agency; revisit if a
third Drupal agency makes the no-box pages worth remembering. To force a full refetch:
  DELETE FROM raw_record WHERE source_connector = 'md_dhcd';

Out of scope here (no box on the page): multifamily financing programs (Rental Housing, LIHTC, HOME,
NHTF), the sub-programs of State Revitalization Programs (Community Legacy, Facade, Strategic Demolition,
BRNI, NCSED, SEED), and anything that only lives in a public notice. Individual and household programs
(home repair loans, EmPOWER, WAP, MEAP, HCVP) are ingested because their box is there; the municipal view
filters them out by applicant type.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from connectors.grants_gov import parse_date
from connectors.sam_assistance_listings import clean
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "md_dhcd"
BASE = "https://dhcd.maryland.gov"
SITEMAP_URL = BASE + "/sitemap.xml"
AGENCY = "Maryland Department of Housing and Community Development"
AGENCY_CODE = "MD-DHCD"

PAGE_DELAY_S = 0.3
TIMEOUT_S = 30.0

# Sitemap paths that are never program pages.
SKIP_PATH = re.compile(
    r"^/(media|news-stories|contacts|about-us|public-information-and-media-inquiries|page-not-found"
    r"|google-translation-disclaimer|procurement)(/|$)"
    r"|special-loan-programs-local-contacts|program-contacts"
)

# Federal pass-throughs among the pages that carry a box, by source_id. Everything else is state money.
# ALNs verified on SAM.gov 2026-10-15; the Recovery Housing Program has no listing of its own, so no ALN.
PASS_THROUGH: dict[str, list[str]] = {
    "neighborhood-revitalization/community-development-funding/community-development-block-grant-program": ["14.228"],
    "neighborhood-revitalization/community-development-funding/community-development-block-grant-program/recovery-housing-program": [],
    "energy-home-repair/energy-grants-and-loans-residents/weatherization-assistance-program-wap": ["81.042"],
    "energy-home-repair/energy-grants-and-loans-residents/maryland-energy-assistance-program": ["93.568"],
}

# First URL segment -> categories. source_code is the segment.
SECTION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "housing": ("housing",),
    "energy-home-repair": ("energy", "housing"),
    "neighborhood-revitalization": ("housing",),
    "infrastructure": ("infrastructure",),
}

# Name keyword -> funding_type, first match wins.
FUNDING_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("tax credit", "tax_credit"), ("loan", "loan"), ("voucher", "voucher"), ("grant", "grant"),
)

# Phrase regex -> applicant types. Scanned over the who-may-apply sections only, never the whole page.
# The matched phrase is stored as source_code so the inference is auditable in SQL.
APPLICANT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"units? of (?:general )?local government", ("municipality", "county")),
    (r"local governments?", ("municipality", "county")),
    (r"municipalit\w*", ("municipality",)),
    (r"\bcities\b", ("municipality",)),
    (r"\btowns?\b", ("municipality",)),
    (r"\bcount(?:y|ies)\b", ("county",)),
    (r"\bnon-?profits?\b", ("nonprofit",)),
    (r"501\s?\(c\)\s?\(3\)", ("nonprofit",)),
    (r"\bfor-profits?\b", ("business",)),
    (r"\bbusiness(?:es)?\b", ("business",)),
    (r"\bretailers?\b", ("business",)),
    (r"\bdevelopers?\b", ("business",)),
    (r"\bhomeowners?\b", ("household",)),
    (r"\bhouseholds?\b", ("household",)),
    (r"\bresidents?\b", ("household",)),
    (r"\brenters?\b", ("household",)),
    (r"\bindividuals?\b", ("individual",)),
    (r"housing authorit\w*", ("housing_authority",)),
    (r"\bschools?\b", ("school",)),
    (r"local education agenc\w*", ("school",)),
)

# Box label (lowercased, colon and nbsp stripped) -> kind.
LABEL_KINDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(applications?|registration) status$"), "status"),
    (re.compile(r"^funding status$"), "funding_status"),
    (re.compile(r"^waitlist status$"), "waitlist_status"),
    (re.compile(r"^(application|registration)( period)? open(s|ed)?( \(expected\))?$"), "opens"),
    (re.compile(r"^(application|registration)( period)? close(s|d)?( \(expected\))?$|^application deadline$"), "closes"),
    (re.compile(r"^next funding cycle$"), "cycle"),
)
STATUS_KINDS = {"status", "funding_status", "waitlist_status"}
DATE_KINDS = {"opens", "closes", "cycle"}   # kept verbatim in closes_at_text; only opens/closes parse

ROLLING_RE = re.compile(r"until (available )?funds|rolling|ongoing", re.I)
MATCH_NOT_REQUIRED_RE = re.compile(r"match(?:ing)?(?: funds?)? (?:is|are) not required", re.I)
MATCH_REQUIRED_RE = re.compile(r"match(?:ing)?(?: funds?)? (?:is|are) required", re.I)
MONTH_YEAR_RE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})$")


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(
        timeout=TIMEOUT_S, follow_redirects=True,
        headers={"User-Agent": "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"},
    )


def iter_sitemap(xml_text: str) -> list[tuple[str, str | None]]:
    """(url, lastmod) for every sitemap entry that could be a program page. Pure; tested on a fixture."""
    root = ET.fromstring(xml_text)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    out: list[tuple[str, str | None]] = []
    for url in root.findall("s:url", ns):
        loc = (url.findtext("s:loc", default="", namespaces=ns) or "").strip()
        if not loc.startswith(BASE):
            continue
        path = urlparse(loc).path
        if path in ("", "/") or SKIP_PATH.search(path):
            continue
        lastmod = (url.findtext("s:lastmod", default="", namespaces=ns) or "").strip() or None
        out.append((loc, lastmod))
    return out


def source_id_for(url: str) -> str:
    return urlparse(url).path.strip("/")


def needs_fetch(lastmod: str | None, prior_payload: dict[str, Any] | None) -> bool:
    """Refetch unless the stored payload has the same sitemap lastmod AND usable page HTML."""
    if not prior_payload or not prior_payload.get("main_html"):
        return True
    return not lastmod or lastmod != prior_payload.get("lastmod")


def page_payload(url: str, lastmod: str | None, html_text: str) -> dict[str, Any] | None:
    """The raw_record payload for one page, or None if the page has no <main>."""
    soup = BeautifulSoup(html_text, "html.parser")
    main = soup.find("main")
    if main is None:
        return None
    updated = soup.find("meta", property="og:updated_time")
    desc = soup.find("meta", attrs={"name": "description"})
    return {
        "url": url,
        "lastmod": lastmod,
        "updated_time": updated.get("content") if isinstance(updated, Tag) else None,
        "description": desc.get("content") if isinstance(desc, Tag) else None,
        "main_html": str(main),
    }


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """`prior` maps source_id -> the payload stored in raw_record on the previous run. Only pages whose
    box carries a status-type label are returned; `limit` caps records, not pages walked."""
    prior = prior or {}
    out: list[RawRecord] = []
    with _client() as client:
        r = client.get(SITEMAP_URL)
        r.raise_for_status()
        for url, lastmod in iter_sitemap(r.text):
            sid = source_id_for(url)
            previous = prior.get(sid)
            if needs_fetch(lastmod, previous):
                resp = client.get(url)
                time.sleep(PAGE_DELAY_S)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                payload = page_payload(url, lastmod, resp.text)
            else:
                payload = previous
            if payload is None or not has_status_label(parse_box(payload["main_html"])):
                continue
            out.append(RawRecord(source_connector=CONNECTOR, source_id=sid, payload=payload))
            if limit and len(out) >= limit:
                break
    return out


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A page that dropped out of the sitemap. Still there with a box: report what the box says.
    Gone, or box removed: 'unknown' (a vanished page is not evidence that a program closed).
    Network error: None (caller marks unknown)."""
    try:
        with _client() as client:
            resp = client.get(f"{BASE}/{source_id}")
    except Exception:  # noqa: BLE001
        return None
    if resp.status_code == 404:
        return {"status": "unknown"}
    try:
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    payload = page_payload(f"{BASE}/{source_id}", None, resp.text)
    return classify_page(payload)


def classify_page(payload: dict[str, Any] | None, today: date | None = None) -> dict[str, Any]:
    lines = parse_box(payload["main_html"]) if payload else []
    if not has_status_label(lines):
        return {"status": "unknown"}
    return {"status": status_for(lines, today), "closes_at": closes_at_for(lines)}


# ---------- box parsing ----------

def _label_key(label: str) -> str:
    return clean(label).rstrip(":").strip().lower()


def parse_box(main_html: str) -> list[tuple[str, str]]:
    """(label, value) per bullet of the summary box, labels normalized to lowercase without the colon.
    Unlabeled bullets get label ''. No box -> []."""
    soup = BeautifulSoup(main_html, "html.parser")
    box = soup.select_one(".maryland-summary-box")
    if box is None:
        return []
    lines: list[tuple[str, str]] = []
    for li in box.select("li"):
        strong = li.find("strong")
        if strong is not None:
            label = _label_key(strong.get_text(" "))
            strong.extract()
        else:
            label = ""
        value = clean(li.get_text(" ")).lstrip(":").strip()
        if label or value:
            lines.append((label, value))
    return lines


def label_kind(label: str) -> str | None:
    for pattern, kind in LABEL_KINDS:
        if pattern.match(label):
            return kind
    return None


def has_status_label(lines: list[tuple[str, str]]) -> bool:
    return any(label_kind(label) in STATUS_KINDS for label, _ in lines)


def _first(lines: list[tuple[str, str]], kind: str) -> tuple[str, str] | None:
    for label, value in lines:
        if label_kind(label) == kind:
            return label, value
    return None


_weekday_re = re.compile(r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+", re.I)
_tail_re = re.compile(r"\s+(at|by)\s+.*$|\s*\(E[DS]T\).*$|,?\s+\d{1,2}:\d{2}.*$", re.I)


def parse_box_date(value: str) -> date | None:
    """'Friday, February 20, 2026 at 8:00 AM(EDT)' -> 2026-02-20. Month-only and prose -> None."""
    s = _weekday_re.sub("", clean(value))
    s = _tail_re.sub("", s).strip().rstrip(",").strip()
    return parse_date(s)


def _future_marker(value: str, today: date) -> bool:
    """Does an opens-line name a date, or a month-year, after today? Used only for the forecasted rule."""
    d = parse_box_date(value)
    if d is None:
        m = MONTH_YEAR_RE.match(clean(value))
        if m:
            d = parse_date(f"{m.group(1)} 1, {m.group(2)}")
    return d is not None and d > today


def status_for(lines: list[tuple[str, str]], today: date | None = None) -> str:
    today = today or date.today()
    for label, value in lines:
        kind = label_kind(label)
        v = value.lower()
        if kind == "status":
            if v == "open":
                return "open"
            if v == "closed":
                opens = _first(lines, "opens")
                return "forecasted" if opens and _future_marker(opens[1], today) else "closed"
            return "unknown"           # 'Varies by jurisdiction' and anything else
        if kind == "funding_status":
            return "exhausted" if re.search(r"fully spent|exhausted", v) else "unknown"
        if kind == "waitlist_status":
            return "unknown"
    return "unknown"


def opens_at_for(lines: list[tuple[str, str]]) -> date | None:
    line = _first(lines, "opens")
    return parse_box_date(line[1]) if line else None


def closes_at_for(lines: list[tuple[str, str]]) -> date | None:
    line = _first(lines, "closes")
    return parse_box_date(line[1]) if line else None


def closes_at_text_for(lines: list[tuple[str, str]]) -> str | None:
    parts = [f"{label}: {value}" for label, value in lines if label_kind(label) in DATE_KINDS]
    return "; ".join(parts) or None


def rolling_for(lines: list[tuple[str, str]]) -> bool | None:
    line = _first(lines, "closes")
    return True if line and ROLLING_RE.search(line[1]) else None


# ---------- body parsing ----------

def page_name(main_html: str) -> str:
    soup = BeautifulSoup(main_html, "html.parser")
    h1 = soup.find("h1")
    return clean(h1.get_text(" ")) if h1 else ""


def body_sections(main_html: str) -> list[tuple[str, str]]:
    """(heading, text) for each <h2> section of the page body, in order."""
    soup = BeautifulSoup(main_html, "html.parser")
    prose = soup.select_one(".usa-prose.maryland-toc-target") or soup
    out: list[tuple[str, str]] = []
    heading: str | None = None
    parts: list[str] = []

    def flush() -> None:
        if heading is not None:
            out.append((heading, clean(" ".join(parts))))

    for el in prose.children:
        if isinstance(el, Tag) and el.name == "h2":
            flush()
            heading, parts = clean(el.get_text(" ")), []
        elif heading is not None:
            text = el.get_text(" ") if isinstance(el, Tag) else str(el)
            if text.strip():
                parts.append(text)
    flush()
    return out


ELIGIBILITY_HEADING_RE = re.compile(r"eligib", re.I)
# Eligibility sections about things rather than people ("Eligible activities", "Eligible project
# locations", "Eligible use of funds", "Eligible contributions"). Applicant tags are inferred from the
# other eligibility sections only, so "serve residents of a Priority Funding Area" never tags a household.
THING_HEADING_RE = re.compile(
    r"project|activit|location|\buse|contribution|cost|expense|propert|improvement|\barea|\bwork|fund|service|item|repair",
    re.I,
)


def eligibility_text_for(sections: list[tuple[str, str]]) -> str | None:
    texts = [text for heading, text in sections if ELIGIBILITY_HEADING_RE.search(heading) and text]
    return "\n\n".join(texts) or None


def applicant_sections_text(sections: list[tuple[str, str]]) -> str:
    return " ".join(
        text for heading, text in sections
        if ELIGIBILITY_HEADING_RE.search(heading) and not THING_HEADING_RE.search(heading) and text
    )


def applicant_types_for(applicant_text: str | None) -> list[ApplicantTag]:
    if not applicant_text:
        return []
    tags: list[ApplicantTag] = []
    for pattern, values in APPLICANT_KEYWORDS:
        m = re.search(pattern, applicant_text, re.I)
        if m:
            phrase = m.group(0).lower()
            tags += [ApplicantTag(value=v, source_code=phrase) for v in values]
    return tags


def match_required_for(body_text: str) -> bool | None:
    if MATCH_NOT_REQUIRED_RE.search(body_text):
        return False
    if MATCH_REQUIRED_RE.search(body_text):
        return True
    return None


def funding_type_for(name: str) -> str | None:
    n = name.lower()
    for keyword, ft in FUNDING_TYPE_KEYWORDS:
        if keyword in n:
            return ft
    return None


def categories_for(source_id: str) -> list[CategoryTag]:
    section = source_id.split("/", 1)[0]
    return [CategoryTag(value=c, source_code=section) for c in SECTION_CATEGORIES.get(section, ("other",))]


# ---------- normalize ----------

def normalize(raw: RawRecord, today: date | None = None) -> Program:
    payload = raw.payload
    main_html: str = payload.get("main_html") or ""
    url: str = payload.get("url") or f"{BASE}/{raw.source_id}"
    lines = parse_box(main_html)
    sections = body_sections(main_html)
    eligibility = eligibility_text_for(sections)
    body_text = " ".join(text for _, text in sections)
    alns = PASS_THROUGH.get(raw.source_id)

    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=url,
        external_number=None,
        name=page_name(main_html),
        level="state",
        jurisdiction="MD",
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(page_name(main_html)),
        funding_source="pass_through" if alns is not None else "direct",
        amount_min=None,
        amount_max=None,
        match_required=match_required_for(body_text),
        match_pct=None,
        status=status_for(lines, today),
        opens_at=opens_at_for(lines),
        closes_at=closes_at_for(lines),
        closes_at_text=closes_at_text_for(lines),
        rolling=rolling_for(lines),
        summary=clean(payload.get("description")) or None,
        eligibility_text=eligibility,
        eligibility_structured=None,
        applicant_types=applicant_types_for(applicant_sections_text(sections)),
        categories=categories_for(raw.source_id),
        alns=alns or [],
    )
