"""Illinois Catalog of State Financial Assistance connector: the GATA office's list of posted funding opportunities.

Source: https://omb.illinois.gov/public/gata/csfa/ (ASP.NET, static HTML, no session). `OpportunityList.aspx` is one
table of the rounds posted now (119 on 2026-10-28): title, agency, application date range, award range. 35 rows link
to a native `Opportunity.aspx?nofo=<n>` page, whose program (`Program.aspx?csfa=<n>`) carries the eligibility; 84
rows are GMS links out to the state's AmpliFund and are read from the list alone (never fetched). About 70 requests
a run.

The list is "posted now": a round that ends leaves it. Status follows the list's own dates; a round that disappears
is `unknown` unless its native page still shows a date range that has ended. See docs/connectors/il_csfa.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from connectors.grants_gov import parse_date
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for, portal_applicant, portal_categories
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "il_csfa"
BASE = "https://omb.illinois.gov/public/gata/csfa/"
LIST_URL = BASE + "OpportunityList.aspx"
AGENCY_URL = BASE + "AgencyList.aspx"
OPPORTUNITY_URL = BASE + "Opportunity.aspx?nofo={n}"
PROGRAM_URL = BASE + "Program.aspx?csfa={n}"
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"
JURISDICTION = "IL"

RANGE_RE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4}|No end date)", re.I)
AWARD_RE = re.compile(r"^\$?\s*([\d,]+(?:\.\d+)?)\s*-\s*\$?\s*([\d,]+(?:\.\d+)?)$")
AGENCY_RE = re.compile(r"^(.*?)\s*\((\d+)\)\s*$")
NOFO_RE = re.compile(r"nofo=(\d+)")
CSFA_RE = re.compile(r"csfa=(\d+)")
NO_END = "no end date"

# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


# ---------- parsing (no I/O) ----------

def amplifund_target(href: str) -> str | None:
    """The AmpliFund URL inside a `GMS.aspx?url=...` link, or None."""
    values = parse_qs(urlparse(href).query).get("url")
    return values[0] if values else None


def parse_list(page_html: str) -> list[dict[str, Any]]:
    """One dict per row of the opportunity table: source_id, kind (`nofo` / `gms`), url, title, agency text,
    date range text, award range text. Rows that link to neither shape are dropped."""
    soup = BeautifulSoup(page_html, "html.parser")
    table = soup.find("table", id="tblList")
    rows: list[dict[str, Any]] = []
    for tr in table.find("tbody").find_all("tr") if table and table.find("tbody") else []:
        cells = tr.find_all("td")
        link = cells[0].find("a", href=True) if len(cells) >= 4 else None
        if link is None:
            continue
        href = link["href"]
        m = NOFO_RE.search(href)
        if m:
            source_id, kind, url = f"nofo-{m.group(1)}", "nofo", urljoin(BASE, href)
        else:
            url = amplifund_target(href)
            guid = url.rstrip("/").rsplit("/", 1)[-1] if url else ""
            if not guid:
                continue
            source_id, kind = f"gms-{guid}", "gms"
        rows.append({
            "source_id": source_id, "kind": kind, "url": url, "title": clean(link.get_text(" ")),
            "agency": clean(cells[1].get_text(" ")), "date_range": clean(cells[2].get_text(" ")),
            "award_range": clean(cells[3].get_text(" ")),
        })
    return rows


def parse_agencies(page_html: str) -> dict[str, str]:
    """Agency number -> full name, from the agency table's `Name (123)` links."""
    soup = BeautifulSoup(page_html, "html.parser")
    out: dict[str, str] = {}
    for a in soup.select("table#tblList td a"):
        m = AGENCY_RE.match(clean(a.get_text(" ")))
        if m:
            out[m.group(2)] = m.group(1)
    return out


def parse_fields(page_html: str) -> dict[str, str]:
    """`div_*` blocks -> text. Lines inside a block stay on separate lines (the tagger reads lines)."""
    soup = BeautifulSoup(page_html, "html.parser")
    out: dict[str, str] = {}
    for div in soup.find_all("div", id=re.compile(r"^div_")):
        if isinstance(div, Tag):
            lines = [clean(line) for line in div.get_text("\n").split("\n")]
            out[div["id"]] = "\n".join(line for line in lines if line)
    return out


def program_number(opportunity_html: str) -> str | None:
    m = CSFA_RE.search(opportunity_html)
    return m.group(1) if m else None


def split_agency(text: str) -> tuple[str, str | None]:
    """`DCEO (420)` -> (`DCEO`, `420`)."""
    m = AGENCY_RE.match(text)
    return (m.group(1), m.group(2)) if m else (text, None)


def date_range(text: str) -> tuple[date | None, date | None, bool]:
    """(start, end, open_ended) from `MM/DD/YYYY - MM/DD/YYYY` or `MM/DD/YYYY - No end date`."""
    m = RANGE_RE.search(text or "")
    if not m:
        return None, None, False
    end = m.group(2)
    return parse_date(m.group(1)), None if end.lower() == NO_END else parse_date(end), end.lower() == NO_END


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The list, the agency table, then each native row's opportunity page and (once per program) program page.
    A detail page that cannot be read falls back to the last stored copy in `prior`."""
    prior = prior or {}
    records: list[RawRecord] = []
    programs: dict[str, dict[str, str] | None] = {}
    with _client() as client:
        rows = parse_list(_get(client, LIST_URL))
        agencies = parse_agencies(_get(client, AGENCY_URL))
        if limit:
            rows = rows[:limit]
        for row in rows:
            _, number = split_agency(row["agency"])
            payload: dict[str, Any] = {"list": row, "agency_name": agencies.get(number or "") or None,
                                       "opportunity": None, "program": None, "program_id": None}
            if row["kind"] == "nofo":
                old = prior.get(row["source_id"]) or {}
                try:
                    time.sleep(DELAY_S)
                    opp_html = _get(client, OPPORTUNITY_URL.format(n=row["source_id"].split("-", 1)[1]))
                    payload["opportunity"] = parse_fields(opp_html)
                    csfa = program_number(opp_html)
                    payload["program_id"] = csfa
                    if csfa and csfa not in programs:
                        time.sleep(DELAY_S)
                        programs[csfa] = parse_fields(_get(client, PROGRAM_URL.format(n=csfa)))
                    payload["program"] = programs.get(csfa) if csfa else None
                except httpx.HTTPError:
                    payload["opportunity"] = old.get("opportunity")
                    payload["program"] = old.get("program")
                    payload["program_id"] = old.get("program_id")
            records.append(RawRecord(source_connector=CONNECTOR, source_id=row["source_id"], payload=payload))
    return records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A round that left the list. Not a closure the source stated -> unknown, unless the round's own native page
    still shows a date range that has ended (closed, with that end date). GMS rows are never fetched."""
    if not source_id.startswith("nofo-"):
        return {"status": "unknown"}
    try:
        with _client() as client:
            fields = parse_fields(_get(client, OPPORTUNITY_URL.format(n=source_id.split("-", 1)[1])))
    except httpx.HTTPError:
        return None
    _, end, _ = date_range(fields.get("div_Application_Range", ""))
    if end and end < date.today():
        return {"status": "closed", "closes_at": end}
    return {"status": "unknown"}


# ---------- normalize ----------

def status_for(start: date | None, end: date | None, today: date) -> str:
    if start and start > today:
        return "forecasted"
    if end and end < today:
        return "closed"
    return "open"


def amount_fields(text: str) -> tuple[int | None, int | None]:
    m = AWARD_RE.match(clean(text))
    return (int(float(m.group(1).replace(",", ""))), int(float(m.group(2).replace(",", "")))) if m else (None, None)


def funding_source_for(value: str) -> str:
    return "pass_through" if "federal" in value.lower() else "direct"


def match_required_for(value: str) -> bool | None:
    return {"yes": True, "no": False}.get(value.strip().lower())


def applicant_tags(program: dict[str, str] | None) -> list[ApplicantTag]:
    if not program:
        return []
    tags: list[ApplicantTag] = []
    for part in (p.strip() for p in program.get("div_Eligible_Applicants", "").split(";")):
        value = portal_applicant(part)
        if value and all(t.value != value for t in tags):
            tags.append(ApplicantTag(value=value, source_code=part))
    text = program.get("div_Applicant_Eligibility", "")
    for tag in applicant_types_for([line for line in text.split("\n") if line] or None):
        if all(t.value != tag.value for t in tags):
            tags.append(tag)
    return tags


def category_tags(program: dict[str, str] | None) -> list[CategoryTag]:
    subject = (program or {}).get("div_Subject_Area", "")
    return [CategoryTag(value=value, source_code=subject) for value in portal_categories(subject)] if subject else []


def eligible_list(program: dict[str, str] | None) -> list[str]:
    return [p.strip() for p in (program or {}).get("div_Eligible_Applicants", "").split(";") if p.strip()]


def eligibility_text_for(program: dict[str, str] | None) -> str | None:
    if not program:
        return None
    lines = []
    if eligible_list(program):
        lines.append("Eligible applicants: " + "; ".join(eligible_list(program)))
    if program.get("div_Applicant_Eligibility"):
        lines.append("Applicant eligibility: " + program["div_Applicant_Eligibility"])
    return "\n".join(lines) or None


def eligibility_structured_for(program: dict[str, str] | None) -> dict[str, Any] | None:
    out: dict[str, Any] = {}
    if eligible_list(program):
        out["eligible_applicants"] = eligible_list(program)
    if (program or {}).get("div_Subject_Area"):
        out["subject_area"] = program["div_Subject_Area"]
    return out or None


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    payload = raw.payload
    row, opp, program = payload["list"], payload.get("opportunity") or {}, payload.get("program")
    today = today or date.today()
    start, end, open_ended = date_range(row.get("date_range", ""))
    abbreviation, _ = split_agency(row.get("agency", ""))
    amount_min, amount_max = amount_fields(row.get("award_range", ""))
    assistance = opp.get("div_Assistance_Type", "").lower()
    title = clean(row.get("title"))
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=row["url"],
        external_number=opp.get("div_CSFA_Number") or None,
        name=title,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=payload.get("agency_name") or abbreviation or None,
        agency_code=f"IL-{abbreviation}" if abbreviation else None,
        funding_type="grant" if assistance == "grant" else funding_type_for(title),
        funding_source=funding_source_for(opp.get("div_Funding_Source", "")),
        amount_min=amount_min,
        amount_max=amount_max,
        match_required=match_required_for(opp.get("div_Cost_Sharing_Match_Required", "")),
        match_pct=None,
        status=status_for(start, end, today),
        opens_at=start,
        closes_at=end,
        closes_at_text="No end date" if open_ended else None,
        rolling=True if open_ended else None,
        summary=(program or {}).get("div_Short_Desc") or (program or {}).get("div_Objective") or None,
        eligibility_text=eligibility_text_for(program),
        eligibility_structured=eligibility_structured_for(program),
        applicant_types=applicant_tags(program),
        categories=category_tags(program),
        alns=[],
    )
