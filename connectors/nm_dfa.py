"""New Mexico DFA's Grant Search Dashboard: the funding opportunities New Mexico's own agencies post.

Source: https://platform.dfa.nm.gov/grant-search.html (DFA's CAPS platform, public by its own `js/session.js`). The
grid reads plain JSON from `/api/CAPS/SearchFundingOpportunities`, 200 rows a page at most; with `excludeClosed=1` that
is about 1,430 open rows in 8 requests. Most are copies of Grants.gov (`source: "grants.gov"`), already read by
`grants_gov`, so only the rows the state's agencies post (`source: "agency"`) are kept, less the few whose program page
is on a federal site (`FEDERAL_HOSTS`). A row that leaves the open list is read once through the profile page's own call,
`GetFundingOpportunity`. See docs/connectors/nm_dfa.md.
"""

from __future__ import annotations

import json
import time
from datetime import date
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from connectors.grants_gov import parse_date
from connectors.hand_list import client as _client
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for, portal_applicant, portal_categories
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "nm_dfa"
API = "https://platform.dfa.nm.gov/api/CAPS"
LIST_URL = API + "/SearchFundingOpportunities?page={page}&pageSize={size}&sortField=lastUpdatedDate&sortDir=desc&excludeClosed=1"
ONE_URL = API + "/GetFundingOpportunity?fundingOpportunityId={id}"
PROFILE_URL = "https://platform.dfa.nm.gov/grant-profile.html?grantId={id}"
PAGE_SIZE = 200          # the API's cap
MAX_PAGES = 20           # 4,000 rows; the open list held 1,428 on 2026-11-20
DELAY_S = 3.0            # the survey's pace; 8 list requests a run
JURISDICTION = "NM"
# Rows whose program page is on a federal site are federal programs the dashboard lists for New Mexico (USDA Rural
# Development, NRCS, the Southwest Border Region Commission): left out, or the state page would call them state
# programs (decision 2026-11-20, one line to overrule).
FEDERAL_HOSTS = ("usda.gov", "sbrc.gov")
# People's names, e-mails and phones and staff ids: never saved, since atlas.db is published.
DROP = frozenset({"programOfficerName", "programOfficerEmail", "programOfficerPhone", "createdBy", "updatedBy",
                  "featuredByUserId", "favoriteCount", "viewCount"})
# Mail-campaign and analytics parameters some agency links carry (EDD's Targeted Federal Match link has Mailchimp's
# `mc_eid`, which identifies one subscriber): dropped from the stored link, the rest of the address kept.
TRACKING = ("mc_cid", "mc_eid", "utm_", "fbclid", "gclid")
INSTRUMENTS = {"grant": "grant", "loan": "loan", "cooperative agreement": "cooperative_agreement", "other": "other"}


# ---------- HTTP ----------

def _json(client: httpx.Client, url: str) -> Any:
    r = client.get(url)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "ok":
        raise ValueError(f"{url}: status {body.get('status')!r}")
    return body.get("data")


def kept(row: dict[str, Any]) -> bool:
    """A row a New Mexico agency posted, whose program page is not on a federal site."""
    if row.get("source") != "agency" or str(row.get("deleted") or 0) not in ("0", "False", "false"):
        return False
    host = (urlparse(row.get("announcementUrl") or "").hostname or "").lower()
    return not any(host == h or host.endswith("." + h) for h in FEDERAL_HOSTS)


def scrub(row: dict[str, Any]) -> dict[str, Any]:
    """The row as it is saved (atlas.db is published): no one's contact details, no tracking parameters in the link."""
    out = {k: v for k, v in row.items() if k not in DROP}
    if out.get("announcementUrl"):
        out["announcementUrl"] = clean_url(str(out["announcementUrl"]))
    return out


def fetch_open(client: httpx.Client) -> list[dict[str, Any]]:
    """Every open row, page by page until the total is read. A failure raises: without the list nothing is known."""
    rows: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        data = _json(client, LIST_URL.format(page=page, size=PAGE_SIZE))
        got = data.get("data") or []
        rows += got
        if not got or len(rows) >= int(data.get("total") or 0):
            break
        time.sleep(DELAY_S)
    return rows


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """`prior` is accepted for interface parity and ignored: the open list is the whole read."""
    with _client() as client:
        rows = [scrub(r) for r in fetch_open(client) if kept(r)]
    if limit:
        rows = rows[:limit]
    return [RawRecord(source_connector=CONNECTOR, source_id=str(r["fundingOpportunityId"]), payload=r) for r in rows]


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A row that left the open list: its own record, read once. Found -> the usual rules on its dates; gone -> unknown
    (leaving the list is not a closure the source stated); unreachable -> None."""
    try:
        with _client() as client:
            row = _json(client, ONE_URL.format(id=source_id))
    except Exception:  # noqa: BLE001
        return None
    if not row or str(row.get("deleted") or 0) not in ("0", "False", "false"):
        return {"status": "unknown"}
    fields = status_fields(row, date.today())
    return {"status": fields["status"], "closes_at": fields["closes_at"]}


# ---------- normalize ----------

def clean_url(url: str) -> str:
    parts = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith(TRACKING)]
    return urlunparse(parts._replace(query=urlencode(query)))


def labels(row: dict[str, Any]) -> list[str]:
    """The applicant labels, a JSON string list in the source."""
    raw = row.get("eligibleApplicants")
    try:
        got = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except json.JSONDecodeError:
        got = [raw]
    return [clean(str(x)) for x in got if clean(str(x))]


def status_fields(row: dict[str, Any], today: date) -> dict[str, Any]:
    """What the source says, in order: a close date (open until it passes), Forecasted, rolling; else unknown."""
    closes = parse_date(row.get("closeDate"))
    rolling = str(row.get("isRollingOpportunity") or 0) in ("1", "True", "true")
    if closes:
        status = "open" if closes >= today else "closed"
    elif clean(row.get("closeDateDescription")).lower() == "forecasted":
        status = "forecasted"
    elif rolling:
        status = "open"
    else:
        status = "unknown"
    return {"status": status, "closes_at": closes, "rolling": True if rolling else None}


def applicant_tags(row: dict[str, Any]) -> list[ApplicantTag]:
    """Labels the portal table knows map directly; the rest, and the free-text line, go through the shared tagger.
    One tag per applicant type."""
    tags = [ApplicantTag(value=portal_applicant(lab), source_code=lab) for lab in labels(row) if portal_applicant(lab)]
    rest = [lab for lab in labels(row) if not portal_applicant(lab)] + [clean(row.get("eligibleApplicantsOther"))]
    tags += applicant_types_for([line for line in rest if line] or None)
    out: dict[str, ApplicantTag] = {}
    for tag in tags:
        out.setdefault(tag.value, tag)
    return list(out.values())


def category_tags(row: dict[str, Any]) -> list[CategoryTag]:
    out: dict[str, CategoryTag] = {}
    for label in row.get("fundingActivityCategoryNames") or []:
        for value in portal_categories(clean(label)):
            out.setdefault(value, CategoryTag(value=value, source_code=clean(label)))
    return list(out.values())


def funding_type(row: dict[str, Any], name: str) -> str:
    for instrument in row.get("fundingInstrumentTypes") or []:
        if INSTRUMENTS.get(clean(instrument).lower()):
            return INSTRUMENTS[clean(instrument).lower()]
    return funding_type_for(name) or "grant"


def amount(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    row = raw.payload
    today = today or date.today()
    status = status_fields(row, today)
    name = clean(row.get("opportunityTitle")) or raw.source_id
    sharing = clean(row.get("costSharingRequired")).lower()
    structured = {
        "eligible_applicants": labels(row) or None,
        "geography": clean(row.get("geographicRestrictionDisplay")) or None,
        "estimated_total_funding": amount(row.get("estimatedTotalFunding")),
        "expected_award_count": row.get("expectedAwardCount") or None,
    }
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=clean_url(clean(row.get("announcementUrl"))) or PROFILE_URL.format(id=raw.source_id),
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=clean(row.get("agencyName")) or clean(row.get("sourceAgencyName")) or None,
        agency_code=None,
        funding_type=funding_type(row, name),
        funding_source="pass_through" if clean(row.get("fundingSource")).lower() == "federal" else "direct",
        amount_min=amount(row.get("awardFloor")),
        amount_max=amount(row.get("awardCeiling")),
        match_required=True if sharing == "yes" else False if sharing == "no" else None,
        match_pct=None,
        status=status["status"],
        opens_at=None,
        closes_at=status["closes_at"],
        closes_at_text=clean(row.get("closeDateDescription")) or None,
        rolling=status["rolling"],
        summary=clean(row.get("description")) or None,
        eligibility_text=clean(row.get("eligibleApplicantsOther")) or ", ".join(labels(row)) or None,
        eligibility_structured={k: v for k, v in structured.items() if v} or None,
        applicant_types=applicant_tags(row),
        categories=category_tags(row),
        alns=[],
    )
