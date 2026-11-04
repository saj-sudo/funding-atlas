"""Delaware DNREC Environmental Finance connector: the office's twelve grant and loan program pages.

Source: https://dnrec.delaware.gov/environmental-finance/ (WordPress, no robots restrictions). Twelve hand-listed
program pages, each prose with block headings ("Eligible Applicants", "Eligible Projects", "Now Accepting Project
Proposals") and the agency's own "Related Topics" tags. Status from the sentence that states the cycle, applicants
from the labelled passages and applicant sentences, categories from the tags. On the hand-list base
(`connectors/hand_list.py`) since 12.1. See docs/connectors/de_dnrec.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from bs4 import BeautifulSoup, Tag

from connectors.hand_list import (
    DATE_RE,
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
from connectors.text import PORTAL_CATEGORIES, funding_type_for, portal_label
from pipeline.models import CategoryTag, RawRecord

CONNECTOR = "de_dnrec"
BASE = "https://dnrec.delaware.gov/environmental-finance/"
# slug -> kind by the index section the page is listed under (None where the page says both)
PAGES: dict[str, str | None] = {
    "community-water-quality-improvement": "grant", "surface-water-planning-grants": "grant",
    "wastewater-planning-grants": "grant", "asset-management": "grant", "planning-advances": "grant",
    "wastewater-treatment": "loan", "water-quality-improvement": "loan", "stormwater-infrastructure": "loan",
    "land-conservation": "loan", "septic-rehabilitation": "grant", "estuary-programs": "loan",
    "non-point-source-funding": None,
}
AGENCY = "Department of Natural Resources and Environmental Control"
AGENCY_CODE = "DE-DNREC"
JURISDICTION = "DE"

LABEL_RE = re.compile(r"eligible (?:applicants?|sectors?)|^eligibility|who (?:may|can) apply|now accepting", re.I)
APPLICANT_RE = re.compile(r"\b(?:eligible to (?:apply|receive)|may apply|can submit|can receive|municipalit\w*|local governments?|homeowners?|nonprofits?)\b", re.I)
CYCLE_RE = re.compile(
    r"\b(?:now accepting|accepting (?:project )?proposals|submission deadline|deadline|submitted at any time"
    r"|first come|application period|application cycle|one application per|now closed|is closed)\b", re.I)
CLOSED_RE = re.compile(r"\b(?:now closed|is closed)\b", re.I)
OPEN_RE = re.compile(r"\b(?:now accepting|accepting (?:project )?proposals|at any time|first come)\b", re.I)
ROLLING_RE = re.compile(r"\b(?:at any time|first come|rolling)\b", re.I)
MATCH_RE = re.compile(r"\b(?:\d:\d (?:cash )?match|match(?:ing)? (?:requirement|grant|funds?)|cash match)\b", re.I)
CONTACT_RE = re.compile(r"@|\b\d{3}-\d{3}-\d{4}\b|^contact us\b", re.I)
LABEL_MAX_CHARS = 80


# ---------- parsing (no I/O) ----------

def _content(doc: BeautifulSoup) -> Tag:
    main = doc.select_one("#main_content") or doc
    for side in main.select(".col-md-3, #readspeaker_button1, .panel-group"):
        side.decompose()
    return main


def parse_page(page_html: str) -> dict[str, Any]:
    """title, blocks [(kind, text)] in order (kind: label, p, li), tags (Related Topics). Contact lines dropped."""
    doc = soup(page_html)
    content = _content(doc)
    tags = [clean(a.get_text(" ")) for a in content.select("a[rel=tag]")]
    for small in content.find_all("small"):
        small.decompose()
    blocks = blocks_from(content, ["h2", "h3", "h4", "p", "li"], drop_re=CONTACT_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": clean(content.h1.get_text(" ")) if content.h1 else (clean(doc.h1.get_text(" ")) if doc.h1 else ""),
            "blocks": blocks, "tags": tags}


def applicant_lines(blocks: Blocks) -> list[str]:
    return label_lines(blocks, LABEL_RE, APPLICANT_RE)


def cycle_sentence(blocks: Blocks) -> str | None:
    return first_sentence(blocks, CYCLE_RE)


# ---------- status ----------

def status_for(sentence: str | None, closes_at: date | None, today: date) -> str:
    if not sentence:
        return "unknown"
    if CLOSED_RE.search(sentence):
        return "closed"
    if OPEN_RE.search(sentence) or (closes_at and closes_at >= today):
        return "open"
    return "unknown"


def closes_at_for(sentence: str | None) -> date | None:
    return last_date(sentence, DATE_RE)


def tag_categories(tags: list[str]) -> list[CategoryTag]:
    """Only the tags the shared table knows; `finance` and `grants` are not topics."""
    out: list[CategoryTag] = []
    for tag in tags:
        for value in PORTAL_CATEGORIES.get(portal_label(tag), ()):
            if all(not (c.value == value and c.source_code == tag) for c in out):
                out.append(CategoryTag(value=value, source_code=tag))
    return out


# ---------- the connector ----------

class Dnrec(HandListConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = JURISDICTION
    PAGES = PAGES

    def urls_for(self, slug: str, spec: str | None) -> list[str]:
        return [f"{BASE}{slug}/"]

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        page = raw.payload["page"]
        blocks = [tuple(b) for b in page.get("blocks", [])]
        text = " ".join(t for _, t in blocks)
        name = clean(page.get("title", "")) or raw.source_id
        sentence = cycle_sentence(blocks)
        closes_at = closes_at_for(sentence)
        lines = applicant_lines(blocks)
        return dict(
            source_url=f"{BASE}{raw.source_id}/",
            name=name,
            funding_type=PAGES.get(raw.source_id) or funding_type_for(name),
            funding_source="direct",
            match_required=True if MATCH_RE.search(text) else None,
            status=status_for(sentence, closes_at, today),
            opens_at=None,
            closes_at=closes_at,
            closes_at_text=sentence,
            rolling=True if sentence and ROLLING_RE.search(sentence) else None,
            summary=first_p(blocks),
            eligibility_text="\n".join(lines) or None,
            eligibility_structured={"topics": page["tags"]} if page.get("tags") else None,
            applicant_types=applicant_tags(lines),
            categories=tag_categories(page.get("tags", [])),
        )


SITE = Dnrec()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
