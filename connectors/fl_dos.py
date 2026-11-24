"""Florida Department of State grants system connector: the grant program table of DOS Grants (milestone 12.9).

Source: https://www.dosgrants.com/Program, one GET a run. The page is a server-rendered table (a Kendo grid printed as
HTML) of every program the system has taken applications for, grouped by division: name, description, application
period ("6/1/2026 - 7/10/2026"). No login, no script. One record per row, except a row whose description is headed by
two or more bold program names (GPS/SCP), which is one record per name. Left out: a row whose own description says the
program is over ("no longer active", "no longer being accepted"), and the rows in `OUT` (one-time rounds long past, and
programs only a library cooperative or a designated cultural organization applies to). Status is the period against the
run date: forecasted before it, open inside it, `unknown` with the dates kept once it has passed.
See docs/connectors/florida.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import httpx
from bs4 import Tag

from connectors import hand_list as hl
from connectors.grants_gov import parse_date
from connectors.maryland_drupal import sentences
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for, portal_categories
from pipeline.models import CategoryTag, Program, RawRecord

CONNECTOR = "fl_dos"
BASE = "https://www.dosgrants.com"
LIST_URL = BASE + "/Program"
AGENCY = "Florida Department of State"
AGENCY_CODE = "FL-DOS"
JURISDICTION = "FL"
DELAY_S = 3.0   # one GET a run; kept for the probe

# The site's own word that a program is over: the row is not a program any more.
OVER_RE = re.compile(r"\bno longer (?:active|being accepted)\b", re.I)
# Rows left out by name, one line each to overrule (docs/connectors/florida.md, scope):
OUT = frozenset({
    "Albert Network Monitoring Solution Grant",       # no description; one round, ended 3/31/2025
    "Federal Election Security",                      # "non-recurring funds ... for fiscal year 2022-2023"
    "DLIS Florida American Rescue Plan Act (ARPA)",   # one-time federal relief round, 2021
    "DLIS Florida CARES Act.",                        # one-time federal relief round, 2020
    "Library Cooperative Grants",                     # "Eligible applicants are the five Multitype Library Cooperatives"
    "Cultural Endowment",                             # designated Cultural Sponsoring Organizations only
})
PERIOD_RE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})")
DIVISION_RE = re.compile(r"^Division:\s*", re.I)
MORE_INFO_RE = re.compile(r"\s*More information regarding the program is available\s+here\s*\.?", re.I)
# The sentences that say who applies. "Applicants must be associated with an Organization" is about the system's
# account type and names no applicant, so it is not one of them.
APPLICANT_RE = re.compile(r"^eligible applicants (?:are|include)\b", re.I)
# "are federal funds" (LSTA), "from the Federal Grants Trust Fund"; the Division of Historical Resources' "provides state
# and federal funds for historic preservation" is about the division, and those programs are legislative appropriations.
FEDERAL_RE = re.compile(r"\bare federal funds\b|\bFederal Grants Trust Fund\b", re.I)
LABEL_MAX_CHARS = 80
SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    return SLUG_RE.sub("-", name.lower()).strip("-")


def parts_of(cell: Tag) -> list[tuple[str | None, str, list[str]]]:
    """(bold name or None, text, links) for a description cell: one part, or one per bold heading when the cell has two
    or more (GPS/SCP)."""
    heads = [b for b in cell.find_all(["b", "strong"]) if 0 < len(clean(b.get_text(" "))) <= LABEL_MAX_CHARS]
    if len(heads) < 2:
        return [(None, clean(cell.get_text(" ")), [a["href"] for a in cell.find_all("a", href=True)])]
    out: list[tuple[str | None, str, list[str]]] = []
    for head in heads:
        text: list[str] = []
        links: list[str] = []
        for sib in head.next_siblings:
            if sib in heads:
                break
            if isinstance(sib, Tag):
                links += [sib["href"]] if sib.name == "a" and sib.get("href") else [a["href"] for a in sib.find_all("a", href=True)]
                text.append(sib.get_text(" "))
            else:
                text.append(str(sib))
        out.append((clean(head.get_text(" ")), clean(" ".join(text)), links))
    return out


def parse_rows(page_html: str) -> list[dict[str, Any]]:
    """Every program in the table, in page order: division, name, description, period, link."""
    table = hl.soup(page_html).find("table")
    rows: list[dict[str, Any]] = []
    division = ""
    for tr in table.find_all("tr") if table else []:
        cells = tr.find_all("td")
        if "k-grouping-row" in (tr.get("class") or []):
            division = DIVISION_RE.sub("", clean(tr.get_text(" ")))
            continue
        if len(cells) < 4:
            continue
        row_name, period = clean(cells[1].get_text(" ")), clean(cells[3].get_text(" "))
        for head, text, links in parts_of(cells[2]):
            rows.append({"division": division, "row": row_name, "name": head or row_name,
                         "description": re.sub(r"\s+([.,])", r"\1", text), "period": period,
                         "link": links[0] if links else None})
    return rows


def kept(row: dict[str, Any]) -> bool:
    return bool(row["name"]) and row["row"] not in OUT and not OVER_RE.search(row["description"])


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The table, one GET. When it cannot be read, the stored records stand in."""
    try:
        with hl.client() as client:
            rows = [r for r in parse_rows(hl.get(client, LIST_URL)) if kept(r)]
    except httpx.HTTPError:
        return [RawRecord(source_connector=CONNECTOR, source_id=sid, payload=p) for sid, p in (prior or {}).items()]
    records = [RawRecord(source_connector=CONNECTOR, source_id=slug(r["name"]), payload=r) for r in rows]
    return records[:limit] if limit else records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A row that left the table: unknown, no request (the table is the whole source)."""
    return {"status": "unknown"}


def status_fields(period: str, today: date) -> dict[str, Any]:
    m = PERIOD_RE.search(period or "")
    opens, closes = (parse_date(m.group(1)), parse_date(m.group(2))) if m else (None, None)
    if not (opens and closes):
        status = "unknown"
    elif today < opens:
        status = "forecasted"
    elif today <= closes:
        status = "open"
    else:
        status = "unknown"   # a past round: the dates are kept, the next round is not stated
    return {"status": status, "opens_at": opens, "closes_at": closes,
            "closes_at_text": f"Application Period: {clean(period)}" if m else None}


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    row = raw.payload
    name = clean(row.get("name")) or raw.source_id
    description = clean(row.get("description"))
    lines = [s for s in sentences(description) if APPLICANT_RE.search(s)]
    division = clean(row.get("division"))
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=LIST_URL,
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(name) or "grant",
        funding_source="pass_through" if FEDERAL_RE.search(description) else "direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        rolling=None,
        summary=clean(MORE_INFO_RE.sub("", description)) or None,
        eligibility_text="\n".join(lines) or None,
        eligibility_structured={"division": division, "more_information": row.get("link")} if division or row.get("link") else None,
        applicant_types=hl.applicant_tags(lines),
        categories=[CategoryTag(value=v, source_code=division) for v in portal_categories(division)] if division else [],
        alns=[],
        **status_fields(row.get("period") or "", today or date.today()),
    )
