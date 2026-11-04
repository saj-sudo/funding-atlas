"""Massachusetts Community One Stop for Growth connector: fourteen capital grant programs under one application.

Source: https://www.mass.gov/info-details/community-one-stop-for-growth (Drupal 11). The page is the index and the
round at once: under "One Stop Programs" three agencies (h3) each list their programs as links, nine to mass.gov pages
in three templates and five to sections of one massdevelopment.com page; under "... Key Dates" the round's dates, the
same for every program (one NOFA). Status comes from those dates, never from the heading (which names FY27 over FY26
dates); applicants come from each program page's own prose. Index first, then one GET per program page and one for the
MassDevelopment page. On the hand-list helpers (`connectors/hand_list.py`). See docs/connectors/ma_onestop.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import Tag

from connectors.hand_list import (
    DATE_RE,
    DELAY_S,
    Blocks,
    applicant_tags,
    blocks_from,
    first_p,
    label_lines,
    last_date,
    resolve_missing,  # noqa: F401  (the pipeline reads it from this module)
)
from connectors.hand_list import client as _client
from connectors.hand_list import get as _get
from connectors.hand_list import soup as _soup
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for
from pipeline.models import CategoryTag, Program, RawRecord

CONNECTOR = "ma_onestop"
INDEX_URL = "https://www.mass.gov/info-details/community-one-stop-for-growth"
JURISDICTION = "MA"
PROGRAMS_HEADING_RE = re.compile(r"^one stop programs$", re.I)
KEY_DATES_RE = re.compile(r"\bkey dates\b", re.I)
AGENCY_CODES = {
    "Executive Office of Economic Development": "MA-EOED",
    "Executive Office of Housing and Livable Communities": "MA-EOHLC",
    "MassDevelopment Finance Agency": "MA-MASSDEV",
}
# The One Stop groups its programs by agency; housing's office is housing, the other two are economic development,
# which is infrastructure everywhere (decision 10.1).
AGENCY_CATEGORIES = {"MA-EOHLC": "housing", "MA-EOED": "infrastructure", "MA-MASSDEV": "infrastructure"}

OPENS_RE = re.compile(r"\bopens?\b", re.I)
FULL_APPLICATION_RE = re.compile(r"\bfull application submission\b", re.I)
LABEL_RE = re.compile(r"eligib|who (?:may|can) apply", re.I)
APPLICANT_RE = re.compile(
    r"\b(?:eligible (?:to apply|to submit|municipalit\w*|entities|applicants?)|are eligible|may apply|is available to"
    r"|open to municipalit\w*|provides grants to|municipalities and other public entities|a (?:community|municipality) must)\b", re.I)
FEDERAL_RE = re.compile(r"\bfederal (?:funds|funding|grant|program)\b|\bHUD\b", re.I)
MATCH_RE = re.compile(r"\bmatch(?:ing)? (?:requirement|funds?|is required)\b|\b\d{1,3}% (?:local )?match\b", re.I)
CONTACT_RE = re.compile(r"@|\b\d{3}[.-]\d{3}[.-]\d{4}\b|\bcontact us\b", re.I)
ZWSP_RE = re.compile(r"[​﻿]")


# ---------- parsing (no I/O) ----------

def _text(el: Tag) -> str:
    return clean(ZWSP_RE.sub("", el.get_text(" ")))


def source_id_for(url: str) -> str:
    """The last path segment of a mass.gov link; `massdev#<fragment>` for a MassDevelopment anchor."""
    plain, fragment = urldefrag(url)
    if "massdevelopment.com" in urlparse(plain).netloc:
        return f"massdev#{fragment}" if fragment else "massdev"
    return urlparse(plain).path.rstrip("/").rsplit("/", 1)[-1]


def _section_lines(main: Tag, heading_re: re.Pattern[str]) -> list[Tag]:
    """The elements between the h2 whose text matches and the next h2."""
    start = next((h for h in main.find_all("h2") if heading_re.search(_text(h))), None)
    out: list[Tag] = []
    node = start
    while start is not None and node is not None:
        node = node.find_next()
        if node is None or node.name == "h2":
            break
        out.append(node)
    return out


def parse_index(index_html: str) -> dict[str, Any]:
    """programs: [{agency, agency_code, title, url, source_id}] in page order; round: {heading, lines}."""
    doc = _soup(index_html)
    main = doc.find("main") or doc
    programs: list[dict[str, Any]] = []
    agency: str | None = None
    for el in _section_lines(main, PROGRAMS_HEADING_RE):
        if el.name == "h3":
            agency = _text(el)
        elif el.name == "a" and el.get("href") and agency and _text(el):
            url = urljoin(INDEX_URL, el["href"])
            programs.append({"agency": agency, "agency_code": AGENCY_CODES.get(agency), "title": _text(el), "url": url,
                             "source_id": source_id_for(url)})
    heading = next((h for h in main.find_all("h2") if KEY_DATES_RE.search(_text(h))), None)
    lines: list[str] = []
    for el in _section_lines(main, KEY_DATES_RE):
        if el.name in ("p", "li"):
            t = _text(el)
            if t and t not in lines:
                lines.append(t)
    return {"programs": programs, "round": {"heading": _text(heading) if heading else "", "lines": lines}}


def _rich_text(main: Tag) -> list[Tag]:
    """The outermost editor prose blocks of a mass.gov page; contacts, menus and the feedback form sit outside them."""
    return [d for d in main.select(".ma__rich-text") if d.find_parent(class_="ma__rich-text") is None]


def parse_page(page_html: str, fragment: str | None = None) -> dict[str, Any]:
    """title, blocks [(kind, text)] for a program: a mass.gov page's rich-text blocks, or one `section` of the
    MassDevelopment page when `fragment` names it."""
    doc = _soup(page_html)
    if fragment:
        section = doc.find(id=fragment)
        if section is None:
            return {"title": "", "blocks": []}
        h = section.find(["h2", "h3"])
        return {"title": _text(h) if h else "", "blocks": blocks_from(section, ["h3", "h4", "p", "li"], drop_re=CONTACT_RE)}
    main = doc.find("main") or doc
    h1 = main.find("h1") or doc.find("h1")
    blocks: Blocks = []
    for block in _rich_text(main):
        blocks += blocks_from(block, ["h2", "h3", "h4", "p", "li"], drop_re=CONTACT_RE)
    return {"title": _text(h1) if h1 else "", "blocks": blocks}


def round_dates(lines: list[str]) -> tuple[date | None, date | None, str | None]:
    """(opens_at, closes_at, the deadline line) from the Key Dates lines: the date on the Opens line, the last date on
    the first Full Application Submission line."""
    opens = next((last_date(line, DATE_RE) for line in lines if OPENS_RE.search(line) and DATE_RE.search(line)), None)
    deadline = next((line for line in lines if FULL_APPLICATION_RE.search(line) and DATE_RE.search(line)), None)
    return opens, (last_date(deadline, DATE_RE) if deadline else None), deadline


def status_for(opens_at: date | None, closes_at: date | None, today: date) -> str:
    if closes_at is None:
        return "unknown"
    if closes_at < today:
        return "closed"
    if opens_at and opens_at > today:
        return "forecasted"
    return "open"


def applicant_lines(blocks: Blocks) -> list[str]:
    return label_lines(blocks, LABEL_RE, APPLICANT_RE, keep_kinds=("li", "p"))


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The index (a failure raises: without it nothing is known), then one GET per mass.gov program page and one for
    the MassDevelopment page. A page that fails keeps the stored page, with the fresh round facts stamped on."""
    prior = prior or {}
    records: list[RawRecord] = []
    shared: dict[str, str] = {}
    with _client() as client:
        index = parse_index(_get(client, INDEX_URL))
        programs = index["programs"][:limit] if limit else index["programs"]
        for program in programs:
            sid = program["source_id"]
            plain, fragment = urldefrag(program["url"])
            payload: dict[str, Any] = {"program": program, "round": index["round"], "page": None}
            try:
                if plain not in shared:
                    time.sleep(DELAY_S)
                    shared[plain] = _get(client, plain)
                payload["page"] = parse_page(shared[plain], fragment or None)
            except httpx.HTTPError:
                payload["page"] = (prior.get(sid) or {}).get("page")
            records.append(RawRecord(source_connector=CONNECTOR, source_id=sid, payload=payload))
    return records


# ---------- normalize ----------

def normalize(raw: RawRecord, today: date | None = None) -> Program:
    program, rnd, page = raw.payload["program"], raw.payload.get("round") or {}, raw.payload.get("page") or {}
    today = today or date.today()
    blocks = [tuple(b) for b in page.get("blocks", [])]
    text = " ".join(t for _, t in blocks)
    opens_at, closes_at, deadline = round_dates(rnd.get("lines", []))
    lines = applicant_lines(blocks)
    name = clean(program["title"]) or raw.source_id
    code = program.get("agency_code")
    category = AGENCY_CATEGORIES.get(code or "")
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=program["url"],
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=program.get("agency"),
        agency_code=code,
        funding_type=funding_type_for(name) or "grant",
        funding_source="pass_through" if FEDERAL_RE.search(text) else "direct",
        amount_min=None,
        amount_max=None,
        match_required=True if MATCH_RE.search(text) else None,
        match_pct=None,
        status=status_for(opens_at, closes_at, today),
        opens_at=opens_at,
        closes_at=closes_at,
        closes_at_text=deadline,
        rolling=None,
        summary=first_p(blocks),
        eligibility_text="\n".join(lines) or None,
        eligibility_structured={"one_stop_round": rnd["heading"]} if rnd.get("heading") else None,
        applicant_types=applicant_tags(lines),
        categories=[CategoryTag(value=category, source_code=program["agency"])] if category else [],
        alns=[],
    )
