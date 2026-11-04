"""Kentucky Department for Local Government connector: the DLG Portal's opportunity list and one page per opportunity.

Source: https://www.dlgportal.ky.gov/en-US/grants/ (Power Pages). The page fills its grid from its own GET
`/en-US/Services/GetGrantOpportunities/?page=N&applicationStatus=Open|Expired`, which a server-side template answers
with plain JSON; each row's `applandingpage` is a server-rendered page with a banner summary and `h2` sections
(Eligibility Criteria, Required Documentation, Award Details, Application Process). Status is the list a row came
from. See docs/connectors/ky_dlg.md.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date
from typing import Any

import httpx

from connectors.grants_gov import parse_date
from connectors.hand_list import (
    DELAY_S,
    applicant_tags,
    resolve_missing,  # noqa: F401  (the pipeline reads it from this module)
)
from connectors.hand_list import client as _client
from connectors.hand_list import get as _get
from connectors.hand_list import soup as _soup
from connectors.maryland_drupal import sentences
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for
from pipeline.models import Program, RawRecord

CONNECTOR = "ky_dlg"
BASE = "https://www.dlgportal.ky.gov/en-US"
LIST_URL = BASE + "/Services/GetGrantOpportunities/"
AGENCY = "Kentucky Department for Local Government"
AGENCY_CODE = "KY-DLG"
JURISDICTION = "KY"
LISTS = {"Open": "open", "Expired": "closed"}
SECTIONS = {
    "eligibility criteria": "eligibility",
    "required documentation": "required_documentation",
    "award details": "award_details",
    "application process": "application_process",
}
# A banner sentence that names who receives the money (RDAAP: "a system of grants to Special Purpose Governmental
# Entities ... and in partnership with county governments"); the rest of a banner says what the money is for.
RECIPIENT_RE = re.compile(r"\b(?:grants? to(?! be\b)|eligible|applicants?)\b", re.I)
# A bullet or a starred heading ("***ONE MAIN REQUIREMENT***") ends a line: LMPP's applicant list runs straight into
# its requirements, and one "will not fund" there would otherwise drop the whole list as a negation.
BREAK_RE = re.compile(r"\s*(?:•|\*{3}[^*]*\*{3})\s*")
# A program's own name before its acronym ("The Local Government Economic Development Fund (LGEDF)") names no
# applicant; it is removed before the tagger reads the line.
NAME_RE = re.compile(r"\b[A-Z][\w-]*(?:\s+(?:of\s+|and\s+)?[A-Z][\w-]*)+\s*\((?=[A-Z]{2,}\))[A-Z]+\)")
MAX_PAGES = 20


# ---------- parsing (no I/O) ----------

def parse_list(text: str) -> dict[str, Any]:
    """The template's JSON (it prints blank lines first): rows and whether another page follows."""
    data = json.loads(text.strip())
    rows = [{k: clean(str(v or "")) for k, v in row.items()} for row in data.get("results") or []]
    return {"rows": rows, "more": bool(data.get("moreRecords"))}


def parse_page(page_html: str) -> dict[str, Any]:
    """Title, banner summary and the body's sections by heading."""
    soup = _soup(page_html)
    main = soup.find("main") or soup
    title_el = main.find("h1")
    banner = main.find(class_="banner")
    summary_el = banner.find(class_="override-rich-text") if banner else None
    sections: dict[str, str] = {}
    # Each body section is an `.override-rich-text` block after a heading whose label sits in `.xrm-attribute-value`.
    # The portal's template leaves its last `h2` unclosed (`<h2>...<h2>`), so the last block ends up inside the
    # heading; the label is read from the nearest label element before the block, never from the `h2`'s text.
    body_root = main.find(class_="body-content") or main
    for body in body_root.find_all(class_="override-rich-text"):
        label = body.find_previous(class_="xrm-attribute-value")
        key = SECTIONS.get(clean(label.get_text(" ")).lower()) if label else None
        if key and key not in sections:
            for style in body.find_all("style"):
                style.decompose()
            sections[key] = clean(body.get_text(" "))
    return {
        "title": clean(title_el.get_text(" ")) if title_el else None,
        "summary": clean(summary_el.get_text(" ")) if summary_el else None,
        "sections": sections,
    }


def page_url(row: dict[str, str]) -> str:
    path = row.get("applandingpage") or row.get("programlandingpage") or ""
    return BASE + path if path.startswith("/") else BASE + "/" + path


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """Both lists (a failure raises: without them nothing is known), then one page per row. A page that fails keeps
    the stored page."""
    prior = prior or {}
    records: list[RawRecord] = []
    seen: set[str] = set()
    with _client() as client:
        listed: list[tuple[str, dict[str, str]]] = []
        for label in LISTS:
            for n in range(1, MAX_PAGES + 1):
                got = parse_list(_get(client, f"{LIST_URL}?page={n}&applicationStatus={label}"))
                listed += [(label, row) for row in got["rows"]]
                if not got["more"]:
                    break
                time.sleep(DELAY_S)
        for label, row in listed:
            sid = row.get("shortname") or row.get("name")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            payload: dict[str, Any] = {"row": row, "list": label, "page": None}
            try:
                time.sleep(DELAY_S)
                payload["page"] = parse_page(_get(client, page_url(row)))
            except httpx.HTTPError:
                payload["page"] = (prior.get(sid) or {}).get("page")
            records.append(RawRecord(source_connector=CONNECTOR, source_id=sid, payload=payload))
            if limit and len(records) >= limit:
                break
    return records


# ---------- normalize ----------

def applicant_lines(page: dict[str, Any]) -> list[str]:
    """The Eligibility Criteria section split at bullets, plus the banner sentences that name a recipient; program
    names with their acronyms removed."""
    eligibility = (page.get("sections") or {}).get("eligibility") or ""
    lines = [part for part in BREAK_RE.split(eligibility) if part.strip()]
    lines += [s for s in sentences(page.get("summary") or "") if RECIPIENT_RE.search(s)]
    return [clean(NAME_RE.sub(" ", line)) for line in lines]


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    row, page = raw.payload["row"], raw.payload.get("page") or {}
    sections = page.get("sections") or {}
    name = page.get("title") or row.get("name") or raw.source_id
    structured = {k: v for k, v in sections.items() if k != "eligibility" and v}
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=page_url(row),
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(name) or "grant",
        funding_source="direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status=LISTS.get(raw.payload.get("list"), "unknown"),
        opens_at=parse_date(row.get("startdate", "").split(" ")[0]),
        closes_at=parse_date(row.get("enddate", "").split(" ")[0]),
        closes_at_text=None,
        rolling=None,
        summary=page.get("summary") or None,
        eligibility_text=sections.get("eligibility") or None,
        eligibility_structured=structured or None,
        applicant_types=applicant_tags(applicant_lines(page)),
        categories=[],
        alns=[],
    )
