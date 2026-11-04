"""Washington seed list: the State Treasurer's Washington Fund Directory, one record per program.

Source: https://tre.wa.gov/financing-and-debt/other-programs/washington-fund-directory (Drupal 10). The landing page
is six topic cards (Education; Emergency Management; Environment, Water, & Energy; Housing, Infrastructure, &
Economic Development; Recreation, Culture, & Social Services; Transportation), each a page with one table: Program
(a link to the agency's page), Type of Program, Fund Source (Grant, Loan, Grant/Loan), Agency, Details. A program
is listed under every topic it fits, so the six tables are read into one record per program with every topic kept.
A directory, not a listing: no status, no dates, no eligibility, so every record is `unknown` with the link, the
agency, the fund source and the details kept, and the category from the row's own "Type of Program" label through
the shared table. Seven GETs a run; the agency pages behind the links are never fetched. See
docs/connectors/wa_fund_directory.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any
from urllib.parse import urljoin

from bs4 import Tag

from connectors.hand_list import (
    DELAY_S,
    resolve_missing,  # noqa: F401  (the pipeline reads it from this module)
)
from connectors.hand_list import client as _client
from connectors.hand_list import get as _get
from connectors.hand_list import soup as _soup
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for, portal_categories
from pipeline.models import CategoryTag, Program, RawRecord, slugify

CONNECTOR = "wa_fund_directory"
BASE = "https://tre.wa.gov"
INDEX_URL = BASE + "/financing-and-debt/other-programs/washington-fund-directory"
AGENCY_PREFIX = "WA"
FUND_SOURCES = {"grant": "grant", "loan": "loan", "grant/loan": "grant"}   # Grant/Loan: the grant side, the label is kept
# The directory's agencies by the acronyms the state itself uses; an agency not listed gets its initials.
AGENCY_CODES = {
    "department of commerce": "COM", "dept. of commerce": "COM", "department of ecology": "ECY",
    "recreation and conservation office": "RCO", "department of transportation": "WSDOT", "military department": "MIL",
    "transportation improvement board": "TIB", "county road administration board": "CRAB",
    "office of superintendent of public instruction": "OSPI", "office of the state treasurer": "OST",
    "freight mobility strategic investment board": "FMSIB", "utilities and transportation commission": "UTC",
    "washington state parks & recreation commission": "PARKS", "department of health": "DOH",
    "washington state historical society": "WSHS", "washington trust for historic preservation": "WTHP",
}
FEDERAL_RE = re.compile(r"\bfederal(?:ly)? (?:funds|funding|grant|program|dollars)\b|\bFEMA\b|\bHUD\b|\bEPA\b|\bUSDA\b|\bFHWA\b|\bU\.S\. Department\b", re.I)


# ---------- parsing (no I/O) ----------

def _text(el: Tag) -> str:
    return clean(el.get_text(" "))


def parse_topics(index_html: str) -> list[dict[str, str]]:
    """The topic cards of the landing page: [{name, url}] in page order (links under the directory path only)."""
    doc = _soup(index_html)
    main = doc.find("main") or doc
    out: list[dict[str, str]] = []
    for h in main.find_all("h3"):
        a = h.find("a", href=True)
        if a and "/washington-fund-directory/" in a["href"] and _text(a):
            out.append({"name": _text(a), "url": urljoin(INDEX_URL, a["href"])})
    return out


def parse_topic(topic_html: str, topic: str) -> list[dict[str, Any]]:
    """One dict per row of a topic page's table: program, url, type, fund_source, agency, details, topic."""
    doc = _soup(topic_html)
    main = doc.find("main") or doc
    table = main.find("table")
    rows: list[dict[str, Any]] = []
    for tr in table.find_all("tr") if table else []:
        tds = tr.find_all("td")
        if len(tds) < 5 or not _text(tds[0]):
            continue
        link = tds[0].find("a", href=True)
        rows.append({"program": _text(tds[0]), "url": urljoin(INDEX_URL, link["href"]) if link else None,
                     "type": _text(tds[1]), "fund_source": _text(tds[2]), "agency": _text(tds[3]),
                     "details": _text(tds[4]), "topic": topic})
    return rows


def merge(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per program (the slug of its name), the first row's facts, every topic it is listed under."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        slug = slugify(r["program"])
        rec = out.setdefault(slug, {k: v for k, v in r.items() if k != "topic"} | {"source_id": slug, "topics": []})
        if r["topic"] not in rec["topics"]:
            rec["topics"].append(r["topic"])
    return list(out.values())


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The landing page, then each topic page. Any failure raises and aborts the run: a missing topic would mark
    its programs missing."""
    rows: list[dict[str, Any]] = []
    with _client() as client:
        for _i, topic in enumerate(parse_topics(_get(client, INDEX_URL))):
            time.sleep(DELAY_S)
            rows += parse_topic(_get(client, topic["url"]), topic["name"])
    records = merge(rows)
    records = records[:limit] if limit else records
    return [RawRecord(source_connector=CONNECTOR, source_id=r["source_id"], payload=r) for r in records]


# ---------- normalize ----------

def agency_code_for(agency: str) -> str:
    """`WA-` plus the state's own acronym for the agency (`Department of Commerce` -> `WA-COM`); initials of the
    capitalized words for an agency the table does not know."""
    code = AGENCY_CODES.get(agency.lower()) or "".join(w[0] for w in agency.split() if w[:1].isupper())
    return f"{AGENCY_PREFIX}-{code}" if code else AGENCY_PREFIX


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    row = raw.payload
    name = clean(row.get("program", "")) or raw.source_id
    agency = clean(row.get("agency", "")) or None
    kind = clean(row.get("type", ""))
    fund_source = clean(row.get("fund_source", ""))
    details = clean(row.get("details", "")) or None
    structured = {k: v for k, v in (("type_of_program", kind), ("fund_source", fund_source), ("topics", row.get("topics") or [])) if v}
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=row.get("url") or INDEX_URL,
        external_number=None,
        name=name,
        level="state",
        jurisdiction="WA",
        administering_agency=agency,
        agency_code=agency_code_for(agency) if agency else None,
        funding_type=FUND_SOURCES.get(fund_source.lower()) or funding_type_for(name),
        funding_source="pass_through" if FEDERAL_RE.search(details or "") else "direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status="unknown",
        opens_at=None,
        closes_at=None,
        closes_at_text=None,
        rolling=None,
        summary=details,
        eligibility_text=None,
        eligibility_structured=structured or None,
        applicant_types=[],
        categories=[CategoryTag(value=v, source_code=kind) for v in portal_categories(kind) if v != "other"] if kind else [],
        alns=[],
    )
