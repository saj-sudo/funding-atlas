"""Maryland Department of Natural Resources connector: parks, land, forest, water and boating grants and loans.

Source: https://dnr.maryland.gov (SharePoint, the state's `mdgov` theme; shared mechanics in
connectors/maryland_sharepoint.py). `/Pages/grantsandloans.aspx` is a hand-curated index: three `<h3>` sections
(Cost-share Programs, Financial and Technical Resources, Tax Credit Programs) with a unit heading (`<h3>`/`<h4>`:
Forest Service, Land Acquisition and Planning, Maryland Environmental Trust, Watershed & Climate Services, ...)
above each group of links. 32 on-site links, 21 distinct live pages after https/case/fragment normalization, two
dead. The Waterway Improvement Fund page is not on the index and is hand-added (`HAND_ADDED`), because it is one of
the three municipal programs the roadmap names.

Program pages are prose, so status is read sentence by sentence, closed wording first:

    The application period for the Fiscal Year 2028 Community Parks and Playgrounds Program grant is now closed.
    Applications are not currently being accepted. Check back in April 2027 for information about the next round.
    Application period opens on September 3, 2026. ... The Application deadline is December 1, 2026.
    Submit applications for State Waterway Improvement Funds via the link below by September 18, 2026, at 11:59 PM.
    Applications are accepted on a rolling basis and evaluated annually.

A closed page with a future "check back in <Month YYYY>" is `forecasted` (no date invented from a month). An
application sentence with a date gives `closes_at`; with no open/closed wording the page is `open` while that date
is ahead and `unknown` after it. "No longer accepting" is deliberately not a closed phrase: the Grants Gateway says
it about another program. Pages that say nothing about applications (Program Open Space Local's county formula,
Rural Legacy, the MET tax-benefit page) are `unknown`. See docs/connectors/md_dnr.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import Tag

from connectors.maryland_drupal import NEGATION_RE, clean, funding_type_for
from connectors.maryland_sharepoint import (
    BODY_SELECTOR,
    DATE_RE,
    MONTH,
    MarylandSharePointConnector,
    body_div,
    canonical_url,
    main_section,
    page_h1,
    page_sentences,
    parse_text_date,
    source_id_for,
)
from pipeline.models import CategoryTag

CONNECTOR = "md_dnr"
BASE = "https://dnr.maryland.gov"
AGENCY = "Maryland Department of Natural Resources"
AGENCY_CODE = "MD-DNR"

INDEX_PATH = "pages/grantsandloans.aspx"
INDEX_PATHS: tuple[str, ...] = (INDEX_PATH,)
SECTION_TITLES = {"cost-share programs", "financial and technical resources", "tax credit programs"}
# Programs the index does not link. The Waterway Improvement Fund page is the one the roadmap names.
HAND_ADDED: dict[str, dict[str, Any]] = {
    "boating/pages/grants.aspx": {
        "url": f"{BASE}/boating/Pages/grants.aspx", "section": None, "unit": "Boating Services", "listed": False,
    },
}
# The H1 on some pages is the unit, not the program; the program name is then the first <h2> of the body.
UNIT_H1 = {"land acquisition and planning"}
UNIT_CATEGORIES = {
    "land acquisition and planning": "parks",
    "watershed & climate services": "water",
    "boating services": "water",
}
# Program Open Space Local: "POS Local funds are allocated annually to the 23 Maryland Counties and Baltimore City
# based on a formula."
FUNDING_TYPE_OVERRIDES = {"land/pages/programopenspace/home.aspx": "formula"}
# Pages that name their federal source; listings verified on SAM.gov 2026-10-16.
#   LWCF: "administered nationally by the ... National Park Service" (15.916 Outdoor Recreation Acquisition,
#   Development and Planning). Forest Legacy: "a federal conservation easement program administered in partnership
#   with states" (10.676). Pumpout grants: "funded by the Federal Clean Vessel Act (75%)" (15.616). Volunteer Fire
#   Assistance: "Federal funds will reimburse up to 50 percent" of the USDA Forest Service VFA program (10.664
#   Cooperative Forestry Assistance).
PASS_THROUGH: dict[str, list[str]] = {
    "land/pages/lwcf-grants.aspx": ["15.916"],
    "forests/pages/programapps/forestlegacy.aspx": ["10.676"],
    "boating/pages/pumpout/grants.aspx": ["15.616"],
    "forests/pages/fire/otheragencies-rcfp.aspx": ["10.664"],
}

CLOSED_RE = re.compile(
    r"application period[^.]*\bis (?:now )?closed|applications? (?:are|is) not (?:currently )?being accepted"
    r"|not currently accepting applications|\b(?:is|are) now closed\b",
    re.I,
)
MONTH_YEAR = rf"{MONTH} \d{{4}}"
FORECAST_RE = re.compile(rf"check back in ({MONTH_YEAR})|next round[^.]*?({MONTH}\.?\s+\d{{1,2}},?\s+\d{{4}}|{MONTH_YEAR})", re.I)
OPEN_RE = re.compile(r"\bnow open\b|\bis open\b|\bare open\b|currently accepting|accepting applications|rolling basis", re.I)
NOT_RE = re.compile(r"no longer|\bnot\b", re.I)          # "is no longer accepting applications" is not an open sentence
ROLLING_RE = re.compile(r"rolling basis|year-round", re.I)
OPENS_RE = re.compile(rf"\b(?:opens|will open)\b[^.]{{0,20}}?({MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})", re.I)
# The sentence that carries the deadline: about applications or proposals, not reports, with a full date.
DEADLINE_SENTENCE_RE = re.compile(r"applicat|proposal", re.I)
DEADLINE_WORD_RE = re.compile(r"\bdue\b|\bdeadline\b|\bcloses? on\b|\bsubmit\w*\b[^.]*\bby\b|\bmust be (?:submitted|received)\b", re.I)
NOT_A_DEADLINE_RE = re.compile(r"\breports?\b|\bnotif|\baward", re.I)   # report due dates, "notified by", award dates
APPLICANT_SENTENCE_RE = re.compile(
    r"\beligible\b|\bmay apply\b|\bavailable to\b|\bopen to\b|\bapplicants?\b|\bapplications? from\b", re.I
)
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december")


# ---------- pure helpers (no I/O) ----------

def future_marker(text: str, today: date) -> tuple[bool, date | None]:
    """(is in the future, full date or None) for 'April 2027' or 'July 15, 2026'."""
    m = DATE_RE.search(text)
    if m:
        d = parse_text_date(m.group(0))
        return (d is not None and d > today), d
    m = re.search(rf"({MONTH}) (\d{{4}})", text, re.I)
    if m:
        month = next((i + 1 for i, name in enumerate(_MONTHS) if name.startswith(m.group(1).lower()[:3])), None)
        year = int(m.group(2))
        return (month is not None and (year, month) > (today.year, today.month)), None
    return False, None


def deadline_sentences(sents: list[str]) -> list[tuple[date, str]]:
    """(date, sentence) for every sentence about applications that carries a deadline word and a full date, in
    page order. A solicitation page lists one deadline per program; the round runs until the latest of them."""
    out: list[tuple[date, str]] = []
    for s in sents:
        if (DEADLINE_SENTENCE_RE.search(s) and not NOT_A_DEADLINE_RE.search(s) and DEADLINE_WORD_RE.search(s)
                and DATE_RE.search(s)):
            d = parse_text_date(s)
            if d:
                out.append((d, s))
    return out


def status_fields_for(main_html: str, today: date) -> dict[str, Any]:
    sents = page_sentences(main_html)
    texts: list[str] = []
    status: str | None = None
    opens_at: date | None = None
    rolling: bool | None = None

    closed = next((s for s in sents if CLOSED_RE.search(s)), None)
    if closed:
        status = "closed"
        texts.append(closed)
        forecast = next((s for s in sents if FORECAST_RE.search(s)), None)
        if forecast:
            ahead, d = future_marker(FORECAST_RE.search(forecast).group(0), today)
            if ahead:
                status, opens_at = "forecasted", d
            if forecast not in texts:
                texts.append(forecast)
    else:
        opened = next((s for s in sents if OPEN_RE.search(s) and not NOT_RE.search(s)), None)
        if opened:
            status = "open"
            rolling = True if ROLLING_RE.search(opened) else None
            texts.append(opened)

    due = deadline_sentences(sents)
    closes_at = max(d for d, _ in due) if due else None
    texts += [s for _, s in due if s not in texts]
    if opens_at is None:
        opens = next((m for s in sents for m in [OPENS_RE.search(s)] if m), None)
        if opens:
            opens_at = parse_text_date(opens.group(1))
            sentence = next(s for s in sents if OPENS_RE.search(s))
            if sentence not in texts:
                texts.insert(0, sentence)

    if status is None and closes_at:
        status = "open" if closes_at >= today else "unknown"
    if status is None:
        status = "unknown"
    return {
        "status": status,
        "opens_at": opens_at,
        "closes_at": closes_at,
        "closes_at_text": " ".join(texts) or None,
        "rolling": rolling if status == "open" and not due else None,     # a dated deadline beats a rolling footnote
    }


def applicant_lines_for(main_html: str) -> list[str]:
    """Sentences that name who may apply, minus negated ones."""
    out: list[str] = []
    for s in page_sentences(main_html):
        if APPLICANT_SENTENCE_RE.search(s) and not NEGATION_RE.search(s) and s not in out:
            out.append(s)
    return out


def program_name(main_html: str, title: str | None) -> str:
    """The H1, unless it is a unit name or empty: then the first <h2> of the body. Else the <title>."""
    h1 = page_h1(main_html)
    if h1 and h1.lower() not in UNIT_H1:
        return h1
    body = body_div(main_html)
    h2 = body.find("h2") if body else None
    return (clean(h2.get_text(" ")) if h2 else "") or h1 or clean(title)


def index_links(index_url: str, html_text: str) -> dict[str, dict[str, Any]]:
    """source_id -> {url, section, unit, listed} for every on-site .aspx link in the index body. A heading that is
    one of the three section titles sets the section; any other heading is the unit for the links after it."""
    section_el = main_section(html_text)
    if section_el is None:
        return {}
    body = section_el.select_one(BODY_SELECTOR) or section_el
    out: dict[str, dict[str, Any]] = {}
    section: str | None = None
    unit: str | None = None
    for el in body.descendants:
        if not isinstance(el, Tag):
            continue
        if el.name in ("h2", "h3", "h4"):
            text = clean(el.get_text(" "))
            if not text:
                continue
            if text.lower() in SECTION_TITLES:
                section, unit = text, None
            else:
                unit = text
        elif el.name == "a" and el.get("href"):
            url = canonical_url(el["href"], index_url)
            parsed = urlparse(url)
            if not parsed.netloc.lower().endswith("dnr.maryland.gov") or not parsed.path.lower().endswith(".aspx"):
                continue
            sid = source_id_for(url)
            if not sid or sid == INDEX_PATH:
                continue
            out.setdefault(sid, {"url": url, "section": section, "unit": unit, "listed": True})
    return out


# ---------- the connector ----------

class Dnr(MarylandSharePointConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    PASS_THROUGH = PASS_THROUGH

    def index_entries(self, client: httpx.Client) -> dict[str, dict[str, Any]]:
        url = f"{BASE}/{INDEX_PATH}"
        resp = client.get(url)
        resp.raise_for_status()
        entries = index_links(url, resp.text)
        for sid, entry in HAND_ADDED.items():
            entries.setdefault(sid, dict(entry))
        return entries

    def name_for(self, payload: dict[str, Any]) -> str:
        return program_name(payload.get("main_html") or "", payload.get("title"))

    def status_fields(self, payload: dict[str, Any], today: date) -> dict[str, Any]:
        return status_fields_for(payload.get("main_html") or "", today)

    def applicant_lines(self, payload: dict[str, Any]) -> list[str]:
        return applicant_lines_for(payload.get("main_html") or "")

    def categories_for(self, payload: dict[str, Any]) -> list[CategoryTag]:
        unit = payload.get("unit") or ""
        return [CategoryTag(value=UNIT_CATEGORIES.get(unit.lower(), "other"), source_code=unit or "dnr")]

    def funding_type_for(self, name: str, payload: dict[str, Any]) -> str | None:
        sid = source_id_for(payload.get("url") or "")
        return FUNDING_TYPE_OVERRIDES.get(sid) or funding_type_for(name)


SITE = Dnr()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
classify_page = SITE.classify_page
