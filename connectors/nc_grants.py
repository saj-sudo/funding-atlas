"""North Carolina seed list: nc.gov's "Grant Opportunities" table, one record per row.

Source: https://www.nc.gov/your-government/all-nc-state-services/grant-opportunities (Drupal). One table, four
columns (Category, Grant Program with a link to the agency's page, Agency as a code such as DEQ, Description), 86
rows on 2026-11-04. A directory, not a listing: no status, no dates, no eligibility, so every record is `unknown`
with the link, the agency and the description kept, and the category through the shared table. Its value is honest
coverage and the list of agencies a North Carolina session reads first (roadmap 12.4). One GET a run; the agency
pages behind the links are never fetched. See docs/connectors/nc_grants.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urljoin

from bs4 import Tag

from connectors.hand_list import client as _client
from connectors.hand_list import get as _get
from connectors.hand_list import resolve_missing  # noqa: F401  (the pipeline reads it from this module)
from connectors.hand_list import soup as _soup
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for, portal_categories
from pipeline.models import CategoryTag, Program, RawRecord, slugify

CONNECTOR = "nc_grants"
INDEX_URL = "https://www.nc.gov/your-government/all-nc-state-services/grant-opportunities"
JURISDICTION = "NC"
COLUMNS = ("category", "program", "agency", "description")
FEDERAL_RE = re.compile(r"\bfederal(?:ly)? (?:funds|funding|grant|program|dollars)\b|\bHUD\b|\bFEMA\b|\bUSDA\b|\bU\.S\. Department\b", re.I)


# ---------- parsing (no I/O) ----------

def _text(el: Tag) -> str:
    return clean(el.get_text(" "))


def parse_index(index_html: str) -> list[dict[str, Any]]:
    """One dict per program: source_id (the slug of the program name), program (the link text), url, agency (the code
    as written), description, categories (every Category the program is listed under, in page order: the table
    repeats a program once per category). Rows without four cells are skipped."""
    doc = _soup(index_html)
    table = (doc.find("main") or doc).find("table")
    rows: dict[str, dict[str, Any]] = {}
    for tr in table.find_all("tr") if table else []:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        link = tds[1].find("a", href=True)
        program = _text(tds[1])
        if not program:
            continue
        slug = slugify(program)
        row = rows.setdefault(slug, {
            "source_id": slug, "program": program, "url": urljoin(INDEX_URL, link["href"]) if link else INDEX_URL,
            "agency": _text(tds[2]), "description": _text(tds[3]), "categories": [],
        })
        category = _text(tds[0])
        if category and category not in row["categories"]:
            row["categories"].append(category)
    return list(rows.values())


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The one table. A failure raises and aborts the run: without it every row would be marked missing."""
    with _client() as client:
        rows = parse_index(_get(client, INDEX_URL))
    rows = rows[:limit] if limit else rows
    return [RawRecord(source_connector=CONNECTOR, source_id=r["source_id"], payload=r) for r in rows]


# ---------- normalize ----------

def normalize(raw: RawRecord, today: date | None = None) -> Program:
    row = raw.payload
    name = clean(row.get("program", "")) or raw.source_id
    agency = clean(row.get("agency", "")) or None
    labels = [clean(c) for c in row.get("categories", []) if clean(c)]
    description = clean(row.get("description", "")) or None
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=row.get("url") or INDEX_URL,
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=agency,
        agency_code=f"NC-{agency.upper().replace(' ', '-')}" if agency else None,
        funding_type=funding_type_for(name),
        funding_source="pass_through" if FEDERAL_RE.search(description or "") else "direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status="unknown",
        opens_at=None,
        closes_at=None,
        closes_at_text=None,
        rolling=None,
        summary=description,
        eligibility_text=None,
        eligibility_structured={"categories": labels} if labels else None,
        applicant_types=[],
        categories=[CategoryTag(value=v, source_code=label) for label in labels for v in portal_categories(label) if v != "other"],
        alns=[],
    )
