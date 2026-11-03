"""Virginia Department of Criminal Justice Services connector: the agency's "Current Funding Opportunities" view.

Source: https://www.dcjs.virginia.gov/grants (Drupal 10), one table of 59 rows on 2026-11-03 (title, application due
date, date posted, a link to the program page), plus one program page per row: a prose body with, on some pages, a
labelled eligibility passage; a details block with due, posted and archive dates; a contact block never read. The
view holds a round until its archive date, so "current" is not "open": status comes from the due date. About 60
requests a run. See docs/connectors/va_dcjs.md.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Comment, Tag

from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for
from pipeline.models import ApplicantTag, Program, RawRecord

CONNECTOR = "va_dcjs"
BASE = "https://www.dcjs.virginia.gov"
LIST_URL = BASE + "/grants"
AGENCY = "Department of Criminal Justice Services"
AGENCY_CODE = "VA-DCJS"
JURISDICTION = "VA"
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

CONTENT_SELECTOR = "#block-uswds-base-subtheme-content"
BODY_SELECTOR = CONTENT_SELECTOR + " .field--name-body"
ELIGIBILITY_RE = re.compile(r"eligib", re.I)
OGMS_RE = re.compile(r"accepting applications through", re.I)
LABEL_MAX_CHARS = 80


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


# ---------- parsing (no I/O) ----------

def _soup(page_html: str) -> BeautifulSoup:
    soup = BeautifulSoup(page_html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):   # Drupal's THEME DEBUG comments
        c.extract()
    return soup


def parse_rows(page_html: str) -> list[dict[str, Any]]:
    """One dict per row of the view, in page order: slug, url, title, due (ISO), posted (ISO). A slug seen twice is
    kept once."""
    soup = _soup(page_html)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tr in soup.select("table.usa-table tbody tr"):
        link = tr.select_one("td.views-field-title a[href]")
        if link is None:
            continue
        url = urljoin(BASE, link["href"])
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if slug in seen:
            continue
        seen.add(slug)
        due = tr.select_one("td.views-field-field-application-due-date time[datetime]")
        posted = tr.select_one("td.views-field-field-date-posted time[datetime]")
        rows.append({"slug": slug, "url": url, "title": clean(link.get_text(" ")),
                     "due": due["datetime"] if due else "", "posted": posted["datetime"] if posted else ""})
    return rows


def _is_label(el: Tag) -> bool:
    """A heading, or a short paragraph that is wholly bold or ends with a colon: the way the pages label a passage."""
    if el.name in ("h2", "h3", "h4", "h5"):
        return True
    text = clean(el.get_text(" "))
    if not text or len(text) > LABEL_MAX_CHARS:
        return False
    bold = el.find(["strong", "b"])
    return text.endswith(":") or (bold is not None and clean(bold.get_text(" ")) == text)


def _bold_lead(el: Tag) -> tuple[str, str] | None:
    """`<p><strong>Eligible Applicants:</strong> This funding ...</p>` -> ("Eligible Applicants:", "This funding ...")."""
    bold = el.find(["strong", "b"])
    if bold is None or el.name != "p":
        return None
    lead = clean(bold.get_text(" "))
    whole = clean(el.get_text(" "))
    if lead and whole.startswith(lead) and len(whole) > len(lead):
        return lead, whole[len(lead):].strip(" :")
    return None


def eligibility_passage(body: Tag) -> list[str]:
    """The paragraphs and list items after a heading or bold label that mentions eligibility, up to the next label."""
    out: list[str] = []
    on = False
    for el in body.find_all(["h2", "h3", "h4", "h5", "p", "li"]):
        if el.name == "li" and el.find_parent("li") is not None:
            continue
        lead = _bold_lead(el)
        if lead and ELIGIBILITY_RE.search(lead[0]):
            on = True
            out.append(lead[1])
            continue
        if _is_label(el):
            on = bool(ELIGIBILITY_RE.search(clean(el.get_text(" "))))
            continue
        if on:
            text = clean(el.get_text(" ")) if el.name != "li" else clean(" ".join(el.find_all(string=True, recursive=False)) or el.get_text(" "))
            if text:
                out.append(text)
    return out


def parse_program(page_html: str) -> dict[str, Any]:
    """title, paragraphs (body text, one per block), eligibility (the labelled passage), due / posted / archive (ISO),
    guidelines (PDF URLs). The contact block is not read."""
    soup = _soup(page_html)
    content, body = soup.select_one(CONTENT_SELECTOR), soup.select_one(BODY_SELECTOR)
    out: dict[str, Any] = {"title": clean(soup.h1.get_text(" ")) if soup.h1 else "", "paragraphs": [],
                           "eligibility": [], "due": "", "posted": "", "archive": "", "guidelines": []}
    if body is not None:
        out["paragraphs"] = [t for t in (clean(p.get_text(" ")) for p in body.find_all(["p", "li"])) if t]
        out["eligibility"] = eligibility_passage(body)
    if content is not None:      # the "Guidelines & Forms Reference" block sits beside the body in the content column
        out["guidelines"] = sorted({urljoin(BASE, a["href"]) for a in content.find_all("a", href=True) if a["href"].lower().endswith(".pdf")})
    for key, cls in (("due", "application-due-date"), ("posted", "date-posted"), ("archive", "archive-date")):
        t = soup.select_one(f".views-field-field-{cls} time[datetime]")
        if t is not None:
            out[key] = t["datetime"]
    return out


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The view, then every program page. A page that cannot be read falls back to the stored copy."""
    prior = prior or {}
    records: list[RawRecord] = []
    with _client() as client:
        rows = parse_rows(_get(client, LIST_URL))
        if limit:
            rows = rows[:limit]
        for row in rows:
            payload: dict[str, Any] = {"row": row, "program": None}
            try:
                time.sleep(DELAY_S)
                payload["program"] = parse_program(_get(client, row["url"]))
            except httpx.HTTPError:
                payload["program"] = (prior.get(row["slug"]) or {}).get("program")
            records.append(RawRecord(source_connector=CONNECTOR, source_id=row["slug"], payload=payload))
    return records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A row that left the view (its archive date passed). Its page still says when it was due."""
    try:
        with _client() as client:
            program = parse_program(_get(client, f"{BASE}/grants/programs/{source_id}"))
    except httpx.HTTPError:
        return None
    due = parse_iso_date(program.get("due", ""))
    if due and due < date.today():
        return {"status": "closed", "closes_at": due}
    return {"status": "unknown"}


# ---------- normalize ----------

def parse_iso_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date() if value else None
    except ValueError:
        return None


def status_for(due: date | None, today: date) -> str:
    if due is None:
        return "unknown"
    return "open" if due >= today else "closed"


def applicant_tags(passage: list[str]) -> list[ApplicantTag]:
    lines = [s for line in passage for s in sentences(line) if not NEGATION_RE.search(s)]
    return applicant_types_for(lines or None)


def summary_for(paragraphs: list[str]) -> str | None:
    for p in paragraphs:
        if not OGMS_RE.search(p):
            return p
    return paragraphs[0] if paragraphs else None


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    row, program = raw.payload["row"], raw.payload.get("program") or {}
    today = today or date.today()
    due = parse_iso_date(program.get("due") or row.get("due", ""))
    posted = parse_iso_date(program.get("posted") or row.get("posted", ""))
    name = clean(row["title"]) or clean(program.get("title", ""))
    structured: dict[str, Any] = {}
    if program.get("due") or row.get("due"):
        structured["due_at"] = program.get("due") or row["due"]
    if parse_iso_date(program.get("archive", "")):
        structured["archive_date"] = parse_iso_date(program["archive"]).isoformat()
    if program.get("guidelines"):
        structured["guidelines"] = program["guidelines"]
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=row["url"],
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(name) or "grant",
        funding_source="direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status=status_for(due, today),
        opens_at=posted,
        closes_at=due,
        closes_at_text=None,
        rolling=None,
        summary=summary_for(program.get("paragraphs", [])),
        eligibility_text="\n".join(program.get("eligibility", [])) or None,
        eligibility_structured=structured or None,
        applicant_types=applicant_tags(program.get("eligibility", [])),
        categories=[],
        alns=[],
    )
