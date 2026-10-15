"""SAM.gov Assistance Listings connector: the federal program catalog (ALN, formerly CFDA) that sits
underneath Grants.gov notices. One listing == one stable program; a Grants.gov opportunity cites one or
more listings by number, which is how the two connectors join (program_aln.aln == listing source_id).

Endpoints (no auth). Both are what sam.gov's own UI calls and are undocumented; both need
`Accept: application/hal+json` or they answer 406.
  GET https://sam.gov/api/prod/sgs/v1/search/?index=cfda&q=&page=N&size=1000&sort=-modifiedDate&mode=search&is_active=true
  GET https://sam.gov/api/prod/fac/v1/programs/{_id}
Escape hatch if they change: the documented API https://api.sam.gov/assistance-listings/v1/search needs a
personal key from a SAM.gov account (10 requests/day for a plain account; 3 pages of 1000 covers every
active listing and includes code names). Not built: a second payload shape means a second normalizer.

Verified against the live endpoints on 2026-10-15 (see tests/fixtures/sam_assistance_listings):
  - 2,869 active listings, unique by programNumber; 210 numbers are non-standard ('93.00Y', '11.67A'):
    keep them as strings, never parse them.
  - hit fields: _id, programNumber, title, objective (truncated), isActive, modifiedDate, assistanceTypes
    (hierarchy; level-2 code F001 Grant, F002 Cooperative Agreement, F003 Direct Loan, ...), organizationHierarchy
  - detail.data: title, objective (full), eligibility.applicant.{types[ET codes], description},
    assistance.deadlines.{flag, description, list[{start, end, description}]},
    financial.rangeAndAverageAssistance[{fiscalYear, minimumAwardAmount, maximumAwardAmount}],
    compliance.formulaAndMatching.types.{matching, formula, moe}
  - the detail endpoint errors for inactive listings; search with q=<programNumber> finds them.

Status: a listing is a catalog entry, not an opportunity. It does not know whether you can apply today;
the NOFO does. So an active listing is stored with status 'unknown' (second meaning of that value: "no
application window of its own") and an inactive one as 'closed'. That keeps listings out of
v_open_for_municipalities without inventing a window.

fetch(prior=...) refetches a listing's detail only when the search hit's modifiedDate moved, so a cold run
is ~2,900 requests and a warm run is 3. To force a full refetch:
  DELETE FROM raw_record WHERE source_connector = 'sam_assistance_listings';
"""

from __future__ import annotations

import html
import re
import time
from collections.abc import Iterator
from typing import Any

import httpx

from connectors.grants_gov import _clean_text, parse_int
from pipeline.models import ALL_APPLICANT_TYPES, ApplicantTag, Program, RawRecord

CONNECTOR = "sam_assistance_listings"
SEARCH_URL = "https://sam.gov/api/prod/sgs/v1/search/"
DETAIL_URL = "https://sam.gov/api/prod/fac/v1/programs/{id}"
VIEW_URL = "https://sam.gov/fal/{id}/view"

PAGE_SIZE = 1000
LOOKUP_SIZE = 100          # q=<number> is a full-text search: it returns every listing whose text mentions the number
PAGE_DELAY_S = 0.5
DETAIL_DELAY_S = 0.25
TIMEOUT_S = 60.0

# Assistance type (level-2 code on the search hit) -> funding_type. Picked by this priority order when a
# listing carries several, so the hash does not flap on array order.
FUNDING_TYPE_PRIORITY: tuple[tuple[str, str], ...] = (
    ("F001", "grant"), ("F002", "cooperative_agreement"), ("F003", "loan"), ("F004", "loan"),
    ("F005", "other"), ("F006", "other"), ("F007", "other"), ("F008", "other"), ("F009", "other"),
    ("F010", "other"),
)

# SAM.gov eligible applicant entity-type codes -> applicant_type(s). None = not represented in our
# vocabulary (federal, territorial, foreign, "other"); '*' = every applicant type. The raw code is kept in
# program_applicant_type.source_code either way.
APPLICANT_CODES: dict[str, tuple[str, ...] | str | None] = {
    "ET11010": "*",                                   # Unrestricted by Entity Type
    "ET11020": ("individual", "household"),           # Unrestricted by Individual Type
    "ET21010": None,                                  # U.S. Federal Government
    "ET22010": ("state",), "ET22030": ("state",), "ET26020": ("state",),
    "ET22020": None, "ET22040": None, "ET26030": None, # territories
    "ET22050": None,                                  # Interstate Organization
    "ET23010": ("tribe",), "ET23020": ("tribe",), "ET26040": ("tribe",),
    "ET23030": ("housing_authority",),                # Tribally Designated Housing Authority
    "ET24010": ("municipality",),                     # Municipality or Township Government
    "ET24020": ("county",),                           # County Government
    "ET24030": ("school",), "ET24040": ("school",),   # School District (Government)
    "ET24050": ("special_district",),                 # Other Local Government Consortium or Regional Organization
    "ET25010": ("housing_authority",),                # Public Housing Authority
    "ET25020": ("special_district",), "ET25030": ("special_district",), "ET25040": ("special_district",),
    "ET25050": ("special_district",), "ET25060": ("special_district",), "ET25070": ("special_district",),
    "ET26010": ("municipality", "county"),            # "Local"
    "ET31010": None, "ET32010": None, "ET32020": None, "ET32030": None, "ET33010": None,  # foreign / intl
    "ET41010": ("nonprofit",), "ET41020": ("nonprofit",),
    "ET41030": ("business",), "ET51060": ("business",), "ET51120": ("business",),
    "ET51100": ("individual",), "ET59020": ("individual",),
    "ET59060": ("individual",), "ET59070": ("individual",), "ET59080": ("individual",),
    "ET59010": ("household",),                        # Homeowner
    "ET59999": None,                                  # Other
}


# ---------- HTTP ----------

def search_params(page: int = 0, size: int = PAGE_SIZE, q: str = "", active: bool | None = True) -> dict[str, Any]:
    params: dict[str, Any] = {
        "index": "cfda", "q": q, "page": page, "size": size, "sort": "-modifiedDate", "mode": "search",
    }
    if active is not None:
        params["is_active"] = "true" if active else "false"
    return params


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=TIMEOUT_S,
        headers={
            "User-Agent": "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)",
            "Accept": "application/hal+json",
        },
    )


def _get(client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    r = client.get(url, params=params)
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, dict) or payload.get("errorCode") or payload.get("error"):
        raise RuntimeError(f"sam.gov error at {url}: {str(payload)[:200]}")
    return payload


def iter_hits(client: httpx.Client, limit: int | None = None) -> Iterator[dict[str, Any]]:
    """Walk active-listing search pages. Dedupes by programNumber in case the sort shifts between pages.
    Any failed page raises: a silently short run would make the pipeline resolve hundreds of 'missing' rows."""
    seen: set[str] = set()
    page = 0
    size = min(PAGE_SIZE, limit) if limit else PAGE_SIZE
    while True:
        payload = _get(client, SEARCH_URL, search_params(page, size))
        results = (payload.get("_embedded") or {}).get("results") or []
        for hit in results:
            pn = str(hit.get("programNumber") or "").strip()
            if not pn or pn in seen:
                continue
            seen.add(pn)
            yield hit
            if limit and len(seen) >= limit:
                return
        total_pages = int((payload.get("page") or {}).get("totalPages") or 0)
        page += 1
        if not results or page >= total_pages:
            return
        time.sleep(PAGE_DELAY_S)


def fetch_detail(client: httpx.Client, listing_id: str) -> dict[str, Any]:
    payload = _get(client, DETAIL_URL.format(id=listing_id))
    if not isinstance(payload.get("data"), dict):
        raise RuntimeError(f"sam.gov detail {listing_id}: no data block")
    return payload


def needs_detail(hit: dict[str, Any], prior_payload: dict[str, Any] | None) -> bool:
    """Refetch unless the stored hit has the same modifiedDate AND the stored detail is usable.
    A failed or empty detail is never frozen in place."""
    if not prior_payload:
        return True
    prior_hit = prior_payload.get("hit") or {}
    prior_detail = prior_payload.get("detail") or {}
    if not isinstance(prior_detail.get("data"), dict) or not prior_detail["data"]:
        return True
    stamp = hit.get("modifiedDate")
    return not stamp or stamp != prior_hit.get("modifiedDate")


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """`prior` maps source_id -> the payload stored in raw_record on the previous run."""
    prior = prior or {}
    out: list[RawRecord] = []
    with _client() as client:
        for hit in iter_hits(client, limit):
            pn = str(hit["programNumber"]).strip()
            previous = prior.get(pn)
            if needs_detail(hit, previous):
                detail = fetch_detail(client, str(hit["_id"]))
                time.sleep(DETAIL_DELAY_S)
            else:
                detail = previous["detail"]  # type: ignore[index]
            out.append(RawRecord(source_connector=CONNECTOR, source_id=pn, payload={"hit": hit, "detail": detail}))
    return out


def lookup(client: httpx.Client, number: str, max_pages: int = 3) -> dict[str, Any] | None:
    """Find one listing (active or not) by its exact program number. The q parameter is a full-text
    search, so filter the results on programNumber rather than trusting rank."""
    for page in range(max_pages):
        payload = _get(client, SEARCH_URL, search_params(page, LOOKUP_SIZE, q=number, active=None))
        results = (payload.get("_embedded") or {}).get("results") or []
        for hit in results:
            if str(hit.get("programNumber") or "").strip() == number:
                return hit
        if len(results) < LOOKUP_SIZE:
            return None
    return None


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A listing that dropped out of the active search: look it up by number without the active filter.
    Inactive -> closed. Still active -> unknown (we just missed it). Not found or error -> None."""
    try:
        with _client() as client:
            hit = lookup(client, source_id)
    except Exception:  # noqa: BLE001
        return None
    return classify_hit(hit)


def classify_hit(hit: dict[str, Any] | None) -> dict[str, Any] | None:
    if not hit:
        return None
    return {"status": "closed"} if hit.get("isActive") is False else {"status": "unknown"}


# ---------- normalize ----------

_zero_width = re.compile(r"[​‌‍⁠﻿]")


def clean(value: Any) -> str:
    """_clean_text plus the zero-width characters SAM.gov text is full of."""
    return _clean_text(_zero_width.sub("", html.unescape(str(value or ""))))


def _deepest_org(hit: dict[str, Any]) -> dict[str, Any]:
    orgs = [o for o in (hit.get("organizationHierarchy") or []) if isinstance(o, dict)]
    return max(orgs, key=lambda o: int(o.get("level") or 0), default={})


def _assistance_codes(hit: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    for at in hit.get("assistanceTypes") or []:
        for node in at.get("hierarchy") or []:
            if int(node.get("level") or 0) == 2 and node.get("code"):
                codes.append(str(node["code"]))
    return codes


def funding_type_for(codes: list[str]) -> str | None:
    present = set(codes)
    for code, ft in FUNDING_TYPE_PRIORITY:
        if code in present:
            return ft
    return "other" if present else None


def _latest_range(data: dict[str, Any]) -> dict[str, Any]:
    ranges = [r for r in ((data.get("financial") or {}).get("rangeAndAverageAssistance") or []) if isinstance(r, dict)]
    return max(ranges, key=lambda r: parse_int(r.get("fiscalYear")) or -1, default={})


def _deadlines_text(data: dict[str, Any]) -> str | None:
    dl = (data.get("assistance") or {}).get("deadlines") or {}
    parts: list[str] = []
    for item in dl.get("list") or []:
        window = " to ".join(str(x) for x in (item.get("start"), item.get("end")) if x)
        desc = clean(item.get("description"))
        parts.append(": ".join(p for p in (window, desc) if p))
    desc = clean(dl.get("description"))
    if desc:
        parts.append(desc)
    return "; ".join(p for p in parts if p) or None


def normalize(raw: RawRecord) -> Program:
    hit: dict[str, Any] = raw.payload.get("hit") or {}
    detail: dict[str, Any] = raw.payload.get("detail") or {}
    data: dict[str, Any] = detail.get("data") if isinstance(detail.get("data"), dict) else {}
    pn = raw.source_id
    org = _deepest_org(hit)
    elig = data.get("eligibility") or {}
    applicant = elig.get("applicant") or {}
    matching = ((data.get("compliance") or {}).get("formulaAndMatching") or {}).get("types") or {}
    rng = _latest_range(data)

    applicant_types: list[ApplicantTag] = []
    for code in applicant.get("types") or []:
        code = str(code).strip()
        target = APPLICANT_CODES.get(code)
        if target == "*":
            applicant_types += [ApplicantTag(value=t, source_code=code) for t in ALL_APPLICANT_TYPES]
        elif target:
            applicant_types += [ApplicantTag(value=t, source_code=code) for t in target]

    active = hit.get("isActive")
    listing_id = str(hit.get("_id") or data.get("id") or "")

    return Program(
        source_connector=CONNECTOR,
        source_id=pn,
        source_url=VIEW_URL.format(id=listing_id) if listing_id else "https://sam.gov/search/?index=cfda&q=" + pn,
        external_number=pn,
        name=clean(data.get("title") or hit.get("title")),
        level="federal",
        jurisdiction="US",
        administering_agency=clean(org.get("name")) or None,
        agency_code=clean(org.get("code")) or None,
        funding_type=funding_type_for(_assistance_codes(hit)),
        funding_source="direct",
        amount_min=parse_int(rng.get("minimumAwardAmount")),
        amount_max=parse_int(rng.get("maximumAwardAmount")),
        match_required=matching.get("matching") if isinstance(matching.get("matching"), bool) else None,
        match_pct=None,
        status="closed" if active is False else "unknown",
        opens_at=None,
        closes_at=None,
        closes_at_text=_deadlines_text(data),
        rolling=None,
        summary=clean(data.get("objective") or hit.get("objective")) or None,
        eligibility_text=clean(applicant.get("description")) or None,
        eligibility_structured=None,
        applicant_types=applicant_types,
        categories=[],
        alns=[pn],
    )
