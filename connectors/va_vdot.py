"""Virginia Department of Transportation connector: the Local Assistance Division's funding programs.

Source: https://www.vdot.virginia.gov/doing-business/for-localities/local-assistance/, a page of resource cards (a
link, a title, a one-line blurb) under the site's "For localities" section; six of the eight cards are funding
programs and the two process cards are excluded by slug. Each program page is prose that states its cycle as a
season ("opens the first week of October") rather than a date, so status is unknown and the cycle sentence is kept.
The section name and the card blurb are the agency's words about who the money is for and feed the tagger. Seven GETs
a run. See docs/connectors/va_vdot.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any
from urllib.parse import urljoin

import httpx

from connectors.grants_gov import parse_date
from connectors.hand_list import (
    DATE_RE,
    DELAY_S,
    applicant_tags,
    resolve_missing,  # noqa: F401  (the pipeline reads it from this module)
)
from connectors.hand_list import client as _client
from connectors.hand_list import get as _get
from connectors.hand_list import soup as _soup
from connectors.maryland_drupal import sentences
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for
from pipeline.models import Program, RawRecord

CONNECTOR = "va_vdot"
BASE = "https://www.vdot.virginia.gov"
INDEX_URL = BASE + "/doing-business/for-localities/local-assistance/"
SECTION_LABEL = "For localities (VDOT section)"
EXCLUDED = frozenset({"locally-administered-projects", "training-and-outreach"})
AGENCY = "Department of Transportation"
AGENCY_CODE = "VA-VDOT"
JURISDICTION = "VA"

CYCLE_RE = re.compile(
    r"\b(?:application period|applications? (?:are|will be|must be) (?:accepted|due|submitted)|deadline|are due|is due"
    r"|must be submitted|are biennial|accepting applications|now closed|is closed|application cycle|pre-application cycle)\b", re.I)
CLOSED_RE = re.compile(r"\b(?:now closed|is closed)\b", re.I)
FULL_DATE_RE = DATE_RE
APPLICANT_RE = re.compile(r"\b(?:eligible|qualif(?:y|ies)|may apply|localit(?:y|ies)|count(?:y|ies)|cit(?:y|ies)|towns?|municipalit\w*)\b", re.I)
CONTACT_RE = re.compile(r"^contact(?: us)?$", re.I)


# ---------- HTTP ----------


# ---------- parsing (no I/O) ----------


def parse_cards(index_html: str) -> list[dict[str, str]]:
    """One dict per resource card on the index: slug, url, title, blurb. Process cards are left out."""
    soup = _soup(index_html)
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select("div.resource-card"):
        link = card.find("a", href=True)
        if link is None:
            continue
        url = urljoin(BASE, link["href"])
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if slug in EXCLUDED or slug in seen:
            continue
        seen.add(slug)
        title = card.find("h3")
        blurb = card.find("p")
        out.append({"slug": slug, "url": url, "title": clean(title.get_text(" ")) if title else "",
                    "blurb": clean(blurb.get_text(" ")) if blurb else ""})
    return out


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the h1), paragraphs (p and li texts in order), stopping at a Contact heading. The site's editor splits
    words across inline spans ("appl</span><span>ications"), so inline text is joined with no separator; the spaces
    the page carries between words are kept by `clean`."""
    soup = _soup(page_html)
    main = soup.select_one("main#main-content-container") or soup.find("main") or soup
    h1 = main.select_one("h1.pagetitle") or main.find("h1")
    paragraphs: list[str] = []
    for el in main.find_all(["h2", "h3", "p", "li"]):
        text = clean(el.get_text(""))
        if el.name in ("h2", "h3") and CONTACT_RE.match(text):
            break
        if el.name in ("p", "li") and text:
            paragraphs.append(text)
    return {"title": clean(h1.get_text(" ")) if h1 else "", "paragraphs": paragraphs}


# One page, several programs: the access roads page describes three programs, each opened by its own "The <name>
# Program provides funding" paragraph. Each becomes its own record, with the page's first paragraph as context and its
# own paragraphs after it (10.6). The first part keeps the page's own id, so the stored record of the whole page becomes
# that program rather than lingering as an `unknown` record no run returns; the others are `slug#part`.
SPLIT_PAGES: dict[str, list[tuple[str, str, str]]] = {
    "access-roads-programs": [
        ("economic-development-access", "Economic Development Access Program", "The Economic Development Access"),
        ("airport-access", "Airport Access Program", "The Airport Access Program"),
        ("recreational-access", "Recreational Access Program", "The Recreational Access Program"),
    ],
}


def _part_id(slug: str, n: int, part: str) -> str:
    return slug if n == 0 else f"{slug}#{part}"


def split_page(slug: str, page: dict[str, Any] | None) -> list[tuple[str, dict[str, Any] | None]]:
    """(source_id, page) for each program on a page: the page itself, or one part per program in `SPLIT_PAGES`."""
    parts = SPLIT_PAGES.get(slug)
    if not parts:
        return [(slug, page)]
    if page is None:
        return [(_part_id(slug, n, part), None) for n, (part, _, _) in enumerate(parts)]
    paragraphs = page.get("paragraphs", [])
    starts = [next((i for i, t in enumerate(paragraphs) if t.startswith(lead)), None) for _, _, lead in parts]
    out: list[tuple[str, dict[str, Any] | None]] = []
    for n, (part, title, _) in enumerate(parts):
        start = starts[n]
        if start is None:
            out.append((_part_id(slug, n, part), None))
            continue
        end = next((s for s in starts[n + 1:] if s is not None), len(paragraphs))
        out.append((_part_id(slug, n, part), {"title": title, "paragraphs": paragraphs[:1] + paragraphs[start:end]}))
    return out


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The index, then each program card's page. An unreadable index aborts; an unreadable page falls back."""
    prior = prior or {}
    records: list[RawRecord] = []
    with _client() as client:
        cards = parse_cards(_get(client, INDEX_URL))
        if limit:
            cards = cards[:limit]
        for card in cards:
            try:
                time.sleep(DELAY_S)
                page = parse_page(_get(client, card["url"]))
            except httpx.HTTPError:
                page = None
            for source_id, part in split_page(card["slug"], page):
                if part is None:
                    part = (prior.get(source_id) or {}).get("page")
                records.append(RawRecord(source_connector=CONNECTOR, source_id=source_id, payload={"card": card, "page": part}))
    return records[:limit] if limit else records


# ---------- normalize ----------

def cycle_sentence(paragraphs: list[str]) -> str | None:
    for text in paragraphs:
        for s in sentences(text):
            if CYCLE_RE.search(s):
                return s
    return None


def applicant_lines(card: dict[str, str], paragraphs: list[str]) -> list[str]:
    lines = [f"{SECTION_LABEL}: {card['blurb']}" if card.get("blurb") else SECTION_LABEL]
    for text in paragraphs:
        for s in sentences(text):
            if APPLICANT_RE.search(s) and s not in lines:
                lines.append(s)
    return lines


def status_for(sentence: str | None, closes_at: date | None, today: date) -> str:
    if sentence and CLOSED_RE.search(sentence):
        return "closed"
    if closes_at and closes_at >= today:
        return "open"
    return "unknown"


def closes_at_for(sentence: str | None) -> date | None:
    dates = [parse_date(m) for m in FULL_DATE_RE.findall(sentence or "")]
    dates = [d for d in dates if d]
    return dates[-1] if dates else None


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    card, page = raw.payload["card"], raw.payload.get("page") or {}
    today = today or date.today()
    paragraphs = page.get("paragraphs", [])
    name = clean(page.get("title", "")) or clean(card.get("title", "")) or raw.source_id
    sentence = cycle_sentence(paragraphs)
    closes_at = closes_at_for(sentence)
    lines = applicant_lines(card, paragraphs)
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=card["url"],
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(name),
        funding_source="direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status=status_for(sentence, closes_at, today),
        opens_at=None,
        closes_at=closes_at,
        closes_at_text=sentence,
        rolling=None,
        summary=paragraphs[0] if paragraphs else (card.get("blurb") or None),
        eligibility_text="\n".join(lines),
        eligibility_structured=None,
        applicant_types=applicant_tags(lines),
        categories=[],
        alns=[],
    )
