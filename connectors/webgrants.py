"""WebGrants storefront connector: the public opportunity lists of Iowa and Montana's agency hosts.

WebGrants (Dulles Technology) serves the same storefront on every host: `storefrontFOList.do` is one static table of
the opportunities posted now, `viewStorefrontOpportunity.do?OIDString=<oid>|Opportunity` one page per opportunity.
The state is configuration (`HOSTS`); columns are read by header name because one host has no pre-application column.
About 41 requests a run. A round that ends leaves the list, so nothing can be read back for it: `resolve_missing`
says `unknown`. Applicants come from the page's eligibility sections only. See docs/connectors/webgrants.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import APPLICANT_MARKER_RE, CONDITION_LEAD_IN_RE, NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for, portal_categories
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "webgrants"
# host key -> (base URL, state). A fourth storefront is one line.
HOSTS: dict[str, tuple[str, str]] = {
    "ia": ("https://www.iowagrants.gov", "IA"),
    "mtagr": ("https://mtagr.webgrantscloud.com", "MT"),
    "mtfwp": ("https://mtfwp.webgrantscloud.com", "MT"),
}
LIST_PATH = "/storefrontFOList.do"
DETAIL_PATH = "/viewStorefrontOpportunity.do?OIDString={oid}"
DELAY_S = 0.3
TIMEOUT_S = 30.0
TRIES = 3
RETRY_WAIT_S = 1.5
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

# List header -> row key.
COLUMNS = {
    "id": "id", "status": "status", "categorical area": "categorical_area", "agency": "agency",
    "program area": "program_area", "title": "title", "posted date": "posted",
    "pre-application due date": "pre_due", "final-application due date": "final_due",
}
# Labels of the contact block. Public on the state's page, and not copied into our payload, which is published.
CONTACT_LABELS = {"program officer", "phone", "email", "e-mail"}
NOT_APPLICABLE = "not applicable"
NO_LIMIT = "no limit"
AMOUNT_RE = re.compile(r"^(No Limit|\$\s*[\d,]+(?:\.\d+)?)\s*-\s*(No Limit|\$\s*[\d,]+(?:\.\d+)?)$", re.I)
BLOCKS = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6"]
ELIGIBILITY_HEADING_RE = re.compile(
    r"^(?:eligible applicants?|eligibility(?: requirements)?|applicant eligibility|who (?:may|can) apply|eligible entities)"
    r"\s*:?$", re.I)


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def _get(client: httpx.Client, url: str) -> str:
    """The page text. A dropped connection is retried (a TLS reset was seen once); an HTTP error status is not."""
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

def parse_list(page_html: str) -> list[dict[str, str]]:
    """One dict per storefront row, keyed by COLUMNS plus `oid` (the page key). Header names decide the columns."""
    soup = BeautifulSoup(page_html, "html.parser")
    table = soup.find("table", id="storefrontFO")
    if table is None:
        return []
    keys = [COLUMNS.get(clean(th.get_text(" ")).lower()) for th in table.find_all("th")]
    rows: list[dict[str, str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        link = tr.find("a", href=True)
        if not cells or link is None or len(cells) != len(keys) or "OIDString=" not in link["href"]:
            continue
        row = {key: clean(cell.get_text(" ")) for key, cell in zip(keys, cells, strict=True) if key}
        row["oid"] = link["href"].split("OIDString=", 1)[1]
        rows.append(row)
    return rows


def _is_heading(el: Tag) -> bool:
    """A short paragraph that is all bold, or all capitals, or a real heading tag, and is not a sentence."""
    text = clean(el.get_text(" "))
    if not text or len(text) > 60 or text.endswith("."):
        return False
    if el.name.startswith("h"):
        return True
    bold = "".join(clean(b.get_text(" ")) for b in el.find_all(["strong", "b"]))
    return el.name == "p" and (bold.replace(" ", "") == text.replace(" ", "") or (text.upper() == text and bool(re.search("[A-Z]", text))))


def parse_detail(page_html: str) -> dict[str, Any]:
    """`fields`: label -> value of the labelled block (the contact lines are left out). `blocks`: [tag, text, is_heading] for each paragraph, list
    item and heading of the description, in order (empty when the page has no description)."""
    soup = BeautifulSoup(page_html, "html.parser")
    fields: dict[str, str] = {}
    for label in soup.find_all("span", class_="field-label"):
        name = clean(label.get_text(" "))
        value = label.find_next_sibling("span", class_="field")
        if value is not None and name.lower() not in CONTACT_LABELS:
            fields[name] = clean(value.get_text(" "))
    synopsis = soup.find("span", id="OpportunitySynopsis_synopsis")
    blocks: list[list[Any]] = []
    for el in synopsis.find_all(BLOCKS) if synopsis else []:
        if el.find(BLOCKS) or not clean(el.get_text(" ")):
            continue
        blocks.append([el.name, clean(el.get_text(" ")), _is_heading(el)])
    return {"fields": fields, "blocks": blocks}


def eligibility_sections(blocks: list[list[Any]]) -> list[tuple[str, list[tuple[str, str]]]]:
    """(heading, [(tag, text), ...]) for each eligibility section: opened by a heading block that is exactly an
    eligibility label, closed by the next heading block."""
    out: list[tuple[str, list[tuple[str, str]]]] = []
    current: list[tuple[str, str]] | None = None
    for tag, text, heading in blocks:
        if ELIGIBILITY_HEADING_RE.match(text):
            current = []
            out.append((text.rstrip(":").strip(), current))
        elif current is not None and heading:
            current = None
        elif current is not None:
            current.append(("li" if tag == "li" else "p", text))
    return [(h, lines) for h, lines in out if lines]


def applicant_sentences(lines: list[tuple[str, str]]) -> list[str]:
    """The sentences of one eligibility section that name who applies. The Drupal base's rule for who-may-apply lines
    (the first line is the applicant statement; later lines only if marked; stop at a condition lead-in like
    "criteria:"), except that negation is judged per sentence: "Units of government (cities, counties) are not
    eligible" drops, and the applicant sentence beside it stays."""
    kept: list[str] = []
    listing = True
    for i, (tag, text) in enumerate(lines):
        marked = i == 0 or bool(APPLICANT_MARKER_RE.search(text))
        if tag == "p":
            if marked:
                kept.append(text)
            if text.endswith(":") and CONDITION_LEAD_IN_RE.search(text):
                break
            listing = marked and text.endswith(":")
        elif listing:
            kept.append(text)
    return [s for line in kept for s in sentences(line) if not NEGATION_RE.search(s)]


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """Each host's list, then every row's detail page. A list that cannot be read aborts the run (every round on that
    host would otherwise look missing); a detail page that cannot be read falls back to the stored copy."""
    prior = prior or {}
    records: list[RawRecord] = []
    with _client() as client:
        for key, (base, _state) in HOSTS.items():
            for row in parse_list(_get(client, base + LIST_PATH)):
                source_id = f"{key}-{row['id']}"
                try:
                    time.sleep(DELAY_S)
                    detail: dict[str, Any] | None = parse_detail(_get(client, base + DETAIL_PATH.format(oid=row["oid"])))
                except httpx.HTTPError:
                    detail = (prior.get(source_id) or {}).get("detail")
                records.append(RawRecord(source_connector=CONNECTOR, source_id=source_id,
                                         payload={"host": key, "list": row, "detail": detail}))
    return records[:limit] if limit else records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A round that left the list. The storefront drops an ended round and answers HTTP 500 for an id it no longer
    lists, so there is nothing to read back and leaving is not a closure the source states: unknown."""
    return {"status": "unknown"}


# ---------- normalize ----------

def status_for(label: str, posted: date | None, final: date | None, today: date) -> str:
    if label.strip().lower() != "posted":
        return "unknown"
    if posted and posted > today:
        return "forecasted"
    if final and final < today:
        return "closed"
    return "open"


def amount_fields(text: str) -> tuple[int | None, int | None]:
    m = AMOUNT_RE.match(clean(text))
    if not m:
        return None, None

    def money(part: str) -> int | None:
        return None if part.lower() == NO_LIMIT else int(float(re.sub(r"[$,\s]", "", part)))

    return money(m.group(1)), money(m.group(2))


def closes_text_for(pre_due: str, final_due: str, recurring: str) -> str | None:
    """`Pre-application due: <date>` unless it is the final date (the list repeats it on some rounds), and
    `Recurring opportunity` when the page says Yes."""
    parts = []
    pre = parse_date(pre_due)
    if pre and pre != parse_date(final_due):
        parts.append(f"Pre-application due: {pre.isoformat()}")
    if recurring.strip().lower() == "yes":
        parts.append("Recurring opportunity")
    return "; ".join(parts) or None


def category_tags(area: str) -> list[CategoryTag]:
    return [CategoryTag(value=value, source_code=part)
            for part in (p.strip() for p in area.split(",")) if part and part.lower() != "unspecified"
            for value in portal_categories(part)]


def applicant_tags(blocks: list[list[Any]]) -> list[ApplicantTag]:
    lines = [s for _, section in eligibility_sections(blocks) for s in applicant_sentences(section)]
    return applicant_types_for(lines or None)


def eligibility_text_for(blocks: list[list[Any]]) -> str | None:
    sections = eligibility_sections(blocks)
    return "\n\n".join(f"{heading}\n" + "\n".join(text for _, text in lines) for heading, lines in sections) or None


def summary_for(blocks: list[list[Any]]) -> str | None:
    return next((text for _, text, heading in blocks if not heading and not ELIGIBILITY_HEADING_RE.match(text)), None)


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    payload = raw.payload
    row, detail = payload["list"], payload.get("detail") or {}
    fields, blocks = detail.get("fields") or {}, detail.get("blocks") or []
    today = today or date.today()
    key = payload["host"]
    base, state = HOSTS[key]
    posted, final = parse_date(row.get("posted")), parse_date(row.get("final_due"))
    final_text = row.get("final_due", "").strip().lower()
    amount_min, amount_max = amount_fields(fields.get("Award Amount Range", ""))
    area = row.get("categorical_area") or fields.get("Categorical Area", "")
    structured: dict[str, Any] = {}
    if area:
        structured["categorical_area"] = [a.strip() for a in area.split(",") if a.strip()]
    if fields.get("Recurring Opportunity"):
        structured["recurring"] = fields["Recurring Opportunity"]
    title = clean(row.get("title"))
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=base + DETAIL_PATH.format(oid=row["oid"]),
        external_number=row.get("id") or None,
        name=title,
        level="state",
        jurisdiction=state,
        administering_agency=row.get("agency") or None,
        agency_code=None,
        funding_type=funding_type_for(title),
        funding_source="direct",
        amount_min=amount_min,
        amount_max=amount_max,
        match_required=None,
        match_pct=None,
        status=status_for(row.get("status", ""), posted, final, today),
        opens_at=posted,
        closes_at=final,
        closes_at_text=closes_text_for(row.get("pre_due", ""), row.get("final_due", ""), fields.get("Recurring Opportunity", "")),
        rolling=True if final_text == NOT_APPLICABLE else None,
        summary=summary_for(blocks),
        eligibility_text=eligibility_text_for(blocks),
        eligibility_structured=structured or None,
        applicant_types=applicant_tags(blocks),
        categories=category_tags(area),
        alns=[],
    )
