"""grants.wv.gov connector: West Virginia's state grants portal, read through its JSON API.

Source: https://grants.wv.gov/grants/Pages/default.aspx (SharePoint) fills its "Funding Opportunities" list from
`POST https://apps.wv.gov/SharePoint/api/search` with siteurl=grants.wv.gov, listname=AvailableGrants and an
OData-style query; an empty query returns the whole list (124 items on 2026-10-17). One request per run, no HTML.

The page defines its own statuses: Active is PostedDate <= today <= DueDate1, Forecasted is any item with text in
the Forecasted column. The connector follows the dates, then reads the Forecasted text the way the MEA connector
reads cycle sentences: a month, season or date still ahead is a forecast; a past one is a stale page; wording with
no date ("Annual deadline of April 1st", "Ongoing") is cycle text for closes_at_text. Nothing is written to a date
column from that text. See docs/connectors/wv_grants.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import httpx

from connectors.grants_gov import parse_date, strip_html
from connectors.maryland_drupal import applicant_types_for, funding_type_for
from connectors.sam_assistance_listings import clean
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "wv_grants"
API_URL = "https://apps.wv.gov/SharePoint/api/search"
SITE = "grants.wv.gov"
LIST_NAME = "AvailableGrants"
MAX_ITEMS = 1000
DETAIL_URL = "https://grants.wv.gov/grants/Pages/grantdetails.aspx?grantid={id}"
TIMEOUT_S = 60.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"
JURISDICTION = "WV"

ROLLING_RE = re.compile(r"ongoing|rolling|continuous", re.I)

# Division keyword -> category, first match wins; the division text is the tag's source_code.
CATEGORY_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("homeland security", "public_safety"), ("justice", "public_safety"),
    ("water development", "water"), ("broadband", "broadband"), ("workforce", "workforce"),
    ("dhhr", "health"), ("health", "health"), ("behavioral", "health"), ("family assistance", "health"),
    ("rehabilitation", "health"),
    ("economic development", "infrastructure"), ("community advancement", "infrastructure"),
)

_MONTHS = {m.lower(): i for i, m in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
     "November", "December"), start=1)}
_SEASONS = {"spring": 3, "summer": 6, "fall": 9, "autumn": 9, "winter": 12}
FORECAST_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Spring|Summer|Fall|Autumn|Winter)"
    r"\s+(?:\d{1,2},\s*)?(\d{4})\b",
    re.I,
)


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT})


def api_form(query: str = "") -> dict[str, str]:
    return {"siteurl": SITE, "listname": LIST_NAME, "query": query, "maxItems": str(MAX_ITEMS)}


def fetch_list(client: httpx.Client) -> list[dict[str, Any]]:
    """The whole AvailableGrants list. The API pads `properties` with empty strings; they are dropped."""
    r = client.post(API_URL, data=api_form())
    r.raise_for_status()
    data = r.json()
    return [item for item in (data.get("properties") or []) if isinstance(item, dict) and item.get("Id")]


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """`prior` is accepted for interface parity and ignored: the list is one request."""
    with _client() as client:
        items = fetch_list(client)
    if limit:
        items = items[:limit]
    return [RawRecord(source_connector=CONNECTOR, source_id=str(item["Id"]), payload=item) for item in items]


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """An item that left the list: re-read the list. Still there -> the usual rules; gone -> unknown (leaving the
    list is not a closure the source stated); unreachable -> None."""
    try:
        with _client() as client:
            items = fetch_list(client)
    except Exception:  # noqa: BLE001
        return None
    for item in items:
        if str(item.get("Id")) == str(source_id):
            fields = status_fields(item, date.today())
            return {"status": fields["status"], "closes_at": fields["closes_at"]}
    return {"status": "unknown"}


# ---------- normalize ----------

def forecast_date(text: str) -> date | None:
    """The date a Forecasted text points at, for comparison only: a month or season name plus a year, or a full
    date. None when the text names no date ("Annual deadline of April 1st", "Ongoing")."""
    full = parse_date(text)
    if full:
        return full
    m = FORECAST_RE.search(text or "")
    if not m:
        return None
    word, year = m.group(1).lower(), int(m.group(2))
    month = _MONTHS.get(word) or _SEASONS.get(word)
    return date(year, month, 1) if month else None


def status_fields(item: dict[str, Any], today: date) -> dict[str, Any]:
    opens = parse_date(item.get("PostedDate"))
    closes = parse_date(item.get("DueDate1"))
    forecast = clean(item.get("Forecasted"))
    past_due = closes is not None and closes < today
    if opens and closes and opens <= today <= closes:
        status = "open"
    elif opens and opens > today:
        status = "forecasted"
    elif forecast:
        when = forecast_date(forecast)
        if when and when >= today:
            status = "forecasted"
        else:
            status = "closed" if past_due else "unknown"
    elif past_due:
        status = "closed"
    else:
        status = "unknown"
    return {"status": status, "opens_at": opens, "closes_at": closes}


def important_dates(item: dict[str, Any]) -> str:
    """The labelled milestones, each as `Title: YYYY-MM-DD`; a title without a date is dropped."""
    parts = []
    for n in (1, 2, 3):
        title, when = clean(item.get(f"ImportantDateTitle{n}")), parse_date(item.get(f"ImportantDate{n}"))
        if title and when:
            parts.append(f"{title}: {when.isoformat()}")
    return "; ".join(parts)


def closes_text_for(item: dict[str, Any]) -> str | None:
    return clean(item.get("Forecasted")) or important_dates(item) or None


def funding_source_for(item: dict[str, Any]) -> str:
    return "pass_through" if clean(item.get("TypeOfGrant")).lower() == "pass-through" else "direct"


def category_tags(division: str) -> list[CategoryTag]:
    if not division:
        return []
    low = division.lower()
    value = next((cat for keyword, cat in CATEGORY_KEYWORDS if keyword in low), "other")
    return [CategoryTag(value=value, source_code=division)]


def applicant_tags(item: dict[str, Any]) -> list[ApplicantTag]:
    return applicant_types_for(clean(item.get("EntityEligible")) or None)


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    item = raw.payload
    today = today or date.today()
    status = status_fields(item, today)
    division = clean(item.get("Division"))
    type_of_grant = clean(item.get("TypeOfGrant"))
    name = clean(item.get("Title"))
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=DETAIL_URL.format(id=raw.source_id),
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=division or None,
        agency_code=None,
        funding_type=funding_type_for(name),
        funding_source=funding_source_for(item),
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status=status["status"],
        opens_at=status["opens_at"],
        closes_at=status["closes_at"],
        closes_at_text=closes_text_for(item),
        rolling=True if ROLLING_RE.search(clean(item.get("Forecasted"))) else None,
        summary=clean(item.get("Details")) or strip_html(item.get("FullDetails")) or None,
        eligibility_text=clean(item.get("EntityEligible")) or None,
        eligibility_structured={"type_of_grant": type_of_grant} if type_of_grant else None,
        applicant_types=applicant_tags(item),
        categories=category_tags(division),
        alns=[],
    )
