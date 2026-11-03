"""Maryland Department of the Environment connector: the Water Infrastructure Financing Administration's seven
loan and grant programs, read from its index table under one status banner.

Source: https://mde.maryland.gov (SharePoint, the state's `mdgov` theme; shared mechanics in
connectors/maryland_sharepoint.py). `/programs/water/WQFA/Pages/index.aspx` opens with an `<h2>` banner ("MWIFA's
funding solicitation is currently closed. Applications will reopen in December 2026.") and lists the programs in a
`Financial Program | Purpose` table: six rows link a page, one (Supplemental Assistance) does not and is keyed to the
index itself. The banner sets every row's status (closed with a month still ahead is `forecasted`); the Purpose cell
and the page's applicant sentences name who may apply. See docs/connectors/md_mde.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup

from connectors.maryland_drupal import NEGATION_RE, clean, funding_type_for
from connectors.maryland_sharepoint import (
    DATE_RE,
    MONTH,
    MarylandSharePointConnector,
    body_div,
    canonical_url,
    future_marker,
    main_section,
    page_sentences,
    parse_text_date,
    source_id_for,
    text_hash,
)
from pipeline.models import CategoryTag, Program, RawRecord

CONNECTOR = "md_mde"
BASE = "https://mde.maryland.gov"
AGENCY = "Maryland Department of the Environment"
AGENCY_CODE = "MD-MDE"

INDEX_PATH = "programs/water/wqfa/pages/index.aspx"
INDEX_PATHS: tuple[str, ...] = (INDEX_PATH,)
# "Both loan programs receive federal funding from the United States Environmental Protection Agency (EPA)" (index);
# no ALN on the page, so none is stated.
PASS_THROUGH: dict[str, list[str]] = {
    "programs/water/wqfa/pages/water_quality_fund.aspx": [],
    "programs/water/wqfa/pages/drinking_water_fund.aspx": [],
}
# "the Bay Restoration Fund (BRF) Onsite Sewer Disposal System (OSDS) grant program" (page); the name has no keyword.
FUNDING_TYPE_OVERRIDES = {"programs/water/bayrestorationfund/onsitedisposalsystems/pages/index.aspx": "grant"}

BANNER_RE = re.compile(r"\bsolicitation\b|\bapplications?\b", re.I)
CLOSED_RE = re.compile(r"\b(?:is|are) (?:currently |now )?closed\b|\bnot (?:currently )?(?:being )?accept", re.I)
REOPEN_RE = re.compile(rf"\b(?:reopen|open|resume)s?\b[^.]*?({MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}|{MONTH} \d{{4}})", re.I)
OPEN_RE = re.compile(r"\b(?:is|are) (?:now |currently )?(?:open|accepting)\b|\bnow accepting\b|\bapplications? (?:are|is) (?:now )?(?:being )?accepted\b", re.I)
CYCLE_RE = re.compile(r"\bapplications? accepted\b|\baccepted .*? annually\b", re.I)
APPLICANT_SENTENCE_RE = re.compile(
    r"\beligible\b|\bmay apply\b|\bavailable to\b|\bassistance to\b|\bloans? to\b|\bassist\b|\bonly\b", re.I
)
MATCH_RE = re.compile(r"\brequires? a (?:local )?match\b|\blocal match requirement\b|\b\d{1,3}(?:\.\d)?% (?:local )?match\b|\bmatch(?:ing)? (?:is|are) required\b", re.I)
PHONE_RE = re.compile(r"\(\d{3}\)\s*\d{3}-\d{4}|\b\d{3}[.-]\d{3}[.-]\d{4}\b")


# ---------- pure helpers (no I/O) ----------

def index_rows(index_url: str, html_text: str) -> dict[str, Any]:
    """{banner, rows: [{title, purpose, href}]} from the index body. Raises when the table or its rows are missing:
    a changed layout must abort the run, not mark every row missing."""
    section = main_section(html_text)
    body = body_div(str(section)) if section is not None else None
    if body is None:
        raise ValueError("MDE index: no mdgov body on the page")
    banner = next((clean(h.get_text(" ")) for h in body.find_all(["h2", "h3"]) if BANNER_RE.search(h.get_text(" "))), None)
    table = next((t for t in body.find_all("table")
                  if t.find("tr") and "financial program" in clean(t.find("tr").get_text(" ")).lower()), None)
    if table is None:
        raise ValueError("MDE index: no Financial Program table on the page")
    rows: list[dict[str, Any]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td"])
        if len(cells) < 2:
            continue
        title = clean(cells[0].get_text(" "))
        if not title:
            continue
        a = cells[0].find("a", href=True)
        rows.append({"title": title, "purpose": clean(cells[1].get_text(" ")) or None,
                     "href": canonical_url(a["href"], index_url) if a else None})
    if not rows:
        raise ValueError("MDE index: the table has no rows")
    return {"banner": banner, "rows": rows}


def entries_for(index_url: str, html_text: str) -> dict[str, dict[str, Any]]:
    data = index_rows(index_url, html_text)
    out: dict[str, dict[str, Any]] = {}
    for row in data["rows"]:
        url = row["href"] or index_url
        facts = {"title": row["title"], "purpose": row["purpose"], "banner": data["banner"], "linked": row["href"] is not None}
        out.setdefault(source_id_for(url), {"url": url, "row": facts})
    return out


def status_fields_for(row: dict[str, Any] | None, main_html: str, today: date) -> dict[str, Any]:
    banner = (row or {}).get("banner")
    if banner:
        if CLOSED_RE.search(banner):
            status, opens_at = "closed", None
            m = REOPEN_RE.search(banner)
            if m:
                ahead, d = future_marker(m.group(1), today)
                if ahead:
                    status, opens_at = "forecasted", d
            return {"status": status, "opens_at": opens_at, "closes_at": None, "closes_at_text": banner, "rolling": None}
        if OPEN_RE.search(banner) and not NEGATION_RE.search(banner):
            m = DATE_RE.search(banner)
            closes_at = parse_text_date(m.group(0)) if m else None
            status = "open" if closes_at is None or closes_at >= today else "unknown"
            return {"status": status, "opens_at": None, "closes_at": closes_at, "closes_at_text": banner, "rolling": None}
    cycle = next((s for s in page_sentences(main_html) if CYCLE_RE.search(s)), None)
    return {"status": "unknown", "opens_at": None, "closes_at": None, "closes_at_text": banner or cycle, "rolling": None}


def applicant_lines_for(row: dict[str, Any] | None, main_html: str) -> list[str]:
    """The Purpose cell first, then the page's applicant sentences (only for a row with a page of its own)."""
    out: list[str] = []
    if row and row.get("purpose"):
        out.append(row["purpose"])
    if row is None or row.get("linked", True):
        for s in page_sentences(main_html):
            if APPLICANT_SENTENCE_RE.search(s) and not NEGATION_RE.search(s) and not PHONE_RE.search(s) and s not in out:
                out.append(s)
    return out


def scrub_phones(main_html: str) -> str:
    """Drop the phone numbers before the body is stored (the WebGrants rule), wherever in the markup they sit."""
    soup = BeautifulSoup(main_html, "html.parser")
    for node in soup.find_all(string=PHONE_RE):
        node.replace_with(PHONE_RE.sub("", str(node)))
    return str(soup)


SCRUB = scrub_phones          # the probe applies it to the index fixture as well


# ---------- the connector ----------

class Mde(MarylandSharePointConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    PASS_THROUGH = PASS_THROUGH

    def index_entries(self, client: httpx.Client) -> dict[str, dict[str, Any]]:
        url = f"{BASE}/programs/water/WQFA/Pages/index.aspx"
        resp = client.get(url)
        resp.raise_for_status()
        return entries_for(url, resp.text)

    def annotate(self, payload: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
        main_html = scrub_phones(payload.get("main_html") or "")
        payload = {**payload, "main_html": main_html, "content_hash": text_hash(main_html)}
        return super().annotate(payload, entry)

    def name_for(self, payload: dict[str, Any]) -> str:
        row = payload.get("row") or {}
        return row.get("title") or super().name_for(payload)

    def status_fields(self, payload: dict[str, Any], today: date) -> dict[str, Any]:
        return status_fields_for(payload.get("row"), payload.get("main_html") or "", today)

    def applicant_lines(self, payload: dict[str, Any]) -> list[str]:
        return applicant_lines_for(payload.get("row"), payload.get("main_html") or "")

    def categories_for(self, payload: dict[str, Any]) -> list[CategoryTag]:
        return [CategoryTag(value="water", source_code="mwifa")]

    def funding_type_for(self, name: str, payload: dict[str, Any]) -> str | None:
        sid = source_id_for(payload.get("url") or "")
        return FUNDING_TYPE_OVERRIDES.get(sid) or funding_type_for(name)

    def normalize(self, raw: RawRecord, today: date | None = None) -> Program:
        program = super().normalize(raw, today)
        row = raw.payload.get("row") or {}
        text = " ".join([row.get("purpose") or ""] + (page_sentences(raw.payload.get("main_html") or "") if row.get("linked", True) else []))
        update: dict[str, Any] = {}
        if row.get("purpose") and program.summary != row["purpose"]:
            update["summary"] = row["purpose"]
        if program.match_required is None and MATCH_RE.search(text):
            update["match_required"] = True
        return program.model_copy(update=update) if update else program


SITE = Mde()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
classify_page = SITE.classify_page

