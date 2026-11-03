"""Maryland Department of Emergency Management connector: the grant roster plus two hand-added program pages.

Source: https://mdem.maryland.gov (SharePoint, the state's `mdgov` theme; shared mechanics in
connectors/maryland_sharepoint.py). `/Pages/grants.aspx` ("GRANT OPPORTUNITY ROSTER", a page that says it is still in
development) renders a SharePoint list as one `<table class="ms-listviewtable">`: per item a title, a description with
a "[Learn More]" link, a "Who is Eligible?" cell, `Applications Open?: Yes|No`, an apply link and an
`Application Deadline`. The list's XML export is under `/_vti_bin/`, which robots.txt disallows, so the table is read.
A roster item is the record and lives at its Learn More page; two program pages the roster does not list (the
Resilient Maryland Revolving Loan Fund and FEMA Public Assistance) are hand-added.

Status: the roster's own field first (`No` is closed, `Yes` with a deadline still ahead is open); a `Yes` with a past
or blank deadline is a stale row and the page's dated window decides (open while its end date is ahead, `unknown`
after, the date kept); a page with no roster facts and no window is `unknown`. See docs/connectors/md_mdem.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import NEGATION_RE, clean, funding_type_for, sentences
from connectors.maryland_sharepoint import (
    DATE_RE,
    MarylandSharePointConnector,
    canonical_url,
    page_h1,
    page_sentences,
    parse_text_date,
    source_id_for,
    summary_for,
    text_hash,
)
from pipeline.models import CategoryTag, Program, RawRecord

CONNECTOR = "md_mdem"
BASE = "https://mdem.maryland.gov"
AGENCY = "Maryland Department of Emergency Management"
AGENCY_CODE = "MD-MDEM"

INDEX_PATH = "pages/grants.aspx"
INDEX_PATHS: tuple[str, ...] = (INDEX_PATH,)
# Programs the roster does not list (the roster says it is incomplete). Beneficiary lists and membership programs on
# the same menu are not programs; see the doc.
HAND_ADDED: dict[str, dict[str, Any]] = {
    "pages/rlf-fund.aspx": {"url": f"{BASE}/Pages/rlf-fund.aspx", "roster": None, "listed": False},
    "community/pages/public-assistance-program.aspx": {
        "url": f"{BASE}/community/Pages/Public-Assistance-Program.aspx", "roster": None, "listed": False,
    },
}
# Pages that name their federal source. Each number is carried by Grants.gov records of the same name in the registry
# (checked 2026-11-03): 97.008 Non-Profit Security Program, 97.029 Flood Mitigation Assistance, 97.036 Disaster
# Grants - Public Assistance. The loan fund is the state's own money (STORM Act capitalised it) and stays direct.
PASS_THROUGH: dict[str, list[str]] = {
    "pages/nonprofit-security-grant-program.aspx": ["97.008"],
    "community/pages/mitigation.aspx": ["97.029"],
    "community/pages/public-assistance-program.aspx": ["97.036"],
}

LEARN_MORE_RE = re.compile(r"\[?\s*learn more\s*\]?", re.I)
WINDOW_RE = re.compile(r"\baccepted\b[^.]*\bfrom\b[^.]*\b(?:until|through|to)\b", re.I)
ACCEPTING_RE = re.compile(r"\b(?:accepting|accepted|accepts)\b", re.I)
ROLLING_RE = re.compile(r"year-round|at any time|rolling basis", re.I)
APPLICANT_SENTENCE_RE = re.compile(
    r"\beligible\b|\bmay apply\b|\bavailable to\b|\bassistance to\b|\bloans?\b(?: \([^)]*\))? to\b", re.I
)
GRANT_WORD_RE = re.compile(r"\bgrant (?:assistance|funding|program)s?\b|\bcompetitive grant\b", re.I)
CONTACT_RE = re.compile(r"@|\[email|__cf_email__|\b\d{3}[.-]\d{3}[.-]\d{4}\b|\bcontact us\b", re.I)
CLAUSE_RE = re.compile(r"\([^)]*\)")


# ---------- pure helpers (no I/O) ----------

def _cell_lines(td: Tag) -> list[str]:
    """The text of one roster cell as lines: SharePoint separates lines with <br> and nested <div>s."""
    for br in td.find_all("br"):
        br.replace_with("\n")
    for div in td.find_all("div"):
        div.insert_before("\n")
    return [clean(line) for line in td.get_text("").split("\n") if clean(line)]


def roster_rows(index_url: str, html_text: str) -> dict[str, dict[str, Any]]:
    """source_id -> {url, roster, listed} for every item of the roster table. Raises when the table or its items are
    missing: a changed layout must abort the run, not mark every row missing."""
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.select_one("table.ms-listviewtable")
    if table is None:
        raise ValueError("MDEM roster: no ms-listviewtable on the page")
    out: dict[str, dict[str, Any]] = {}
    item: dict[str, Any] | None = None
    cells: list[Tag] = []

    def finish() -> None:
        if item is None:
            return
        facts = _facts(item["title"], cells)
        url = canonical_url(facts.pop("learn_more"), index_url) if facts.get("learn_more") else index_url
        out.setdefault(source_id_for(url), {"url": url, "roster": facts, "listed": True})

    for td in table.find_all("td"):
        classes = td.get("class") or []
        if "ms-vb-title" in classes:
            finish()
            item, cells = {"title": clean(td.get_text(" "))}, []
        elif "ms-vb-tall" in classes and item is not None:
            cells.append(td)
    finish()
    if not out:
        raise ValueError("MDEM roster: the table has no items")
    return out


def _facts(title: str, cells: list[Tag]) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "title": title, "description": None, "learn_more": None, "eligible_lines": [],
        "applications_open": None, "apply_url": None, "deadline": None, "deadline_text": None,
    }
    for td in cells:
        text = clean(td.get_text(" "))
        label, _, value = text.partition(":")
        key = label.strip().lower()
        if key.startswith("who is eligible"):
            lines = _cell_lines(td)
            facts["eligible_lines"] = [ln for ln in lines if not ln.lower().startswith("who is eligible")]
        elif key.startswith("applications open"):
            v = value.strip().lower()
            facts["applications_open"] = True if v.startswith("yes") else False if v.startswith("no") else None
        elif key == "apply":
            a = td.find("a", href=True)
            facts["apply_url"] = a["href"] if a else None
        elif key.startswith("application deadline"):
            facts["deadline_text"] = value.strip() or None
            d = parse_date(value.strip().split()[0]) if value.strip() else None
            facts["deadline"] = d.isoformat() if d else None
        else:
            a = next((a for a in td.find_all("a", href=True) if LEARN_MORE_RE.search(a.get_text(" "))), None)
            facts["learn_more"] = a["href"] if a else None
            facts["description"] = clean(LEARN_MORE_RE.sub("", text)) or None
    return facts


def scrub_contacts(main_html: str) -> str:
    """Drop the people and e-mails the page's contact block names before the body is stored."""
    soup = BeautifulSoup(main_html, "html.parser")
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("mailto:") or "email-protection" in a["href"]:
            a.decompose()
    for el in soup.find_all(["p", "div", "li", "h2", "h3"]):
        own = " ".join(c for c in el.find_all(string=True, recursive=False))
        if CONTACT_RE.search(own) and len(clean(el.get_text(" "))) < 200:
            el.decompose()
    return str(soup)


SCRUB = scrub_contacts        # the probe applies it to the index fixture as well


def roster_clauses(lines: list[str]) -> list[str]:
    """Each eligibility line as clauses: the text outside parentheses, then each parenthetical; negated clauses dropped."""
    out: list[str] = []
    for line in lines:
        parts = [CLAUSE_RE.sub(" ", line)] + CLAUSE_RE.findall(line)
        for part in parts:
            for s in sentences(part.strip("() ")):
                s = re.sub(r"^\d+\.\s*", "", s)
                if s and not NEGATION_RE.search(s) and s not in out:
                    out.append(s)
    return out


def window_for(sents: list[str]) -> tuple[str | None, date | None, date | None]:
    """(sentence, opens_at, closes_at) for the first 'accepted from <date> until <date>' sentence."""
    for s in sents:
        if WINDOW_RE.search(s):
            dates = [parse_text_date(m.group(0)) for m in DATE_RE.finditer(s)]
            dates = [d for d in dates if d]
            return s, (dates[0] if dates else None), (dates[-1] if dates else None)
    return None, None, None


def status_fields_for(roster: dict[str, Any] | None, main_html: str, today: date) -> dict[str, Any]:
    sents = page_sentences(main_html)
    window, opens_at, window_end = window_for(sents)
    texts: list[str] = []
    if roster:
        texts.append(f"Applications Open?: {'Yes' if roster.get('applications_open') else 'No'}"
                     + (f"; Application Deadline: {roster['deadline_text']}" if roster.get("deadline_text") else ""))
    if window:
        texts.append(window)
    deadline = parse_date(roster.get("deadline")) if roster else None

    if roster and roster.get("applications_open") is False:
        status, closes_at = "closed", deadline
    elif roster and roster.get("applications_open") and deadline and deadline >= today:
        status, closes_at = "open", deadline
    elif window_end:
        status, closes_at = ("open" if window_end >= today else "unknown"), window_end
    else:
        status, closes_at = "unknown", None
    rolling = None
    if status == "unknown" and not roster:
        accepting = next((s for s in sents if ACCEPTING_RE.search(s) and ROLLING_RE.search(s) and not NEGATION_RE.search(s)), None)
        if accepting:
            status, rolling = "open", True
            texts.append(accepting)
    return {
        "status": status,
        "opens_at": opens_at if status in ("open", "unknown") and window else None,
        "closes_at": closes_at,
        "closes_at_text": " ".join(texts) or None,
        "rolling": rolling,
    }


def applicant_lines_for(roster: dict[str, Any] | None, main_html: str) -> list[str]:
    if roster and roster.get("eligible_lines"):
        clauses = roster_clauses(roster["eligible_lines"])
        if clauses:
            return clauses
    out: list[str] = []
    for s in page_sentences(main_html):
        if APPLICANT_SENTENCE_RE.search(s) and not NEGATION_RE.search(s) and not CONTACT_RE.search(s) and s not in out:
            out.append(s)
    return out


# ---------- the connector ----------

class Mdem(MarylandSharePointConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    PASS_THROUGH = PASS_THROUGH

    def index_entries(self, client: httpx.Client) -> dict[str, dict[str, Any]]:
        url = f"{BASE}/{INDEX_PATH}"
        resp = client.get(url)
        resp.raise_for_status()
        entries = roster_rows(url, resp.text)
        for sid, entry in HAND_ADDED.items():
            entries.setdefault(sid, dict(entry))
        return entries

    def annotate(self, payload: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
        main_html = scrub_contacts(payload.get("main_html") or "")
        payload = {**payload, "main_html": main_html, "content_hash": text_hash(main_html)}
        return super().annotate(payload, entry)

    def name_for(self, payload: dict[str, Any]) -> str:
        roster = payload.get("roster") or {}
        return roster.get("title") or page_h1(payload.get("main_html") or "") or clean(payload.get("title"))

    def status_fields(self, payload: dict[str, Any], today: date) -> dict[str, Any]:
        return status_fields_for(payload.get("roster"), payload.get("main_html") or "", today)

    def applicant_lines(self, payload: dict[str, Any]) -> list[str]:
        return applicant_lines_for(payload.get("roster"), payload.get("main_html") or "")

    def categories_for(self, payload: dict[str, Any]) -> list[CategoryTag]:
        return [CategoryTag(value="public_safety", source_code="mdem")]

    def funding_type_for(self, name: str, payload: dict[str, Any]) -> str | None:
        ft = funding_type_for(name)
        if ft:
            return ft
        roster = payload.get("roster") or {}
        text = " ".join([roster.get("description") or ""] + page_sentences(payload.get("main_html") or ""))
        return "grant" if GRANT_WORD_RE.search(text) else None

    def normalize(self, raw: RawRecord, today: date | None = None) -> Program:
        program = super().normalize(raw, today)
        roster = raw.payload.get("roster") or {}
        summary = roster.get("description") or summary_for(raw.payload.get("description"))
        return program.model_copy(update={"summary": summary}) if summary != program.summary else program


SITE = Mdem()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
classify_page = SITE.classify_page


def index_fixture_html(html_text: str) -> str:
    """What the probe saves for the roster page: the whole `main#mdgovMain`, because the table is in the second section."""
    soup = BeautifulSoup(html_text, "html.parser")
    main = soup.select_one("main#mdgovMain") or soup
    return str(main)
