"""Grants.gov connector: federal direct opportunities open to local governments.

Endpoints (no auth):
  POST https://api.grants.gov/v1/api/search2          list, paginated
  POST https://api.grants.gov/v1/api/fetchOpportunity detail, one per opportunity

fetch() returns one RawRecord per opportunity with payload {"hit": <search2 hit>, "detail": <fetchOpportunity data>}.

Verified against the live API on 2026-10-15 (see tests/fixtures/grants_gov):
  - hit fields: id, number, title, agencyCode, agency, openDate, closeDate (MM/DD/YYYY), oppStatus, docType, cfdaList
  - detail.data has `synopsis` (posted) and/or `forecast` (forecasted); synopsis wins when both exist
  - detail dates look like "Oct 11, 2029 12:00:00 AM EDT"; awardCeiling/awardFloor may be the string "none"
normalize() maps that payload onto Program. Nothing here is clever on purpose.
"""

from __future__ import annotations

import html
import re
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from typing import Any

import httpx

from pipeline.models import ALL_APPLICANT_TYPES, ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "grants_gov"
SEARCH_URL = "https://api.grants.gov/v1/api/search2"
FETCH_URL = "https://api.grants.gov/v1/api/fetchOpportunity"
DETAIL_URL = "https://www.grants.gov/search-results-detail/{id}"

# 01 County governments, 02 City or township governments, 99 Unrestricted.
ELIGIBILITIES = "01|02|99"
OPP_STATUSES = "forecasted|posted"
ROWS = 100
PAGE_DELAY_S = 0.5
DETAIL_DELAY_S = 0.25
TIMEOUT_S = 30.0

STATUS_MAP = {"posted": "open", "forecasted": "forecasted", "closed": "closed", "archived": "closed"}

# Grants.gov applicant eligibility codes -> applicant_type. 25 ("Others") has no structured meaning;
# its explanation lives in eligibility_text. 99 expands to every applicant type.
APPLICANT_CODES: dict[str, str | None] = {
    "00": "state", "01": "county", "02": "municipality", "04": "special_district", "05": "school",
    "06": "higher_ed", "07": "tribe", "08": "housing_authority", "11": "tribe", "12": "nonprofit",
    "13": "nonprofit", "20": "higher_ed", "21": "individual", "22": "business", "23": "business",
    "25": None, "99": "*",
}

# Grants.gov funding activity category codes -> category. Draft; raw codes are kept in
# program_category.source_code so this can be remapped in SQL later.
CATEGORY_CODES: dict[str, str] = {
    "IIJ": "infrastructure", "CD": "infrastructure", "HO": "housing", "EN": "energy",
    "T": "transportation", "NR": "parks", "ENV": "water", "DPR": "public_safety",
    "LJL": "public_safety", "HL": "health", "ELT": "workforce",
}

INSTRUMENT_CODES: dict[str, str] = {"G": "grant", "CA": "cooperative_agreement", "PC": "other", "O": "other"}


# ---------- HTTP ----------

def search_body(start: int = 0, rows: int = ROWS) -> dict[str, Any]:
    return {
        "keyword": "",
        "oppNum": "",
        "eligibilities": ELIGIBILITIES,
        "agencies": "",
        "oppStatuses": OPP_STATUSES,
        "aln": "",
        "fundingCategories": "",
        "fundingInstruments": "",
        "rows": rows,
        "startRecordNum": start,
        "sortBy": "openDate|desc",
    }


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"})


def _post(client: httpx.Client, url: str, body: dict[str, Any]) -> dict[str, Any]:
    r = client.post(url, json=body)
    r.raise_for_status()
    payload = r.json()
    if payload.get("errorcode", 0) not in (0, None):
        raise RuntimeError(f"grants.gov error {payload.get('errorcode')}: {payload.get('msg')}")
    return payload


def iter_hits(client: httpx.Client, limit: int | None = None) -> Iterator[dict[str, Any]]:
    """Walk search2 pages. Dedupes by id in case the sort shifts between pages."""
    seen: set[str] = set()
    start = 0
    rows = min(ROWS, limit) if limit else ROWS
    while True:
        data = _post(client, SEARCH_URL, search_body(start, rows))["data"]
        hits = data.get("oppHits") or []
        for h in hits:
            hid = str(h["id"])
            if hid in seen:
                continue
            seen.add(hid)
            yield h
            if limit and len(seen) >= limit:
                return
        start += len(hits)
        if not hits or start >= int(data.get("hitCount") or 0):
            return
        time.sleep(PAGE_DELAY_S)


def fetch_detail(client: httpx.Client, opportunity_id: str) -> dict[str, Any]:
    return _post(client, FETCH_URL, {"opportunityId": int(opportunity_id)})["data"]


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """`prior` (last stored payloads) is accepted for interface parity and ignored: Grants.gov gives no
    per-record change stamp on the search hit, so every detail is refetched."""
    out: list[RawRecord] = []
    with _client() as client:
        for hit in iter_hits(client, limit):
            hid = str(hit["id"])
            detail = fetch_detail(client, hid)
            out.append(RawRecord(source_connector=CONNECTOR, source_id=hid, payload={"hit": hit, "detail": detail}))
            time.sleep(DETAIL_DELAY_S)
    return out


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """Called for programs that stopped appearing in search results. Reads the detail record and
    derives status from its dates. None (fetch failed) means the caller marks it 'unknown'."""
    try:
        with _client() as client:
            detail = fetch_detail(client, source_id)
    except Exception:  # noqa: BLE001
        return None
    syn = _synopsis(detail)
    closes = parse_date(syn.get("responseDate")) or parse_date(syn.get("estApplicationResponseDate"))
    archive = parse_date(syn.get("archiveDate"))
    today = date.today()
    if (closes and closes < today) or (archive and archive < today):
        return {"status": "closed", "closes_at": closes}
    return {"status": "unknown", "closes_at": closes}


# ---------- normalize ----------

def _synopsis(detail: dict[str, Any]) -> dict[str, Any]:
    data = detail.get("data", detail) if isinstance(detail.get("data"), dict) else detail
    return data.get("synopsis") or data.get("forecast") or {}


def _data(detail: dict[str, Any]) -> dict[str, Any]:
    return detail.get("data", detail) if isinstance(detail.get("data"), dict) else detail


def normalize(raw: RawRecord) -> Program:
    hit: dict[str, Any] = raw.payload.get("hit") or {}
    detail: dict[str, Any] = raw.payload.get("detail") or {}
    data = _data(detail)
    syn = _synopsis(detail)
    source_id = raw.source_id

    applicant_types: list[ApplicantTag] = []
    for item in syn.get("applicantTypes") or []:
        code = str(item.get("id", "")).strip()
        target = APPLICANT_CODES.get(code)
        if target == "*":
            applicant_types += [ApplicantTag(value=t, source_code=code) for t in ALL_APPLICANT_TYPES]
        elif target:
            applicant_types.append(ApplicantTag(value=target, source_code=code))

    categories = [
        CategoryTag(value=CATEGORY_CODES.get(str(item.get("id", "")).strip(), "other"),
                    source_code=str(item.get("id", "")).strip())
        for item in syn.get("fundingActivityCategories") or []
    ]

    instruments = syn.get("fundingInstruments") or []
    funding_type = INSTRUMENT_CODES.get(str(instruments[0].get("id", "")).strip()) if instruments else None

    alns = [str(a) for a in (hit.get("cfdaList") or hit.get("alnist") or [])] or [
        str(c.get("cfdaNumber")) for c in (data.get("cfdas") or []) if c.get("cfdaNumber")
    ]

    return Program(
        source_connector=CONNECTOR,
        source_id=source_id,
        source_url=DETAIL_URL.format(id=source_id),
        external_number=_clean_text(hit.get("number") or data.get("opportunityNumber")) or None,
        name=_clean_text(html.unescape(hit.get("title") or data.get("opportunityTitle") or "")),
        level="federal",
        jurisdiction="US",
        administering_agency=syn.get("agencyName") or hit.get("agency"),
        agency_code=syn.get("agencyCode") or hit.get("agencyCode"),
        funding_type=funding_type,
        funding_source="direct",
        amount_min=parse_int(syn.get("awardFloor")),
        amount_max=parse_int(syn.get("awardCeiling")),
        match_required=parse_bool(syn.get("costSharing")),
        match_pct=None,
        status=STATUS_MAP.get(str(hit.get("oppStatus", "")).lower(), "unknown"),
        opens_at=parse_date(hit.get("openDate")) or parse_date(syn.get("postingDate"))
        or parse_date(syn.get("estSynopsisPostingDate")),
        closes_at=parse_date(hit.get("closeDate")) or parse_date(syn.get("responseDate"))
        or parse_date(syn.get("estApplicationResponseDate")),
        closes_at_text=_clean_text(syn.get("responseDateDesc")) or None,
        rolling=None,
        summary=strip_html(syn.get("synopsisDesc") or syn.get("forecastDesc")) or None,
        eligibility_text=strip_html(syn.get("applicantEligibilityDesc")) or None,
        eligibility_structured=None,
        applicant_types=applicant_types,
        categories=categories,
        alns=alns,
    )


# ---------- small parsers ----------

_DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y")
_month_re = re.compile(r"^[A-Za-z]{3,9} \d{1,2}, \d{4}")


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):  # epoch millis
        try:
            return datetime.fromtimestamp(value / 1000, UTC).date()
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        s = s[:10]
    m = _month_re.match(s)
    if m:
        s = m.group(0)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = re.sub(r"[,$\s]", "", str(value))
    return int(s) if re.fullmatch(r"-?\d+", s) else None


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    return None


class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("p", "br", "li", "div", "tr"):
            self.parts.append(" ")


def strip_html(value: Any) -> str:
    if value is None:
        return ""
    s = html.unescape(str(value))
    p = _Stripper()
    p.feed(s)
    return _clean_text("".join(p.parts))


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
