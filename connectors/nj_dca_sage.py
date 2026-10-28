"""New Jersey Department of Community Affairs SAGE connector: the RFPs DCA lists publicly.

Source: https://dcasage.intelligrants.com/RFPMailingRequest_List.asp ("Available RFPs", no registration). One classic-ASP
page, ten RFPs on 2026-10-28, every value in a `<span id="<field>_<n>_text">` where `n` is the RFP's position on the page.
Titles and divisions are `RFPCategoryName` labels in document order. There is no ID, so the slug of the title is the key.
The other SAGE instance (njsage.intelligrants.com) is login-only. The program contact is dropped before the payload is
stored. See docs/connectors/nj_dca_sage.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for
from pipeline.models import ApplicantTag, Program, RawRecord, slugify

CONNECTOR = "nj_dca_sage"
LIST_URL = "https://dcasage.intelligrants.com/RFPMailingRequest_List.asp"
AGENCY = "Department of Community Affairs"
AGENCY_CODE = "NJ-DCA"
JURISDICTION = "NJ"
TIMEOUT_S = 30.0
TRIES = 3
RETRY_WAIT_S = 1.5
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

INSTRUCTION_TEXT = "Request more information about available RFPs"
DEADLINE_LABEL = "Deadline for Submission"
FIELD_ID_RE = re.compile(r"^(\w+)_(\d+)_text$")
DIVISION_BG = "#C3D3D3"
# The program contact (a named staff member). Left out of the stored payload: the database is published.
CONTACT_FIELDS = {"ProgramContact", "ProgramContactPhone"}


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def _get(client: httpx.Client, url: str) -> str:
    """The page text. A dropped connection is retried; an HTTP error status is not."""
    for attempt in range(TRIES):
        try:
            resp = client.get(url)
        except httpx.TransportError:
            if attempt == TRIES - 1:
                raise
            time.sleep(RETRY_WAIT_S)
            continue
        resp.raise_for_status()
        return resp.text
    raise AssertionError("unreachable")


# ---------- parsing (no I/O) ----------

def parse_page(page_html: str) -> tuple[list[dict[str, Any]], int]:
    """(rfps, expected): one dict per RFP in page order (`division`, `title`, `fields`: field name -> text, contact left
    out), and the number of "Deadline for Submission" labels, which the RFP count must equal."""
    soup = BeautifulSoup(page_html, "html.parser")
    division = title = ""
    rfps: dict[int, dict[str, Any]] = {}
    for el in soup.find_all(["label", "span"]):
        if el.name == "label" and "RFPCategoryName" in (el.get("class") or []):
            cell = el.find_parent("td")
            if cell is not None and (cell.get("bgcolor") or "").upper() == DIVISION_BG:
                division = clean(el.get_text(" "))
            else:
                title = clean(el.get_text(" "))
            continue
        m = FIELD_ID_RE.match(el.get("id") or "") if el.name == "span" else None
        if m is None or m.group(1) in CONTACT_FIELDS:
            continue
        rfp = rfps.setdefault(int(m.group(2)), {"division": division, "title": title, "fields": {}})
        rfp["fields"][m.group(1)] = clean(el.get_text(" "))
    expected = sum(1 for label in soup.find_all("label") if DEADLINE_LABEL in label.get_text())
    return list(rfps.values()), expected


def unique_slugs(titles: list[str]) -> list[str]:
    """The slug of each title; a repeat gets -2, -3 (titles carry the year and are unique today)."""
    seen: dict[str, int] = {}
    out = []
    for title in titles:
        slug = slugify(title)
        seen[slug] = seen.get(slug, 0) + 1
        out.append(slug if seen[slug] == 1 else f"{slug}-{seen[slug]}")
    return out


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The one page. The run aborts when the parser and the page disagree (the RFP count must equal the number of
    deadline labels; an empty list must still carry the page's instruction text), so an error page or a changed
    layout fails loudly instead of marking every RFP missing."""
    with _client() as client:
        page = _get(client, LIST_URL)
    rfps, expected = parse_page(page)
    if len(rfps) != expected:
        raise ValueError(f"found {len(rfps)} RFPs but {expected} deadline labels: the page layout changed")
    if not rfps and INSTRUCTION_TEXT not in page:
        raise ValueError("no RFPs and no instruction text: not the RFP list page")
    records = [RawRecord(source_connector=CONNECTOR, source_id=slug, payload=rfp)
               for slug, rfp in zip(unique_slugs([r["title"] for r in rfps]), rfps, strict=True)]
    return records[:limit] if limit else records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """An RFP that left the page. One page and nothing behind it to read back; leaving is not a closure the source
    states: unknown."""
    return {"status": "unknown"}


# ---------- normalize ----------

def money(text: str) -> int | None:
    m = re.fullmatch(r"\$?\s*([\d,]+(?:\.\d+)?)", clean(text))
    return int(float(m.group(1).replace(",", ""))) if m else None


def status_for(due: date | None, today: date) -> str:
    return "closed" if due and due < today else "open"


def funding_type_of(title: str) -> str | None:
    """The shared title rule, except a tax credit: a "Tax Credit Planning" RFP is a planning grant named for the program
    it supports."""
    found = funding_type_for(title)
    return None if found == "tax_credit" else found


def applicant_tags(eligibility: str) -> list[ApplicantTag]:
    lines = [s for s in sentences(eligibility) if not NEGATION_RE.search(s)]
    return applicant_types_for(lines or None)


def structured_for(rfp: dict[str, Any]) -> dict[str, Any] | None:
    f = rfp["fields"]
    out: dict[str, Any] = {}
    if rfp["division"]:
        out["division"] = rfp["division"]
    if f.get("rfpPopulationTargeted"):
        out["population"] = f["rfpPopulationTargeted"]
    if f.get("rfpEstimateTotalRFPFunds"):
        out["total_funds"] = f["rfpEstimateTotalRFPFunds"]
    start, stop = f.get("rfpContractStartDate", ""), f.get("rfpContractStopDate", "")
    if start or stop:
        out["grant_period"] = " - ".join(x for x in (start, stop) if x)
    return out or None


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    rfp = raw.payload
    f = rfp["fields"]
    today = today or date.today()
    due = parse_date(f.get("rfpDueDate"))
    division = rfp["division"]
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=LIST_URL,
        external_number=None,
        name=rfp["title"],
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=f"{AGENCY}, {division}" if division else AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_of(rfp["title"]),
        funding_source="direct",
        amount_min=money(f.get("rfpMinimumAwardAmount", "")),
        amount_max=money(f.get("rfpMaximumAwardAmount", "")),
        match_required=None,
        match_pct=None,
        status=status_for(due, today),
        opens_at=None,
        closes_at=due,
        closes_at_text=None,
        rolling=None,
        summary=f.get("rfpDescription") or None,
        eligibility_text=f.get("rfpEligibility") or None,
        eligibility_structured=structured_for(rfp),
        applicant_types=applicant_tags(f.get("rfpEligibility", "")),
        categories=[],
        alns=[],
    )
