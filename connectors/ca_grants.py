"""California Grants Portal connector: the state's open-data CSV of every grant posted on grants.ca.gov.

Source: dataset `california-grants-portal` on data.ca.gov, resource "California Grants Portal - Updated Daily CSV".
One GET per run (6.6 MB, 2,025 rows on 2026-10-27) through the dataset download path, which 302s to signed object
storage. data.ca.gov's robots.txt disallows /api/, so the resource id is a constant rather than a CKAN lookup.

The portal labels every row active / closed / forecasted and the connector takes the label as is. `Public Agency`
and `Other Legal Entity` tag no applicant type (the pa_grants rule); `ApplicantTypeNotes` goes through the shared
keyword tagger. See docs/connectors/ca_grants.md.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from typing import Any

import httpx

from connectors.grants_gov import parse_date, strip_html
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, portal_applicant, portal_categories
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "ca_grants"
RESOURCE_ID = "111c8c88-21f6-453c-ae2c-b4785a0624f5"
CSV_URL = (
    "https://data.ca.gov/dataset/california-grants-portal/resource/"
    f"{RESOURCE_ID}/download/california-grants-portal-data.csv"
)
TIMEOUT_S = 120.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"
JURISDICTION = "CA"

STATUS_MAP = {"active": "open", "closed": "closed", "forecasted": "forecasted"}
FUNDING_TYPES = {"grant": "grant", "loan": "loan"}

ROLLING_RE = re.compile(r"ongoing|rolling|continuous", re.I)
RANGE_RE = re.compile(r"^between\s+\$?([\d,]+(?:\.\d+)?)\s+and\s+\$?([\d,]+(?:\.\d+)?)$", re.I)
AMOUNT_RE = re.compile(r"^\$?([\d,]+(?:\.\d+)?)$")
PCT_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*%$")

# The rows of the last file read in this process, for resolve_missing.
_last_rows: dict[str, dict[str, str]] | None = None


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def parse_csv(text: str) -> list[dict[str, str]]:
    """Rows keyed by header; the byte-order mark on the first header is dropped, rows without a PortalID too."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿"), newline=""))
    return [row for row in reader if (row.get("PortalID") or "").strip()]


def fetch_rows(client: httpx.Client) -> list[dict[str, str]]:
    global _last_rows
    r = client.get(CSV_URL)
    r.raise_for_status()
    rows = parse_csv(r.content.decode("utf-8-sig"))
    _last_rows = {row["PortalID"].strip(): row for row in rows}
    return rows


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """`prior` is accepted for interface parity and ignored: the file is one request."""
    with _client() as client:
        rows = fetch_rows(client)
    if limit:
        rows = rows[:limit]
    return [RawRecord(source_connector=CONNECTOR, source_id=row["PortalID"].strip(), payload=row) for row in rows]


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A row that left the file. Closed rounds stay in the file, so leaving it is a removal the source did not
    explain: unknown. Still there (a file read since) -> its label. Unreadable -> None."""
    rows = _last_rows
    if rows is None:
        try:
            with _client() as client:
                fetch_rows(client)
        except Exception:  # noqa: BLE001
            return None
        rows = _last_rows or {}
    row = rows.get(str(source_id))
    if row is None:
        return {"status": "unknown"}
    return {"status": STATUS_MAP.get(clean(row.get("Status")).lower(), "unknown"),
            "closes_at": parse_date(row.get("ApplicationDeadline"))}


# ---------- normalize ----------

def _parts(value: Any) -> list[str]:
    return [p for p in (s.strip() for s in clean(value).split(";")) if p]


def _money(text: str) -> int:
    return int(float(text.replace(",", "")))


def amount_fields(value: Any) -> tuple[int | None, int | None]:
    """(amount_min, amount_max) from EstAmounts: a range, or one amount for both; anything else null."""
    text = clean(value)
    m = RANGE_RE.match(text)
    if m:
        return _money(m.group(1)), _money(m.group(2))
    m = AMOUNT_RE.match(text)
    if m:
        return _money(m.group(1)), _money(m.group(1))
    return None, None


def match_fields(value: Any) -> tuple[bool | None, float | None]:
    text = clean(value)
    if text.lower() == "not required":
        return False, None
    m = PCT_RE.match(text)
    return (True, float(m.group(1))) if m else (None, None)


def funding_type_for(value: Any) -> str | None:
    parts = _parts(value)
    return FUNDING_TYPES.get(parts[0].lower()) if parts else None


def funding_source_for(value: Any) -> str:
    return "pass_through" if "federal" in clean(value).lower() else "direct"


def status_for(value: Any) -> str:
    return STATUS_MAP.get(clean(value).lower(), "unknown")


def closes_text_for(row: dict[str, Any]) -> str | None:
    """Deadline text that is not a date, verbatim, and open-date text that is not a date as `Opens: ...`."""
    parts = []
    deadline, opens = clean(row.get("ApplicationDeadline")), clean(row.get("OpenDate"))
    if deadline and not parse_date(deadline):
        parts.append(deadline)
    if opens and not parse_date(opens):
        parts.append(f"Opens: {opens}")
    return "; ".join(parts) or None


def applicant_tags(row: dict[str, Any]) -> list[ApplicantTag]:
    tags: list[ApplicantTag] = []
    for part in _parts(row.get("ApplicantType")):
        value = portal_applicant(part)
        if value and all(t.value != value for t in tags):
            tags.append(ApplicantTag(value=value, source_code=part))
    for tag in applicant_types_for(clean(row.get("ApplicantTypeNotes")) or None):
        if all(t.value != tag.value for t in tags):
            tags.append(tag)
    return tags


def category_tags(row: dict[str, Any]) -> list[CategoryTag]:
    return [CategoryTag(value=value, source_code=part)
            for part in _parts(row.get("Categories")) for value in portal_categories(part)]


def eligibility_text_for(row: dict[str, Any]) -> str | None:
    lines = [
        f"{label}: {clean(row.get(key))}"
        for label, key in (("Applicant type", "ApplicantType"), ("Eligibility", "ApplicantTypeNotes"),
                           ("Geography", "Geography"))
        if clean(row.get(key))
    ]
    return "\n".join(lines) or None


def eligibility_structured_for(row: dict[str, Any]) -> dict[str, Any] | None:
    out: dict[str, Any] = {}
    loi = clean(row.get("LOI")).lower()
    if loi in ("yes", "no"):
        out["loi_required"] = loi == "yes"
    if clean(row.get("FundingMethod")):
        out["funding_method"] = clean(row.get("FundingMethod"))
    return out or None


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    """`today` is accepted for interface parity: the status is the portal's label, not derived from dates."""
    row = raw.payload
    amount_min, amount_max = amount_fields(row.get("EstAmounts"))
    match_required, match_pct = match_fields(row.get("MatchingFunds"))
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=clean(row.get("GrantURL")),
        external_number=clean(row.get("GrantID")) or None,
        name=clean(row.get("Title")),
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=clean(row.get("AgencyDept")) or None,
        agency_code=None,
        funding_type=funding_type_for(row.get("Type")),
        funding_source=funding_source_for(row.get("FundingSource")),
        amount_min=amount_min,
        amount_max=amount_max,
        match_required=match_required,
        match_pct=match_pct,
        status=status_for(row.get("Status")),
        opens_at=parse_date(row.get("OpenDate")),
        closes_at=parse_date(row.get("ApplicationDeadline")),
        closes_at_text=closes_text_for(row),
        rolling=True if ROLLING_RE.search(clean(row.get("ApplicationDeadline"))) else None,
        summary=strip_html(row.get("Purpose")) or strip_html(row.get("Description")) or None,
        eligibility_text=eligibility_text_for(row),
        eligibility_structured=eligibility_structured_for(row),
        applicant_types=applicant_tags(row),
        categories=category_tags(row),
        alns=[],
    )
