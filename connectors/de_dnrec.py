"""Delaware DNREC Environmental Finance connector: the office's twelve grant and loan program pages.

Source: https://dnrec.delaware.gov/environmental-finance/ (WordPress, no robots restrictions). Twelve hand-listed
program pages, each prose with block headings ("Eligible Applicants", "Eligible Projects", "Now Accepting Project
Proposals") and the agency's own "Related Topics" tags. Status from the sentence that states the cycle, applicants
from the labelled passages and applicant sentences, categories from the tags. See docs/connectors/de_dnrec.md.
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
from connectors.text import PORTAL_CATEGORIES, applicant_types_for, funding_type_for, portal_label
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

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
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

LABEL_RE = re.compile(r"eligible (?:applicants?|sectors?)|^eligibility|who (?:may|can) apply|now accepting", re.I)
APPLICANT_RE = re.compile(r"\b(?:eligible to (?:apply|receive)|may apply|can submit|can receive|municipalit\w*|local governments?|homeowners?|nonprofits?)\b", re.I)
CYCLE_RE = re.compile(
    r"\b(?:now accepting|accepting (?:project )?proposals|submission deadline|deadline|submitted at any time"
    r"|first come|application period|application cycle|one application per|now closed|is closed)\b", re.I)
CLOSED_RE = re.compile(r"\b(?:now closed|is closed)\b", re.I)
OPEN_RE = re.compile(r"\b(?:now accepting|accepting (?:project )?proposals|at any time|first come)\b", re.I)
ROLLING_RE = re.compile(r"\b(?:at any time|first come|rolling)\b", re.I)
MATCH_RE = re.compile(r"\b(?:\d:\d (?:cash )?match|match(?:ing)? (?:requirement|grant|funds?)|cash match)\b", re.I)
FULL_DATE_RE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b")
CONTACT_RE = re.compile(r"@|\b\d{3}-\d{3}-\d{4}\b|^contact us\b", re.I)
LABEL_MAX_CHARS = 80


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


# ---------- parsing (no I/O) ----------

def _content(soup: BeautifulSoup) -> Tag:
    main = soup.select_one("#main_content") or soup
    for side in main.select(".col-md-3, #readspeaker_button1, .panel-group"):
        side.decompose()
    return main


def parse_page(page_html: str) -> dict[str, Any]:
    """title, blocks [(kind, text)] in order (kind: label, p, li), tags (Related Topics). Contact lines dropped."""
    soup = BeautifulSoup(page_html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    content = _content(soup)
    tags = [clean(a.get_text(" ")) for a in content.select("a[rel=tag]")]
    for small in content.find_all("small"):
        small.decompose()
    blocks: list[tuple[str, str]] = []
    for el in content.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        if el.name == "h1":
            continue
        text = clean(el.get_text(" ")) if el.name != "li" else clean(" ".join(el.find_all(string=True, recursive=False)) or el.get_text(" "))
        if not text or CONTACT_RE.search(text):
            continue
        bold = el.find(["strong", "b"])
        label = el.name in ("h2", "h3", "h4") or (bold is not None and clean(bold.get_text(" ")) == text and len(text) <= LABEL_MAX_CHARS)
        blocks.append(("label" if label else el.name, text))
    return {"title": clean(content.h1.get_text(" ")) if content.h1 else (clean(soup.h1.get_text(" ")) if soup.h1 else ""),
            "blocks": blocks, "tags": tags}


def applicant_lines(blocks: list[tuple[str, str]]) -> list[str]:
    out: list[str] = []
    on = False
    for kind, text in blocks:
        if kind == "label":
            on = bool(LABEL_RE.search(text))
            continue
        if on:
            out.append(text)
            continue
        for s in sentences(text):
            if APPLICANT_RE.search(s) and s not in out:
                out.append(s)
    return out


def cycle_sentence(blocks: list[tuple[str, str]]) -> str | None:
    for _kind, text in blocks:
        for s in sentences(text):
            if CYCLE_RE.search(s):
                return s
    return None


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    prior = prior or {}
    records: list[RawRecord] = []
    with _client() as client:
        for i, slug in enumerate(PAGES):
            if limit and i >= limit:
                break
            if i:
                time.sleep(DELAY_S)
            try:
                page = parse_page(_get(client, f"{BASE}{slug}/"))
            except httpx.HTTPError:
                if slug in prior:
                    records.append(RawRecord(source_connector=CONNECTOR, source_id=slug, payload=prior[slug]))
                continue
            records.append(RawRecord(source_connector=CONNECTOR, source_id=slug, payload={"page": page}))
    return records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    return {"status": "unknown"}


# ---------- normalize ----------

def status_for(sentence: str | None, closes_at: date | None, today: date) -> str:
    if not sentence:
        return "unknown"
    if CLOSED_RE.search(sentence):
        return "closed"
    if OPEN_RE.search(sentence) or (closes_at and closes_at >= today):
        return "open"
    return "unknown"


def closes_at_for(sentence: str | None) -> date | None:
    dates = [parse_date(m) for m in FULL_DATE_RE.findall(sentence or "")]
    dates = [d for d in dates if d]
    return dates[-1] if dates else None


def tag_categories(tags: list[str]) -> list[CategoryTag]:
    """Only the tags the shared table knows; `finance` and `grants` are not topics."""
    out: list[CategoryTag] = []
    for tag in tags:
        for value in PORTAL_CATEGORIES.get(portal_label(tag), ()):
            if all(not (c.value == value and c.source_code == tag) for c in out):
                out.append(CategoryTag(value=value, source_code=tag))
    return out


def applicant_tags(lines: list[str]) -> list[ApplicantTag]:
    kept = [s for line in lines for s in sentences(line) if not NEGATION_RE.search(s)]
    return applicant_types_for(kept or None)


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    page = raw.payload["page"]
    today = today or date.today()
    blocks = [tuple(b) for b in page.get("blocks", [])]
    text = " ".join(t for _, t in blocks)
    name = clean(page.get("title", "")) or raw.source_id
    sentence = cycle_sentence(blocks)
    closes_at = closes_at_for(sentence)
    lines = applicant_lines(blocks)
    summary = next((t for k, t in blocks if k == "p"), None)
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=f"{BASE}{raw.source_id}/",
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=PAGES.get(raw.source_id) or funding_type_for(name),
        funding_source="direct",
        amount_min=None,
        amount_max=None,
        match_required=True if MATCH_RE.search(text) else None,
        match_pct=None,
        status=status_for(sentence, closes_at, today),
        opens_at=None,
        closes_at=closes_at,
        closes_at_text=sentence,
        rolling=True if sentence and ROLLING_RE.search(sentence) else None,
        summary=summary,
        eligibility_text="\n".join(lines) or None,
        eligibility_structured={"topics": page["tags"]} if page.get("tags") else None,
        applicant_types=applicant_tags(lines),
        categories=tag_categories(page.get("tags", [])),
        alns=[],
    )
