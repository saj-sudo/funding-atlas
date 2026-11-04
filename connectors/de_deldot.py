"""Delaware Department of Transportation connector: the two programs with a call for applications from outside the
department, the Transportation Alternatives Program (overview and apply pages) and Safe Routes to School.
Hand-listed; three GETs a run; on the hand-list base (`connectors/hand_list.py`) since 12.1. See
docs/connectors/de_deldot.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from bs4 import BeautifulSoup, Tag

from connectors.hand_list import (
    DATE_ORDINAL_RE,
    Blocks,
    HandListConnector,
    applicant_tags,
    blocks_from,
    first_p,
    first_sentence,
    label_lines,
    last_date,
    soup,
)
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for
from pipeline.models import RawRecord

CONNECTOR = "de_deldot"
BASE = "https://deldot.gov"
PAGES: dict[str, tuple[str, ...]] = {
    "tap": ("/Programs/tap/", "/Programs/tap/index.shtml?dc=apply"),
    "srts": ("/Programs/srts/index.shtml",),
}
AGENCY = "Department of Transportation"
AGENCY_CODE = "DE-DELDOT"
JURISDICTION = "DE"
TITLE_SUFFIX = " - Delaware Department of Transportation"

LABEL_RE = re.compile(r"sponsors? may include|eligible (?:applicants?|sponsors?)|who (?:may|can) apply", re.I)
APPLICANT_RE = re.compile(r"\b(?:can receive funding|may apply|eligible to apply|eligible entity|project sponsors?)\b", re.I)
CYCLE_RE = re.compile(r"\b(?:deadline|now being accepted|applications? (?:are|will be) (?:accepted|due)|call-?out|now closed|is closed)\b", re.I)
CLOSED_RE = re.compile(r"\b(?:now closed|is closed)\b", re.I)
FEDERAL_RE = re.compile(r"\b(?:Bipartisan Infrastructure Law|Surface Transportation Block Grant|federal(?:ly)? (?:fund\w*|program)|Federal Highway Administration)\b", re.I)
MATCH_RE = re.compile(r"\bup to \d{2,3}% of (?:a|the) project\b|\bmatch(?:ing)? (?:requirement|funds?)\b", re.I)
CONTACT_RE = re.compile(r"\b\d{3}[.-]\d{3}[.-]\d{4}\b|@|^contact us$|^toll free", re.I)


# ---------- parsing (no I/O) ----------

def _content(doc: BeautifulSoup) -> Tag:
    main = doc.select_one("#main_content") or doc
    for side in main.select("#leftCol, .panel-group, #sidebox"):
        side.decompose()
    return main


def parse_page(page_html: str) -> dict[str, Any]:
    """title (from <title>), blocks [(kind, text)]: label, p, li. Contact lines dropped."""
    doc = soup(page_html)
    title = clean(doc.title.get_text(" ")) if doc.title else ""
    title = title[: -len(TITLE_SUFFIX)] if title.endswith(TITLE_SUFFIX) else title
    blocks = blocks_from(_content(doc), ["h2", "h3", "h4", "p", "li"], drop_re=CONTACT_RE)
    return {"title": title, "blocks": blocks}


def applicant_lines(blocks: Blocks) -> list[str]:
    return label_lines(blocks, LABEL_RE, APPLICANT_RE, keep_kinds=("li",), keep_label=True)


def cycle_sentence(blocks: Blocks) -> str | None:
    return first_sentence(blocks, CYCLE_RE)


# ---------- status ----------

def closes_at_for(sentence: str | None) -> date | None:
    return last_date(sentence, DATE_ORDINAL_RE)


def status_for(sentence: str | None, closes_at: date | None, today: date) -> str:
    if sentence and CLOSED_RE.search(sentence):
        return "closed"
    if closes_at and closes_at >= today:
        return "open"
    return "unknown"


# ---------- the connector ----------

class Deldot(HandListConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = JURISDICTION
    PAGES = PAGES

    def urls_for(self, slug: str, spec: tuple[str, ...]) -> list[str]:
        return [BASE + path for path in spec]

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: tuple[str, ...], pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        return [(slug, {"paths": list(spec), "pages": pages})]

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        pages = raw.payload["pages"]
        blocks = [tuple(b) for page in pages for b in page.get("blocks", [])]
        text = " ".join(t for _, t in blocks)
        name = clean(pages[0].get("title", "")) if pages else raw.source_id
        sentence = cycle_sentence(blocks)
        closes_at = closes_at_for(sentence)
        lines = applicant_lines(blocks)
        return dict(
            source_url=BASE + raw.payload["paths"][0],
            name=name or raw.source_id,
            funding_type=funding_type_for(name) or "grant",
            funding_source="pass_through" if FEDERAL_RE.search(text) else "direct",
            match_required=True if MATCH_RE.search(text) else None,
            status=status_for(sentence, closes_at, today),
            opens_at=None,
            closes_at=closes_at,
            closes_at_text=sentence,
            rolling=None,
            summary=first_p(blocks),
            eligibility_text="\n".join(lines) or None,
            eligibility_structured=None,
            applicant_types=applicant_tags(lines),
            categories=[],
        )


SITE = Deldot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
