"""The Vermont agency base: what every vermont.gov Drupal 10 agency page shares (milestone 12.6).

Vermont's agencies (ACCD, VTrans, Forests Parks and Recreation, Emergency Management) all run vermont.gov's USWDS
Drupal theme: the title is the `h1`, the page's own text is the body field of the main content block. This module
reads that body into `(kind, text)` blocks with the hand-list helpers, and holds the Vermont status table and the field
mapping; an agency module sets its constants, its page dict and its category label. See docs/connectors/vermont.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.grants_gov import parse_date
from connectors.hand_list import (
    Blocks,
    HandListConnector,
    applicant_tags,
    blocks_from,
    soup,
)
from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for, portal_categories
from pipeline.models import CategoryTag, RawRecord

JURISDICTION = "VT"
BODY_SELECTOR = ".block-system-main-block .field--name-body"
LABEL_MAX_CHARS = 90

_MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
# "November 20, 2026", "December 4th, 2026", "Sunday, December 13, 2026" (the weekday is outside the match), and the
# one numeric form a page uses, "11/20/2026".
DATE_RE = re.compile(rf"\b{_MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b|\b\d{{1,2}}/\d{{1,2}}/\d{{4}}\b")
_ORDINAL_RE = re.compile(r"(\d)(?:st|nd|rd|th)")

# VTrans's accessibility notice tops every page; contact lines name a person.
DROP_RE = re.compile(r"committed to ensuring accessibility|Telephone:|Tel:|E-mail|e-mail|@vermont\.gov", re.I)

DUE_RE = re.compile(r"\b(?:due|deadline)\b", re.I)
NOT_DEADLINE_RE = re.compile(r"\b(?:closeout|close-out|report(?:s|ing)?|grant term|implementation period|reimbursement)\b", re.I)
OPENS_RE = re.compile(r"\bapplications?\s+opens?\b|\bpre-applications?\s+open\b|\bopen(?:s)?\s+(?:on|by)\b", re.I)
OPEN_RE = re.compile(r"\b(?:is|are)\s+now\s+open\b|\bnow\s+accepting\b|\baccepting\s+applications\b", re.I)
CLOSED_RE = re.compile(r"\b(?:is|are)\s+(?:now\s+)?closed\b|\bclosed\s+for\s+applications\b|\bno\s+longer\s+accepting\b", re.I)

# A label that heads the list of who may apply ("Applicant Eligibility"); a label about eligible projects is not one.
ELIGIBILITY_LABEL_RE = re.compile(r"\bapplicant eligibility\b|\bwho (?:is|are|may be) eligible\b|\bwho (?:can|may) apply\b"
                                  r"|\beligible applicants\b", re.I)
APPLICANT_SENTENCE_RE = re.compile(
    r"\beligible applicants?\b|\beligibility\b[^.]*\blimited to\b|\b(?:funds?|funding|grants?)\b[^.]*\bavailable to\b"
    r"|\b(?:grant|grants|grant funding|funding)\s+to\s+municipalit|\bmay apply\b|\beligible to apply\b"
    r"|\b(?:is|are) eligible for funding\b|\bfor local municipalities\b", re.I)
SHORT_ITEM = 160
# "Any Vermont town, city (except Burlington), ... is eligible for funding": the shared negation guard drops a sentence
# with "except" in it, so a parenthetical exclusion is removed before tagging (the sentence itself is kept as written).
EXCLUSION_RE = re.compile(r"\s*\([^)]*\bexcept\b[^)]*\)", re.I)
FEDERAL_RE = re.compile(
    r"\bFederal Highway Administration\b|\bFHWA\b|\bFEMA\b|\bFederal Emergency Management Agency\b|\bHUD\b"
    r"|\bHousing and Urban Development\b|\bNational Park Service\b|\bfederally funded\b", re.I)
# FPR states the money in a "Funding source:" line; where a page has one, it alone decides (VOREC's example projects
# mention a "FEMA buyout property", which says nothing about VOREC's own money).
FUNDING_SOURCE_RE = re.compile(r"^funding source:", re.I)
FEDERAL_LINE_RE = re.compile(r"\bfederal\b|\bFHWA\b|\bFEMA\b|\bHUD\b|\bNational Park Service\b", re.I)
# A deadline's date sits next to its word ("are due November 20, 2026", "December 2, 2026 at 6 p.m. - Application
# Due"); a date further off in the sentence is another fact ("July 23, 2024: See the Amended Notice ... deadlines").
NEAR_CHARS = 40
MATCH_RE = re.compile(r"\bmatch(?:ing)?\b[^.]*\brequired\b|\brequire[sd]?\b[^.]*\bmatch\b", re.I)
MATCH_NOT_RE = re.compile(r"\bno match\b|\bmatch (?:is )?not required\b", re.I)


# ---------- parsing (no I/O) ----------

def parse_page(page_html: str) -> dict[str, Any]:
    """title and the body's blocks, accessibility notice and contact lines dropped."""
    doc = soup(page_html)
    body = doc.select_one(BODY_SELECTOR)
    title = clean(doc.h1.get_text(" ")) if doc.h1 else ""
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS) if body else []
    return {"title": title, "blocks": blocks}


def all_sentences(blocks: Blocks) -> list[str]:
    return [s for _, text in blocks for s in sentences(text)]


def first_date(text: str) -> date | None:
    for m in DATE_RE.finditer(text):
        d = parse_date(_ORDINAL_RE.sub(r"\1", m.group(0)))
        if d:
            return d
    return None


def deadline(sents: list[str]) -> tuple[str | None, date | None]:
    """The first sentence that says due or deadline with a date next to the word (not a closeout, report or
    grant-term date)."""
    for s in sents:
        if NOT_DEADLINE_RE.search(s):
            continue
        for due in DUE_RE.finditer(s):
            for m in DATE_RE.finditer(s):
                gap = m.start() - due.end() if m.start() >= due.end() else due.start() - m.end()
                d = parse_date(_ORDINAL_RE.sub(r"\1", m.group(0))) if gap <= NEAR_CHARS else None
                if d:
                    return s, d
    return None, None


def opening(sents: list[str]) -> date | None:
    for s in sents:
        if OPENS_RE.search(s) and not DUE_RE.search(s):
            d = first_date(s)
            if d:
                return d
    return None


def round_for(blocks: Blocks, today: date) -> dict[str, Any]:
    """status, opens_at, closes_at, closes_at_text by the Vermont table (docs/connectors/vermont.md)."""
    sents = all_sentences(blocks)
    due_s, due = deadline(sents)
    opens = opening(sents)
    closed_s = next((s for s in sents if CLOSED_RE.search(s)), None)
    open_s = next((s for s in sents if OPEN_RE.search(s) and not NEGATION_RE.search(s)), None)
    if due and due >= today:
        status, text = ("forecasted" if opens and opens > today else "open"), due_s
    elif closed_s:
        status, text = "closed", closed_s
    elif due:
        # a deadline that has passed outranks undated "now open" wording, which a page keeps until someone edits it
        status, text = "unknown", due_s
    elif open_s:
        status, text = "open", open_s
    else:
        status, text = "unknown", None
    return {"status": status, "opens_at": opens, "closes_at": due, "closes_at_text": text}


def summary_for(blocks: Blocks) -> str | None:
    """The first paragraph that is not a status line."""
    for kind, text in blocks:
        if kind == "p" and not (OPEN_RE.search(text) or CLOSED_RE.search(text) or DUE_RE.search(text)):
            return text
    return None


def applicant_lines(blocks: Blocks) -> list[str]:
    """Short list items under an applicant label, kept whole; from every block (bold labels included: VTrans writes
    its intro bold) the sentences that say who may apply. A paragraph that says neither ends the label's list."""
    out: list[str] = []
    on = False
    for kind, text in blocks:
        if kind == "label":
            on = bool(ELIGIBILITY_LABEL_RE.search(text))
        elif on and kind == "li" and len(text) <= SHORT_ITEM:
            if text not in out:
                out.append(text)
            continue
        hits = [s for s in sentences(text) if APPLICANT_SENTENCE_RE.search(s)]
        if kind == "p" and not hits:
            on = False
        out += [s for s in hits if s not in out]
    return out


def funding_source_for(blocks: Blocks, text: str) -> str:
    line = next((t for _, t in blocks if FUNDING_SOURCE_RE.search(t)), None)
    if line is not None:
        return "pass_through" if FEDERAL_LINE_RE.search(line) else "direct"
    return "pass_through" if FEDERAL_RE.search(text) else "direct"


# ---------- the base ----------

class VermontAgency(HandListConnector):
    """A Vermont agency: set CONNECTOR, BASE, AGENCY, AGENCY_CODE, CATEGORY_LABEL and PAGES (slug -> path)."""

    JURISDICTION = JURISDICTION
    CATEGORY_LABEL: str = ""

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        return [(slug, {"path": spec, "page": pages[0]})]

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        page = raw.payload["page"]
        path = raw.payload.get("path") or self.PAGES.get(raw.source_id, "/" + raw.source_id)
        blocks = [tuple(b) for b in page.get("blocks", [])]
        text = " ".join(t for _, t in blocks)
        name = clean(page.get("title", "")) or raw.source_id
        lines = applicant_lines(blocks)
        match = None if MATCH_NOT_RE.search(text) else (True if MATCH_RE.search(text) else None)
        return dict(
            source_url=self.BASE + path,
            name=name,
            funding_type=funding_type_for(name) or "grant",
            funding_source=funding_source_for(blocks, text),
            match_required=match,
            rolling=None,
            summary=summary_for(blocks),
            eligibility_text="\n".join(lines) or None,
            eligibility_structured=None,
            applicant_types=applicant_tags([EXCLUSION_RE.sub("", line) for line in lines]),
            categories=[CategoryTag(value=v, source_code=self.CATEGORY_LABEL) for v in portal_categories(self.CATEGORY_LABEL)],
            **round_for(blocks, today),
        )
