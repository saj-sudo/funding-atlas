"""Illinois Catalog of State Financial Assistance connector: the GATA office's list of posted funding opportunities.

Source: https://omb.illinois.gov/public/gata/csfa/ (ASP.NET, static HTML, no session). `OpportunityList.aspx` is one
table of the rounds posted now (125 on 2026-11-03): title, agency, application date range, award range. 37 rows link
to a native `Opportunity.aspx?nofo=<n>` page, whose program (`Program.aspx?csfa=<n>`) carries the eligibility; 88
rows are GMS links out to the state's AmpliFund (`il.amplifund.com`, Euna Grants), whose public page carries the same
kind of labelled fields and is read since 2026-11-03. About 160 requests a run. For native rounds whose program text
says `N/A` or `SEE NOFO`, the NOFO attachment's own eligibility sentences are quoted in `NOFO_QUOTES`, read once by
hand (decision 6 in the doc).

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
from connectors.maryland_drupal import NEGATION_RE, sentences
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

# AmpliFund page labels never stored (named people) and the fund activity vocabulary (the Grants.gov list, longest
# first, because the page joins several with ", " and the names contain commas themselves).
AMPLIFUND_CONTACT = frozenset({
    "Agency Contact Name", "Agency Contact Phone", "Agency Contact Email", "Opportunity Manager", "Additional Users",
    "State Awarding Agency Contacts", "Question Submission Email Address",
})
AMPLIFUND_CATEGORIES: tuple[str, ...] = (
    "Employment, Labor, and Training", "Law, Justice, and Legal Services", "Disaster Prevention and Relief",
    "Science and Technology", "Arts and Humanities", "Community Development", "Regional Development",
    "Environmental Quality", "Food and Nutrition", "Natural Resources", "Business and Commerce", "Consumer Protection",
    "Income Security", "Transportation", "Agriculture", "Environment", "Education", "Housing", "Energy", "Health",
)

# Eligibility sentences quoted from a native round's NOFO attachment (`FileView.aspx?nofo=<n>`, a PDF the daily run
# does not read), for rounds whose program text names no applicant. Keyed by nofo number; the date is the day the
# PDF was read. The source's own words, one line per sentence or bullet; a new round gets a new nofo number and no
# quote until someone reads its PDF. See docs/connectors/il_csfa.md decision 6.
NOFO_QUOTES: dict[str, tuple[str, list[str]]] = {
    "1998": ("2026-11-03", [
        "This Redeploy Illinois Planning Grant funding opportunity is limited to those Illinois units of government who are in an Illinois County or Cook County area as defined by 730 ILCS 110/16.1",
        "Interested and eligible is defined as those county units of government who submitted a complete and responsive Planning Grant Final Report",
    ]),
    "2725": ("2026-11-03", [
        "Eligible proposals will come from a Local Government Unit within the State of Illinois, as defined in 35 Ill. Adm. Code 662.110 as follows",
        "Local Government Unit: a county, municipality, township, municipal or county sewerage or utility authority, sanitary district, public water district, improvement authority or any other political subdivision whose primary purpose is to construct, own, operate and maintain wastewater treatment facilities or public water supply facilities or both",
    ]),
    "3149": ("2026-11-03", [
        "Eligible Applicants include: Local Governments; Nonprofit Organizations; For-Profit Organizations; Small Businesses; Educational Organizations",
    ]),
    "4240": ("2026-11-03", [
        "This grant opportunity will be limited to the following types of entities: Units of local government",
        "Locally owned independent grocers or cooperatives with fewer than 500 employees and no more than four Illinois grocery locations. This includes for-profit and nonprofit entities.",
    ]),
    "4335": ("2026-11-03", [
        "The following organization types are potentially eligible for this opportunity: Corporation - For Profit",
        "Limited Liability Company", "All Limited Partnerships", "Agricultural Cooperative", "Local Government Entity",
        "Sole Proprietor", "Special Act Corporation",
    ]),
    "4356": ("2026-11-03", [
        "Eligible Applicants: City or township governments; County Governments; Government Organizations; Nonprofit Organizations",
    ]),
}

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


def parse_amplifund(page_html: str) -> dict[str, str]:
    """An AmpliFund opportunity page's labelled fields (`div.display-group`: label, field) -> text, lines kept apart.
    The contact labels are never read."""
    soup = BeautifulSoup(page_html, "html.parser")
    out: dict[str, str] = {}
    for group in soup.select("div.display-group"):
        label, field = group.select_one(".display-label"), group.select_one(".display-field")
        if label is None or field is None:
            continue
        name = clean(label.get_text(" "))
        if not name or name in AMPLIFUND_CONTACT:
            continue
        lines = [clean(line) for line in field.get_text("\n").split("\n")]
        out[name] = "\n".join(line for line in lines if line)
    return out


def split_categories(text: str) -> list[str]:
    """`Education Employment, Labor, and Training` -> the known names it is made of, longest first; anything left
    over is one piece of its own."""
    rest, out = clean(text), []
    while rest:
        hit = next((c for c in AMPLIFUND_CATEGORIES if rest.lower().startswith(c.lower())), None)
        if hit is None:
            out.append(rest.strip(", "))
            break
        out.append(hit)
        rest = rest[len(hit):].lstrip(", ")
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
                                       "opportunity": None, "program": None, "program_id": None, "amplifund": None}
            old = prior.get(row["source_id"]) or {}
            if row["kind"] == "gms":
                try:
                    time.sleep(DELAY_S)
                    payload["amplifund"] = parse_amplifund(_get(client, row["url"]))
                except httpx.HTTPError:
                    payload["amplifund"] = old.get("amplifund")
            if row["kind"] == "nofo":
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
    still shows a date range that has ended (closed, with that end date). A GMS row's AmpliFund page renders its
    close date by script only, so it is not read back: unknown."""
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


def nofo_quotes(source_id: str) -> list[str]:
    _, quotes = NOFO_QUOTES.get(source_id.split("-", 1)[1] if source_id.startswith("nofo-") else "", ("", []))
    return list(quotes)


def eligibility_of(payload: dict[str, Any], source_id: str = "") -> dict[str, Any]:
    """What the record says about who may apply, in one shape for both row kinds: the portal's labels, the free-text
    lines (each labelled by where it came from) and the NOFO quotes for a native round that has them."""
    program, amp = payload.get("program") or {}, payload.get("amplifund") or {}
    labels = [p.strip() for p in program.get("div_Eligible_Applicants", "").split(";") if p.strip()]
    texts: list[tuple[str, str]] = []
    if program.get("div_Applicant_Eligibility"):
        texts.append(("Applicant eligibility", program["div_Applicant_Eligibility"]))
    if amp:
        labels = [p.strip() for p in amp.get("Eligible Applicants", "").split(", ") if p.strip()]
        for label, key in (("Applicant eligibility", "Applicant Eligibility Information"),
                           ("Additional eligibility", "Additional Eligibility Information")):
            if amp.get(key):
                texts.append((label, amp[key]))
    quotes = nofo_quotes(source_id)
    return {"labels": labels, "texts": texts, "quotes": quotes}


def applicant_tags(elig: dict[str, Any]) -> list[ApplicantTag]:
    """The labels through the shared table, then the free text and the NOFO quotes sentence by sentence through the
    shared tagger, negated sentences dropped ("not open to local units of government" tags nothing)."""
    tags: list[ApplicantTag] = []
    for part in elig["labels"]:
        value = portal_applicant(part)
        if value and all(t.value != value for t in tags):
            tags.append(ApplicantTag(value=value, source_code=part))
    lines = [line for _, text in elig["texts"] for line in text.split("\n") if line] + elig["quotes"]
    kept = [s for line in lines for s in sentences(line) if not NEGATION_RE.search(s)]
    for tag in applicant_types_for(kept or None):
        if all(t.value != tag.value for t in tags):
            tags.append(tag)
    return tags


def category_tags(payload: dict[str, Any]) -> list[CategoryTag]:
    program, amp = payload.get("program") or {}, payload.get("amplifund") or {}
    subject = program.get("div_Subject_Area", "")
    if subject:
        return [CategoryTag(value=value, source_code=subject) for value in portal_categories(subject)]
    return [CategoryTag(value=value, source_code=label)
            for label in split_categories(amp.get("Fund Activity Categories", "")) for value in portal_categories(label)]


def eligibility_text_for(elig: dict[str, Any], source_id: str = "") -> str | None:
    lines = []
    if elig["labels"]:
        lines.append("Eligible applicants: " + "; ".join(elig["labels"]))
    lines += [f"{label}: {text}" for label, text in elig["texts"]]
    if elig["quotes"]:
        read_on = NOFO_QUOTES[source_id.split("-", 1)[1]][0]
        lines.append(f"NOFO (read {read_on}): " + " ".join(elig["quotes"]))
    return "\n".join(lines) or None


def eligibility_structured_for(payload: dict[str, Any], elig: dict[str, Any]) -> dict[str, Any] | None:
    program, amp = payload.get("program") or {}, payload.get("amplifund") or {}
    out: dict[str, Any] = {}
    if elig["labels"]:
        out["eligible_applicants"] = elig["labels"]
    if program.get("div_Subject_Area"):
        out["subject_area"] = program["div_Subject_Area"]
    if amp.get("Fund Activity Categories"):
        out["fund_activity_categories"] = split_categories(amp["Fund Activity Categories"])
    for key, name in (("Opportunity Funding", "opportunity_funding"), ("Award Type", "award_type"),
                      ("Submission Timeline Type", "submission_timeline")):
        if amp.get(key):
            out[name] = amp[key]
    return out or None


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    payload = raw.payload
    row, opp, program = payload["list"], payload.get("opportunity") or {}, payload.get("program") or {}
    amp = payload.get("amplifund") or {}
    elig = eligibility_of(payload, raw.source_id)
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
        external_number=opp.get("div_CSFA_Number") or amp.get("CSFA Number") or None,
        name=title,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=payload.get("agency_name") or abbreviation or None,
        agency_code=f"IL-{abbreviation}" if abbreviation else None,
        funding_type="grant" if assistance == "grant" else funding_type_for(title),
        funding_source=funding_source_for(opp.get("div_Funding_Source") or amp.get("Funding Sources", "")),
        amount_min=amount_min,
        amount_max=amount_max,
        match_required=match_required_for(opp.get("div_Cost_Sharing_Match_Required") or amp.get("Matching Requirement", "")),
        match_pct=None,
        status=status_for(start, end, today),
        opens_at=start,
        closes_at=end,
        closes_at_text="No end date" if open_ended else None,
        rolling=True if open_ended else None,
        summary=program.get("div_Short_Desc") or program.get("div_Objective") or amp.get("Description") or None,
        eligibility_text=eligibility_text_for(elig, raw.source_id),
        eligibility_structured=eligibility_structured_for(payload, elig),
        applicant_types=applicant_tags(elig),
        categories=category_tags(payload),
        alns=[],
    )
