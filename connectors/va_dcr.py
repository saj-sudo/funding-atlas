"""Virginia Department of Conservation and Recreation connector: the six recreation and land conservation grant pages.

Source: https://www.dcr.virginia.gov, a hand-built site; the "Recreation Oriented Grants" index links six program
pages, read by hand list (six GETs a run). Each page is prose: a round headline ("2026 LWCF Grant Round is now
closed."), paragraphs and, on some, a labelled list of who may apply. Status comes from the round sentence, applicants
from the applicant sentences and the labelled list, the federal wording decides pass_through. On the hand-list base
(`connectors/hand_list.py`) since 12.1. See docs/connectors/va_dcr.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.hand_list import (
    DATE_RE,
    Blocks,
    HandListConnector,
    applicant_tags,
    blocks_from,
    first_sentence,
    label_lines,
    last_date,
    soup,
)
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for
from pipeline.models import CategoryTag, RawRecord

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
FEDERAL_RE = re.compile(r"\bfederal (?:reimbursement program|funding|program)\b|\bpass-through entity\b|\bFederal Highway Administration\b", re.I)
MATCH_RE = re.compile(r"\b\d{2}[-/]\d{2}\s*%?\s*matching\b|\bmatching reimbursement\b", re.I)
QUESTIONS_RE = re.compile(r"^questions\??$", re.I)
LABEL_MAX_CHARS = 80


# ---------- parsing (no I/O) ----------

def parse_page(page_html: str) -> dict[str, Any]:
    """title, blocks (tag, text) in order from `#page`, stopping at a "Questions?" heading (a named contact)."""
    doc = soup(page_html)
    page = doc.select_one("main #page") or doc.select_one("#page") or doc
    title = clean(page.h1.get_text(" ")) if page.h1 else ""
    blocks = blocks_from(page, ["h2", "h3", "h4", "p", "li"], stop_re=QUESTIONS_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


def applicant_lines(blocks: Blocks) -> list[str]:
    """The list items and paragraphs under a label that mentions eligibility, plus every sentence that says who
    may apply."""
    return label_lines(blocks, ELIGIBILITY_LABEL_RE, APPLICANT_SENTENCE_RE, keep_kinds=("li", "p"))


def round_sentence(blocks: Blocks) -> str | None:
    return first_sentence(blocks, STRONG_ROUND_RE) or first_sentence(blocks, ROUND_RE)


def summary_for(blocks: Blocks) -> str | None:
    """The first paragraph (a round headline is a label, not a paragraph, and is skipped by its tag)."""
    for tag, text in blocks:
        if tag == "p":
            return text
    return None


# ---------- status ----------

def closes_at_for(sentence: str | None) -> date | None:
    if not sentence or not DUE_RE.search(sentence):
        return None
    return last_date(sentence, DATE_RE)


def status_for(sentence: str | None, closes_at: date | None, today: date) -> str:
    if not sentence:
        return "unknown"
    if CLOSED_RE.search(sentence):
        return "closed"
    if OPEN_RE.search(sentence) and closes_at and closes_at >= today:
        return "open"
    return "unknown"


# ---------- the connector ----------

class Dcr(HandListConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = JURISDICTION
    PAGES = PAGES

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        return [(slug, {"path": spec, "page": pages[0]})]

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        page, path = raw.payload["page"], raw.payload.get("path", PAGES.get(raw.source_id, "/" + raw.source_id))
        blocks = [tuple(b) for b in page.get("blocks", [])]
        text = " ".join(t for _, t in blocks)
        sentence = round_sentence(blocks)
        closes_at = closes_at_for(sentence)
        lines = applicant_lines(blocks)
        name = clean(page.get("title", "")) or raw.source_id
        categories = [CategoryTag(value="parks", source_code=RECREATION_LABEL)] if path.startswith(RECREATION_SECTION) else []
        return dict(
            source_url=BASE + path,
            name=name,
            funding_type=funding_type_for(name) or "grant",
            funding_source="pass_through" if FEDERAL_RE.search(text) else "direct",
            match_required=True if MATCH_RE.search(text) else None,
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
        )


SITE = Dcr()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
