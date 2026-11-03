"""New York SFS Grant Opportunity Portal connector: the state's one public index of agency grant rounds.

Source: the PeopleSoft component `NY_SUPPUB_FL.AUC_RESP_INQ_AUC` on https://esupplier.sfs.ny.gov (public, no login). A
GET answers the search page with the default search already run (Status = Anticipated and Available, 32 rows on
2026-11-03) as server-rendered HTML. Everything after that is the page's own form posted back with `ICAction` naming
the control: a row's title link opens its Grant Abstract, "Return to Search" comes back to the grid (as an XML partial
answer whose CDATA holds the same HTML), and the Search button with Status = Closed lists the closed rounds (227). The
browser's JavaScript only fills three hidden fields; the connector fills them itself. Nothing is executed.

The grid labels every row's status; dates are not consulted. `Governmental Entity` is the portal's one broad label; a
row that carries it also has its Solicitation Profile read sentence by sentence for the governmental applicants it
names (decision 2 in the doc). The contact name and email are dropped before the payload is stored. See
docs/connectors/ny_sfs.md.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for, portal_applicant, portal_categories
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "ny_sfs"
HOST = "https://esupplier.sfs.ny.gov"
COMPONENT = "/fscm/SUPPLIER/ERP/c/NY_SUPPUB_FL.AUC_RESP_INQ_AUC.GBL"
LIST_URL = HOST + "/psc" + COMPONENT          # the content frame: what is read
PORTAL_URL = HOST + "/psp" + COMPONENT        # the framed page the state links: the fallback source_url
JURISDICTION = "NY"
DELAY_S = 0.3
TIMEOUT_S = 30.0
TRIES = 3
RETRY_WAIT_S = 1.5
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

# PeopleSoft actions (the `ICAction` a control submits).
LINK_ACTION = "AUC_NAME_LNK${n}"
RETURN_ACTION = "NY_GG_SRCH_WRK_RETURN_PB"
SEARCH_ACTION = "RESP_INQA_WK_INQ_AUC_GO_PB"
STATUS_FIELD = "NY_AUC_INQ_WRK_NY_GG_PORT_STATUS"
CLOSED = "C"

# The form's constant hidden fields, as the page sends them.
FORM_CONSTANTS: dict[str, str] = {
    "ICType": "Panel", "ICElementNum": "0", "ICModelCancel": "0", "ICXPos": "0", "ICYPos": "0",
    "ResponsetoDiffFrame": "-1", "TargetFrameName": "None", "FacetPath": "None", "ICFocus": "",
    "ICSaveWarningFilter": "0", "ICChanged": "-1", "ICSkipPending": "0", "ICAutoSave": "0", "ICResubmit": "0",
    "ICActionPrompt": "false", "ICTypeAheadID": "", "ICBcDomData": "", "ICPanelName": "", "ICFind": "",
    "ICAddCount": "", "ICAppClsData": "",
}

# Grid cell id prefix -> row key. The row number follows a `$`.
GRID_CELLS: dict[str, str] = {
    "AUC_ID_COL$span": "event_id",
    "NY_AUC_INQ1_WRK_BUSINESS_UNIT": "agency_code",
    "NY_AUC_INQ1_WRK_NY_GG_PORT_STATUS": "status",
    "NY_AUC_INQ1_WRK_FIELDLIST": "eligibility",
    "RESP_INQA1_WK_AUC_DTTM_PREVIEW": "posted",
    "RESP_INQA1_WK_AUC_DTTM_START": "release",
    "RESP_INQA1_WK_AUC_DTTM_FINISH": "due",
}
# Abstract span id -> abstract key. The contact (OPRID and the mailto link) is left out on purpose.
ABSTRACT_SPANS: dict[str, str] = {
    "NY_GG_ABSTRT_VW_AUC_ID": "event_id",
    "NY_GG_ABSTRT_VW_DESCR1": "agency",
    "NY_GG_ABSTRT_VW_AUC_NAME": "name",
    "NY_GG_ABSTRT_VW_DESCRLONG2": "profile",
    "NY_GG_ABSTRT_VW_DATETIMESTRING": "due",
    "NY_GG_ABSTRT_VW_DESCR254": "bidders_conference",
    "NY_GG_ABSTRT_VW_DATE_STRING2": "anticipated_award_date",
    "NY_GG_ABSTRT_VW_STRING_TEXT": "contract_length",
    "NY_GG_ABSTRT_VW_FUNDED_AMT": "total_funding",
    "NY_GG_ABSTRT_VW_DESCRLONG": "letter_of_intent",
    "NY_GG_ABSTRT_VW_DATE_STRING1": "questions_due",
    "NY_GG_ABSTRT_VW_DESCRLONG1": "qa_narrative",
    "NY_GG_ABSTRT_VW_NY_GG_POST_TYPE": "qa_post_type",
    "NY_GG_ABSTRT_VW_DATE_STRING": "qa_post_date",
    "NY_GG_SRCH_WRK_LONGVALUE": "eligibility",
    "NY_GG_SRCH_WRK_DESCRLONG": "service_areas",
}
ANNOUNCEMENT_LABEL = "Announcement Link"
# The portal's broad label, and the kinds of body it can mean. A row with it has its Solicitation Profile read for
# these; a tag of any other kind found there (a beneficiary: "residents", "individuals") is the portal's labels' call.
GOVERNMENTAL_ENTITY = "governmental entity"
GOVERNMENTAL_TYPES = frozenset({"municipality", "county", "state", "school", "special_district", "housing_authority", "higher_ed"})

STATUS_MAP: dict[str, str] = {
    "available": "open",
    "advertised only - not in sfs": "open",
    "anticipated": "forecasted",
    "closed": "closed",
}

# Agency short descriptions as the abstracts gave them on 2026-11-03, for closed rows (which have no abstract) whose
# code did not appear on an open abstract this run. The source's own words; a code not here stays null.
AGENCY_NAMES: dict[str, str] = {
    "AGM01": "AGRICULTURE & MARKETS",
    "CFS01": "Off of Children & Family Serv",
    "DCJ01": "Div of Criminal Justice Serv",
    "DDP01": "St Cncl on Development Dsblty",
    "DEC01": "Dept of Environ Conservation",
    "DOH01": "Department of Health",
    "DOL01": "Department of Labor",
    "OMH01": "Office of Mental Health",
    "PRK01": "Off of Parks, Rec & Hstrc Pres",
    "TDA01": "Off of Temp & Disability Assi",
}

_SID_RE = re.compile(r"name='ICSID'[^>]*value='([^']*)'")
_STATE_INPUT_RE = re.compile(r"name='ICStateNum'[^>]*value='(\d+)'")
_STATE_SCRIPT_RE = re.compile(r"ICStateNum\.value=(\d+)")
_CDATA_RE = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)
_ROW_RE = re.compile(r"^AUC_ID_COL\$span\$(\d+)$")
_WEEKDAY_RE = re.compile(r"^(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,\s*", re.I)


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def _request(client: httpx.Client, method: str, url: str, data: dict[str, str] | None = None) -> str:
    """The answer text. A dropped connection is retried; an HTTP error status is not."""
    for attempt in range(TRIES):
        try:
            resp = client.request(method, url, data=data)
        except httpx.TransportError:
            if attempt == TRIES - 1:
                raise
            time.sleep(RETRY_WAIT_S)
            continue
        resp.raise_for_status()
        return resp.text
    raise AssertionError("unreachable")


def _get(client: httpx.Client) -> str:
    return _request(client, "GET", LIST_URL)


def _post(client: httpx.Client, page: str, action: str, **fields: str) -> str:
    """Submit the page's form with `action` as the clicked control: what `submitAction_win0` does in the browser.
    `page` is the answer the form state is taken from (the previous answer, always)."""
    sid, state = form_state(page)
    data = {**FORM_CONSTANTS, "ICSID": sid, "ICStateNum": state, "ICAction": action, **fields}
    time.sleep(DELAY_S)
    return _request(client, "POST", LIST_URL, data=data)


# ---------- answers (no I/O) ----------

def unwrap(text: str) -> str:
    """A PeopleSoft XML partial answer holds its HTML in CDATA sections; a full page is returned as is."""
    if text.lstrip().startswith("<?xml"):
        return "\n".join(_CDATA_RE.findall(text))
    return text


def form_state(page: str) -> tuple[str, str]:
    """(ICSID, ICStateNum) of an answer, from the hidden inputs of a full page or the onload script of a partial one.
    An answer with neither is not the portal's page (an error page, a changed component) and aborts the run."""
    text = unwrap(page)
    sid = _SID_RE.search(text)
    state = _STATE_INPUT_RE.search(text) or _STATE_SCRIPT_RE.search(text)
    if sid is None or state is None:
        raise RuntimeError("the answer carries no PeopleSoft form state (ICSID / ICStateNum): not the portal's page")
    return sid.group(1), state.group(1)


def _text(el: Tag | None) -> str:
    return clean(el.get_text(" ")) if el is not None else ""


def parse_rows(page: str) -> list[dict[str, Any]]:
    """One dict per grid row in grid order: n, event_id, agency_code, name, linked, status, eligibility, posted,
    release, due. Works on a full page and on an unwrapped partial answer."""
    soup = BeautifulSoup(unwrap(page), "html.parser")
    rows: list[dict[str, Any]] = []
    for id_cell in soup.find_all("span", id=_ROW_RE):
        n = int(_ROW_RE.match(id_cell["id"]).group(1))
        row: dict[str, Any] = {"n": n}
        for prefix, key in GRID_CELLS.items():
            row[key] = _text(soup.find(id=f"{prefix}${n}"))
        link = soup.find("a", id=f"AUC_NAME_LNK${n}")
        row["name"] = _text(link if link is not None else soup.find(id=f"AUC_NAME_LNK$span${n}"))
        row["linked"] = link is not None
        rows.append(row)
    return rows


def has_search_form(page: str) -> bool:
    return SEARCH_ACTION in unwrap(page)


def parse_abstract(page: str) -> dict[str, str]:
    """The Grant Abstract's labelled values by key, plus `announcement_url` (the link before the Announcement Link
    label). The contact name and email are not read."""
    soup = BeautifulSoup(unwrap(page), "html.parser")
    out: dict[str, str] = {}
    for span_id, key in ABSTRACT_SPANS.items():
        out[key] = _text(soup.find("span", id=span_id))
    label = soup.find("span", string=lambda s: s is not None and clean(s) == ANNOUNCEMENT_LABEL)
    link = label.find_previous("a", href=True) if label is not None else None
    href = (link["href"] if link is not None else "").strip()
    out["announcement_url"] = "" if href.lower().startswith(("mailto:", "javascript:")) else href
    return out


def row_key(row: dict[str, Any]) -> str:
    """Agency code plus Event ID: the Event ID alone repeats across agencies."""
    return f"{row['agency_code']}-{re.sub(r'\s+', '-', row['event_id'].strip())}"


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The default (open) grid, one abstract per open row through the row's link and Return to Search, then the
    closed grid. Any failure aborts the run (a partial read would mark unread rounds unknown or blank their
    summaries). With `limit`, only the first rows' abstracts are read and the closed search is skipped."""
    records: dict[str, RawRecord] = {}
    with _client() as client:
        page = _get(client)
        if not has_search_form(page):
            raise RuntimeError("the portal answered without its search form: not the Grant Opportunity page")
        open_rows = parse_rows(page)
        if limit:
            open_rows = open_rows[:limit]
        for row in open_rows:
            if not row["linked"]:
                abstract: dict[str, str] | None = None
            else:
                answer = _post(client, page, LINK_ACTION.format(n=row["n"]))
                abstract = parse_abstract(answer)
                if abstract["event_id"] != row["event_id"]:
                    raise RuntimeError(f"abstract {abstract['event_id']!r} answered for row {row['n']} {row['event_id']!r}")
                page = _post(client, answer, RETURN_ACTION)
            records.setdefault(row_key(row), RawRecord(source_connector=CONNECTOR, source_id=row_key(row),
                                                       payload={"grid": "open", "row": row, "abstract": abstract}))
        if limit:
            return list(records.values())
        closed_rows = parse_rows(_post(client, page, SEARCH_ACTION, **{STATUS_FIELD: CLOSED}))
    if not closed_rows:
        raise RuntimeError("the closed search answered no rows (227 on 2026-11-03): not read")
    for row in closed_rows:
        records.setdefault(row_key(row), RawRecord(source_connector=CONNECTOR, source_id=row_key(row),
                                                   payload={"grid": "closed", "row": row, "abstract": None}))
    agencies = {r.payload["row"]["agency_code"]: r.payload["abstract"]["agency"]
                for r in records.values() if r.payload["abstract"] and r.payload["abstract"].get("agency")}
    for r in records.values():
        if r.payload["abstract"] is None:
            r.payload["agency"] = agencies.get(r.payload["row"]["agency_code"])
    return list(records.values())


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A key on neither grid was taken down, which the source does not state as a closure, and there is no per-record
    URL to read back: unknown, no request."""
    return {"status": "unknown"}


# ---------- normalize ----------

def parse_grid_date(value: str) -> date | None:
    """`10/02/26 10:10AM` and `12/01/2026 4:00PM EST`: the date part, two- or four-digit year."""
    words = value.split() if value else []     # str.split() also splits on the grid's non-breaking spaces
    head = words[0] if words else ""
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(head, fmt).date()
        except ValueError:
            continue
    return None


def parse_abstract_date(value: str) -> date | None:
    """`December 1, 2026 / 04:00 PM`, `Wednesday, November 04, 2026`, `10/14/2026`."""
    s = _WEEKDAY_RE.sub("", clean(value)).split("/ ", 1)[0].strip()
    for fmt in ("%B %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def status_for(label: str) -> str:
    return STATUS_MAP.get(clean(label).lower(), "unknown")


def labels(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def applicant_tags(eligibility: str) -> list[ApplicantTag]:
    tags = []
    for label in labels(eligibility):
        value = portal_applicant(label)
        if value:
            tags.append(ApplicantTag(value=value, source_code=label))
    return tags


PROSE_RE = re.compile(r"[.!?](?:\s|$)")


def profile_tags(profile: str) -> list[ApplicantTag]:
    """The governmental applicants the Solicitation Profile names, sentence by sentence, negated sentences dropped
    (the Texas rule on the only prose the portal has). The matched phrase is the tag's source_code. A profile with
    no sentence in it is a title ("2027 Transportation for Youth to County and Local Fairs", "Municipal Waste
    Reduction and Recycling Program 2024"): a name says what the money is for, not who applies, and tags nothing."""
    if not PROSE_RE.search(profile):
        return []
    lines = [line for line in sentences(profile) if not NEGATION_RE.search(line)]
    return [tag for tag in applicant_types_for(lines or None) if tag.value in GOVERNMENTAL_TYPES]


def applicant_tags_for(row: dict[str, Any], abstract: dict[str, str] | None) -> list[ApplicantTag]:
    """The grid's labels through the table, plus the profile's governmental applicants when the row is open to a
    Governmental Entity and has an abstract."""
    tags = applicant_tags(row["eligibility"])
    if abstract and any(label.lower() == GOVERNMENTAL_ENTITY for label in labels(row["eligibility"])):
        tags += profile_tags(abstract.get("profile", ""))
    return tags


def category_tags(service_areas: str) -> list[CategoryTag]:
    return [CategoryTag(value=value, source_code=label)
            for label in labels(service_areas) for value in portal_categories(label)]


def source_url_for(abstract: dict[str, str] | None) -> str:
    """The announcement link when it is an http(s) URL with a host; else the portal page."""
    href = (abstract or {}).get("announcement_url", "")
    parts = urlparse(href)
    if parts.scheme in ("http", "https") and "." in parts.netloc:
        return href
    return PORTAL_URL


def closes_text_for(row: dict[str, Any]) -> str | None:
    """A date cell that is not a date, verbatim (none seen)."""
    parts = [f"{name}: {row[key]}" for key, name in (("due", "Due date"), ("release", "Release date"))
             if row.get(key) and parse_grid_date(row[key]) is None]
    return "; ".join(parts) or None


def _date_or_text(value: str, parse) -> str | None:
    if not clean(value):
        return None
    parsed = parse(value)
    return parsed.isoformat() if parsed else clean(value)


def structured_for(row: dict[str, Any], abstract: dict[str, str] | None) -> dict[str, Any] | None:
    out: dict[str, Any] = {"portal_status": clean(row["status"])}
    posted = _date_or_text(row.get("posted", ""), parse_grid_date)
    if posted:
        out["posted_at"] = posted
    if abstract:
        for key in ("total_funding", "contract_length"):
            if clean(abstract.get(key, "")):
                out[key] = clean(abstract[key])
        for key in ("anticipated_award_date", "questions_due"):
            value = _date_or_text(abstract.get(key, ""), parse_abstract_date)
            if value:
                out[key] = value
    return out


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    row, abstract = raw.payload["row"], raw.payload.get("abstract")
    agency = clean(abstract["agency"]) if abstract and abstract.get("agency") else None
    agency = agency or raw.payload.get("agency") or AGENCY_NAMES.get(row["agency_code"])
    name = clean(row["name"])
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=source_url_for(abstract),
        external_number=clean(row["event_id"]) or None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=agency,
        agency_code=clean(row["agency_code"]) or None,
        funding_type=funding_type_for(name) or "grant",
        funding_source="direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status=status_for(row["status"]),
        opens_at=parse_grid_date(row.get("release", "")),
        closes_at=parse_grid_date(row.get("due", "")),
        closes_at_text=closes_text_for(row),
        rolling=None,
        summary=(clean(abstract.get("profile", "")) or None) if abstract else None,
        eligibility_text=clean(row["eligibility"]) or None,
        eligibility_structured=structured_for(row, abstract),
        applicant_types=applicant_tags_for(row, abstract),
        categories=category_tags(abstract.get("service_areas", "")) if abstract else [],
        alns=[],
    )
