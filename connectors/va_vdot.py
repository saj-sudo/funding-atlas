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
from bs4 import BeautifulSoup, Comment

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for
from pipeline.models import ApplicantTag, Program, RawRecord

CONNECTOR = "va_vdot"
BASE = "https://www.vdot.virginia.gov"
INDEX_URL = BASE + "/doing-business/for-localities/local-assistance/"
SECTION_LABEL = "For localities (VDOT section)"
EXCLUDED = frozenset({"locally-administered-projects", "training-and-outreach"})
AGENCY = "Department of Transportation"
AGENCY_CODE = "VA-VDOT"
JURISDICTION = "VA"
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

CYCLE_RE = re.compile(
    r"\b(?:application period|applications? (?:are|will be|must be) (?:accepted|due|submitted)|deadline|are due|is due"
    r"|must be submitted|are biennial|accepting applications|now closed|is closed|application cycle|pre-application cycle)\b", re.I)
CLOSED_RE = re.compile(r"\b(?:now closed|is closed)\b", re.I)
FULL_DATE_RE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b")
APPLICANT_RE = re.compile(r"\b(?:eligible|qualif(?:y|ies)|may apply|localit(?:y|ies)|count(?:y|ies)|cit(?:y|ies)|towns?|municipalit\w*)\b", re.I)
CONTACT_RE = re.compile(r"^contact(?: us)?$", re.I)


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
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return soup


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
            payload: dict[str, Any] = {"card": card, "page": None}
            try:
                time.sleep(DELAY_S)
                payload["page"] = parse_page(_get(client, card["url"]))
            except httpx.HTTPError:
                payload["page"] = (prior.get(card["slug"]) or {}).get("page")
            records.append(RawRecord(source_connector=CONNECTOR, source_id=card["slug"], payload=payload))
    return records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A card VDOT dropped: not a closure it stated; unknown, no request."""
    return {"status": "unknown"}


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


def applicant_tags(lines: list[str]) -> list[ApplicantTag]:
    kept = [s for line in lines for s in sentences(line) if not NEGATION_RE.search(s)]
    return applicant_types_for(kept or None)


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
