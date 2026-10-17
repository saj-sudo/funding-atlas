"""pa.gov grants index connector: Pennsylvania's state-run "Discover State Grants" portal.

Source: https://www.pa.gov/grants, an Adobe Experience Manager site whose grant list is a Coveo search index
(search hub "All Grants", 377 grants from 17 agencies on 2026-10-17). Enumeration is one POST per 100 results to
the Coveo search API with the public search key read from https://www.pa.gov/grants/search at run time (it sits in
the page as data-api-key and rotates on site rebuilds). Each grant has a page at
https://www.pa.gov/grants/search/grant-details/<agency>/<n> that embeds the whole record as HTML-escaped JSON in
`<div id="pageApiData" data-page-api-data="...">`; the connector reads that attribute, never the rendered text.

Status is a labelled field: "Accepting applications" -> open, "Closed" -> closed, and a closed record whose
openDate is still ahead (and not after its closeDate) is forecasted. Dates can be placeholders (2035-12-31,
2999-07-01 on recurring programs and loans) and are kept as stated; `rolling` comes from grantCycle. The Coveo hit
has no trustworthy change stamp, so every detail page is fetched every run (~377 requests, 0.3 s apart).
See docs/connectors/pa_grants.md for the field mapping and the decisions behind it.
"""

from __future__ import annotations

import html
import json
import re
import time
from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx

from connectors.grants_gov import parse_date, parse_int, strip_html
from connectors.maryland_drupal import applicant_types_for
from connectors.sam_assistance_listings import clean
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "pa_grants"
SEARCH_PAGE = "https://www.pa.gov/grants/search"
COVEO_URL = "https://platform.cloud.coveo.com/rest/search/v2"
SEARCH_HUB = "All Grants"
DETAIL_BASE = "https://www.pa.gov/grants/search/grant-details/"
ROWS = 100
PAGE_DELAY_S = 0.5
DETAIL_DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"
JURISDICTION = "PA"

KEY_RE = re.compile(r'data-api-key="([^"]+)"')
PAGE_DATA_RE = re.compile(r'data-page-api-data="([^"]*)"')
SOURCE_ID_RE = re.compile(r"grant-details/([A-Za-z0-9-]+)/(\d+)")

STATUS_MAP = {"accepting applications": "open", "closed": "closed"}

# First `;`-separated token of fundingType, lower-cased -> funding_type. Unmapped text stays null.
FUNDING_TYPES: dict[str, str] = {
    "grant": "grant", "loan": "loan", "loan program": "loan", "tax credit": "tax_credit", "tax refund": "tax_credit",
    "reimbursement": "other", "reimbursement agreement": "other", "disaster reimbursement": "other",
    "fund": "other", "incentitive payment": "other", "incentive payment": "other",
}

# applicantCategory values -> applicant_type. "Public Agency" and "Other Legal Entity" tag nothing on purpose
# (decision 2 in the doc): the free-text applicantType line names the real ones.
APPLICANT_CATEGORIES: dict[str, str] = {
    "municipality": "municipality", "nonprofit": "nonprofit", "school": "school", "business": "business",
    "individual": "individual", "native american tribal organization or government": "tribe",
}

CATEGORIES: dict[str, str] = {
    "transportation": "transportation", "energy": "energy", "environment & water": "water", "housing": "housing",
    "parks & recreation": "parks", "health & human services": "health",
    "employment, labor, & training": "workforce", "law, justice, & legal services": "public_safety",
    "community & economic development": "infrastructure",
}

ROLLING_RE = re.compile(r"continuous|rolling|re-?occurring|revolving", re.I)
MATCH_NONE_RE = re.compile(r"^(?:n/?a|none|no|not applicable)\.?$", re.I)
MATCH_NOT_REQUIRED_RE = re.compile(r"no match|not required|no cost[- ]?shar", re.I)
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")

# Detail-record key -> Coveo hit field that stands in when the detail page could not be read.
HIT_FALLBACKS: dict[str, str] = {
    "title": "copapwppagetitle", "status": "copapwpapplicationstatus", "openDate": "copapwpopendate",
    "closeDate": "copapwpclosedate", "fundingType": "copapwpfundingtype", "fundingSource": "copapwpfundingsource",
    "category": "copapwpcategory", "applicantCategory": "copapwpapplicanttype", "grantCycle": "copapwpgrantcycle",
    "minimumAward": "copapwpminimumaward", "maximumAward": "copapwpmaximumaward",
    "shortDescription": "copapwpshortdescription", "overview": "copapwpoverview",
    "issuingAgency": "copapwpfundingagency",
}


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def read_search_key(page_html: str) -> str:
    """The public Coveo search key from the search page's markup. Missing means the site changed: fail loudly."""
    m = KEY_RE.search(page_html or "")
    if not m:
        raise RuntimeError(f"{SEARCH_PAGE} carries no data-api-key; the Coveo search key cannot be read")
    return m.group(1)


def fetch_search_key(client: httpx.Client) -> str:
    r = client.get(SEARCH_PAGE)
    r.raise_for_status()
    return read_search_key(r.text)


def search_body(first: int = 0, rows: int = ROWS) -> dict[str, Any]:
    return {
        "q": "",
        "searchHub": SEARCH_HUB,
        "numberOfResults": rows,
        "firstResult": first,
        "sortCriteria": "copapwpclosedate ascending",
    }


def source_id_for(url: str | None) -> str | None:
    """`<agency>/<n>` from a grant-details URL, agency lower-cased, number as an integer."""
    m = SOURCE_ID_RE.search(url or "")
    return f"{m.group(1).lower()}/{int(m.group(2))}" if m else None


def detail_url(source_id: str) -> str:
    return DETAIL_BASE + source_id


def hit_fields(result: dict[str, Any]) -> dict[str, Any]:
    """What the payload keeps from a Coveo result: its copapwp* fields and the URL."""
    raw = result.get("raw") or {}
    out = {k: v for k, v in raw.items() if k.startswith("copapwp")}
    out.setdefault("copapwpurl", result.get("clickUri") or result.get("uri") or "")
    return out


def iter_hits(client: httpx.Client, key: str, limit: int | None = None) -> Iterator[dict[str, Any]]:
    """Walk the Coveo pages. Dedupes by source_id in case the sort shifts between pages."""
    seen: set[str] = set()
    first = 0
    rows = min(ROWS, limit) if limit else ROWS
    while True:
        r = client.post(COVEO_URL, json=search_body(first, rows), headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        for result in results:
            hit = hit_fields(result)
            sid = source_id_for(hit.get("copapwpurl"))
            if not sid or sid in seen:
                continue
            seen.add(sid)
            yield hit
            if limit and len(seen) >= limit:
                return
        first += len(results)
        if not results or first >= int(data.get("totalCount") or 0):
            return
        time.sleep(PAGE_DELAY_S)


def parse_detail(page_html: str) -> dict[str, Any] | None:
    """The record JSON embedded in a grant-details page, or None when the page has none."""
    m = PAGE_DATA_RE.search(page_html or "")
    if not m:
        return None
    try:
        data = json.loads(html.unescape(m.group(1)))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def fetch_detail(client: httpx.Client, source_id: str) -> dict[str, Any] | None:
    r = client.get(detail_url(source_id))
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return parse_detail(r.text)


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """`prior` is accepted for interface parity and ignored: the Coveo hit carries no change stamp of the source's,
    so every detail page is read every run."""
    out: list[RawRecord] = []
    with _client() as client:
        key = fetch_search_key(client)
        for hit in iter_hits(client, key, limit):
            sid = source_id_for(hit["copapwpurl"])
            detail = fetch_detail(client, sid) or {}
            out.append(RawRecord(source_connector=CONNECTOR, source_id=sid, payload={"hit": hit, "detail": detail}))
            time.sleep(DETAIL_DELAY_S)
    return out


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A program that left the index: read its page. Readable -> status by the same rules; gone or without a
    record -> unknown (a vanished page is not a closure); unreachable -> None."""
    try:
        with _client() as client:
            detail = fetch_detail(client, source_id)
    except Exception:  # noqa: BLE001
        return None
    if not detail:
        return {"status": "unknown"}
    fields = status_fields(detail, date.today())
    return {"status": fields["status"], "closes_at": fields["closes_at"]}


# ---------- normalize ----------

def _text(value: Any) -> str:
    """Scalar or list -> one clean string (lists joined with '; '); zero-width characters dropped, as on SAM.gov
    (some titles start with one)."""
    if isinstance(value, list):
        return clean("; ".join(str(v) for v in value if v not in (None, "")))
    return clean(value)


def _parts(value: Any) -> list[str]:
    return [p for p in (s.strip() for s in _text(value).split(";")) if p]


def parse_when(value: Any) -> date | None:
    """ISO text, or epoch milliseconds as a number or a digit string (the Coveo hit's shape)."""
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    return parse_date(value)


def record(payload: dict[str, Any]) -> dict[str, Any]:
    """The detail JSON with the hit's fields standing in for anything the page did not give."""
    out: dict[str, Any] = dict(payload.get("detail") or {})
    hit = payload.get("hit") or {}
    for key, hit_key in HIT_FALLBACKS.items():
        if not _text(out.get(key)) and _text(hit.get(hit_key)):
            out[key] = hit[hit_key]
    return out


def status_fields(rec: dict[str, Any], today: date) -> dict[str, Any]:
    opens = parse_when(rec.get("openDate"))
    closes = parse_when(rec.get("closeDate"))
    status = STATUS_MAP.get(_text(rec.get("status")).lower(), "unknown")
    if status == "closed" and opens and opens > today and (closes is None or closes >= opens):
        status = "forecasted"
    return {"status": status, "opens_at": opens, "closes_at": closes}


def funding_type_for(value: Any) -> str | None:
    parts = _parts(value)
    return FUNDING_TYPES.get(parts[0].lower()) if parts else None


def funding_source_for(value: Any) -> str:
    return "pass_through" if "federal" in _text(value).lower() else "direct"


def match_fields(value: Any) -> tuple[bool | None, float | None]:
    """(match_required, match_pct). The percentage is taken only when the text holds exactly one."""
    text = _text(value)
    if not text or MATCH_NONE_RE.match(text):
        return None, None
    if MATCH_NOT_REQUIRED_RE.search(text):
        return False, None
    pcts = PCT_RE.findall(text)
    return True, (float(pcts[0]) if len(pcts) == 1 else None)


def rolling_for(value: Any) -> bool | None:
    return True if ROLLING_RE.search(_text(value)) else None


def applicant_tags(rec: dict[str, Any]) -> list[ApplicantTag]:
    tags: list[ApplicantTag] = []
    for part in _parts(rec.get("applicantCategory")):
        value = APPLICANT_CATEGORIES.get(part.lower())
        if value and all(t.value != value for t in tags):
            tags.append(ApplicantTag(value=value, source_code=part))
    for tag in applicant_types_for(_text(rec.get("applicantType")) or None):
        if all(t.value != tag.value for t in tags):
            tags.append(tag)
    return tags


def category_tags(rec: dict[str, Any]) -> list[CategoryTag]:
    return [CategoryTag(value=CATEGORIES.get(part.lower(), "other"), source_code=part) for part in _parts(rec.get("category"))]


def eligibility_text_for(rec: dict[str, Any]) -> str | None:
    lines = [
        f"{label}: {_text(rec.get(key))}"
        for label, key in (("Eligibility", "eligibility"), ("Applicant type", "applicantType"),
                           ("Population served", "populationServedType"))
        if _text(rec.get(key))
    ]
    return "\n".join(lines) or None


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    rec = record(raw.payload)
    today = today or date.today()
    status = status_fields(rec, today)
    match_required, match_pct = match_fields(rec.get("matchingFundsRequirements"))
    short = _text(rec.get("shortIssuingAgency"))
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=detail_url(raw.source_id),
        external_number=None,
        name=_text(rec.get("title")),
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=_text(rec.get("issuingAgency")) or None,
        agency_code=f"PA-{short.upper()}" if short else None,
        funding_type=funding_type_for(rec.get("fundingType")),
        funding_source=funding_source_for(rec.get("fundingSource")),
        amount_min=parse_int(_text(rec.get("minimumAward"))),
        amount_max=parse_int(_text(rec.get("maximumAward"))),
        match_required=match_required,
        match_pct=match_pct,
        status=status["status"],
        opens_at=status["opens_at"],
        closes_at=status["closes_at"],
        closes_at_text=_text(rec.get("grantCycle")) or None,
        rolling=rolling_for(rec.get("grantCycle")),
        summary=strip_html(rec.get("overview")) or strip_html(rec.get("shortDescription")) or None,
        eligibility_text=eligibility_text_for(rec),
        eligibility_structured=None,
        applicant_types=applicant_tags(rec),
        categories=category_tags(rec),
        alns=[],
    )
