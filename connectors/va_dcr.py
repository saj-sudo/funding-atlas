"""Virginia Department of Conservation and Recreation connector: the six recreation and land conservation grant pages.

Source: https://www.dcr.virginia.gov, a hand-built site; the "Recreation Oriented Grants" index links six program
pages, read by hand list (six GETs a run). Each page is prose: a round headline ("2026 LWCF Grant Round is now
closed."), paragraphs and, on some, a labelled list of who may apply. Status comes from the round sentence, applicants
from the applicant sentences and the labelled list, the federal wording decides pass_through. See
docs/connectors/va_dcr.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup, Comment, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "va_dcr"
BASE = "https://www.dcr.virginia.gov"
PAGES: dict[str, str] = {
    "lwcf": "/recreational-planning/lwcf",
    "orlp": "/recreational-planning/orlp",
    "trailfnd": "/recreational-planning/trailfnd",
    "trail-access-program": "/recreational-planning/trail-access-program",
    "abpp-grants": "/recreational-planning/abpp-grants",
    "vlcf": "/land-conservation/vlcf",
}
RECREATION_SECTION = "/recreational-planning/"
RECREATION_LABEL = "Recreation Oriented Grants"
AGENCY = "Department of Conservation and Recreation"
AGENCY_CODE = "VA-DCR"
JURISDICTION = "VA"
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

ELIGIBILITY_LABEL_RE = re.compile(r"eligib", re.I)
APPLICANT_SENTENCE_RE = re.compile(
    r"\b(?:eligible applicants?|entities eligible|funding may be awarded to|eligible to apply|may apply"
    r"|(?:organizations?|governments?|entities|agencies|authorities|bodies|trusts|applicants?)\b[^.]*\bare (?:also )?eligible)\b", re.I)
# A sentence that states the round's position comes first; a sentence that merely mentions a grant round second.
STRONG_ROUND_RE = re.compile(
    r"\b(?:now closed|is closed|closed on|(?:round|grant) closed|deadline|are due|accepting applications"
    r"|accepted (?:pre)?applications|not anticipated until)\b", re.I)
ROUND_RE = re.compile(r"\bgrant round\b", re.I)
CLOSED_RE = re.compile(r"\bclosed\b", re.I)
OPEN_RE = re.compile(r"\b(?:now open|accepting applications|are due)\b", re.I)
DUE_RE = re.compile(r"\b(?:closed on|due|deadline|by|through|until)\b", re.I)
FULL_DATE_RE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b")
FEDERAL_RE = re.compile(r"\bfederal (?:reimbursement program|funding|program)\b|\bpass-through entity\b|\bFederal Highway Administration\b", re.I)
MATCH_RE = re.compile(r"\b\d{2}[-/]\d{2}\s*%?\s*matching\b|\bmatching reimbursement\b", re.I)
QUESTIONS_RE = re.compile(r"^questions\??$", re.I)
LABEL_MAX_CHARS = 80


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


# ---------- parsing (no I/O) ----------

def _is_label(el: Tag) -> bool:
    text = clean(el.get_text(" "))
    if el.name in ("h2", "h3", "h4"):
        return True
    bold = el.find(["strong", "b"])
    return bool(text) and len(text) <= LABEL_MAX_CHARS and bold is not None and clean(bold.get_text(" ")) == text


def parse_page(page_html: str) -> dict[str, Any]:
    """title, blocks (tag, text) in order from `#page`, stopping at a "Questions?" heading (a named contact)."""
    soup = BeautifulSoup(page_html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    page = soup.select_one("main #page") or soup.select_one("#page") or soup
    title = clean(page.h1.get_text(" ")) if page.h1 else ""
    blocks: list[tuple[str, str]] = []
    for el in page.find_all(["h2", "h3", "h4", "p", "li"]):
        text = clean(el.get_text(" ")) if el.name != "li" else clean(" ".join(el.find_all(string=True, recursive=False)) or el.get_text(" "))
        if el.name in ("h2", "h3", "h4") and QUESTIONS_RE.match(text):
            break
        if text:
            blocks.append((el.name, text, ) if not _is_label(el) else ("label", text))
    return {"title": title, "blocks": blocks}


def applicant_lines(blocks: list[tuple[str, str]]) -> list[str]:
    """The list items and paragraphs under a label that mentions eligibility, plus every sentence that says who
    may apply."""
    out: list[str] = []
    on = False
    for tag, text in blocks:
        if tag == "label":
            on = bool(ELIGIBILITY_LABEL_RE.search(text))
            continue
        if on and tag in ("li", "p"):
            out.append(text)
            continue
        for s in sentences(text):
            if APPLICANT_SENTENCE_RE.search(s) and s not in out:
                out.append(s)
    return out


def round_sentence(blocks: list[tuple[str, str]]) -> str | None:
    for pattern in (STRONG_ROUND_RE, ROUND_RE):
        for _tag, text in blocks:
            for s in sentences(text):
                if pattern.search(s):
                    return s
    return None


def summary_for(blocks: list[tuple[str, str]]) -> str | None:
    """The first paragraph (a round headline is a label, not a paragraph, and is skipped by its tag)."""
    for tag, text in blocks:
        if tag == "p":
            return text
    return None


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The six pages. One that cannot be read falls back to the stored copy, or is skipped."""
    prior = prior or {}
    records: list[RawRecord] = []
    with _client() as client:
        for i, (slug, path) in enumerate(PAGES.items()):
            if limit and i >= limit:
                break
            if i:
                time.sleep(DELAY_S)
            try:
                page = parse_page(_get(client, BASE + path))
            except httpx.HTTPError:
                if slug in prior:
                    records.append(RawRecord(source_connector=CONNECTOR, source_id=slug, payload=prior[slug]))
                continue
            records.append(RawRecord(source_connector=CONNECTOR, source_id=slug, payload={"path": path, "page": page}))
    return records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A hand-listed page that could not be read: unknown, no request."""
    return {"status": "unknown"}


# ---------- normalize ----------

def closes_at_for(sentence: str | None) -> date | None:
    if not sentence or not DUE_RE.search(sentence):
        return None
    dates = [parse_date(m) for m in FULL_DATE_RE.findall(sentence)]
    dates = [d for d in dates if d]
    return dates[-1] if dates else None


def status_for(sentence: str | None, closes_at: date | None, today: date) -> str:
    if not sentence:
        return "unknown"
    if CLOSED_RE.search(sentence):
        return "closed"
    if OPEN_RE.search(sentence) and closes_at and closes_at >= today:
        return "open"
    return "unknown"


def applicant_tags(lines: list[str]) -> list[ApplicantTag]:
    kept = [s for line in lines for s in sentences(line) if not NEGATION_RE.search(s)]
    return applicant_types_for(kept or None)


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    page, path = raw.payload["page"], raw.payload.get("path", PAGES.get(raw.source_id, "/" + raw.source_id))
    today = today or date.today()
    blocks = [tuple(b) for b in page.get("blocks", [])]
    text = " ".join(t for _, t in blocks)
    sentence = round_sentence(blocks)
    closes_at = closes_at_for(sentence)
    lines = applicant_lines(blocks)
    name = clean(page.get("title", "")) or raw.source_id
    categories = [CategoryTag(value="parks", source_code=RECREATION_LABEL)] if path.startswith(RECREATION_SECTION) else []
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=BASE + path,
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(name) or "grant",
        funding_source="pass_through" if FEDERAL_RE.search(text) else "direct",
        amount_min=None,
        amount_max=None,
        match_required=True if MATCH_RE.search(text) else None,
        match_pct=None,
        status=status_for(sentence, closes_at, today),
        opens_at=None,
        closes_at=closes_at,
        closes_at_text=sentence,
        rolling=None,
        summary=summary_for(blocks),
        eligibility_text="\n".join(lines) or None,
        eligibility_structured=None,
        applicant_types=applicant_tags(lines),
        categories=categories,
        alns=[],
    )
