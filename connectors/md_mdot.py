"""Maryland Department of Transportation connector: three hand-listed grant pages of The Secretary's Office (the
Kim Lamphier Bikeways Network Program, the Urban Tree Program, the TOD Capital Grant and Revolving Loan Fund).

The pages are the mdgov theme's Bootstrap layout (`main.mdgov-main`, `div.card` accordions), not the rich-text body
the SharePoint base reads, so this is the DCR/DelDOT hand-list pattern: three GETs a run. Every page keeps its old
banners ("Applications are OPEN ...", "currently closed for applications") inside HTML comments, which are removed
before anything is read. The Urban Tree page names no eligible applicant; its how-to-apply PDF does, and that
sentence is quoted by hand, dated, in `HAND_QUOTES`. See docs/connectors/md_mdot.md.
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

CONNECTOR = "md_mdot"
BASE = "https://www.mdot.maryland.gov"
URL = BASE + "/tso/pages/Index.aspx?PageId={n}"
# slug -> (PageId, section menu label)
PAGES: dict[str, tuple[int, str]] = {
    "bikeways": (28, "Active Transportation"),
    "urban-tree": (165, "Active Transportation"),
    "tod": (217, "Transit Oriented Development"),
}
AGENCY = "Maryland Department of Transportation"
AGENCY_CODE = "MD-MDOT"
JURISDICTION = "MD"
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

# The name says "Grant and Revolving Loan Fund" and the keyword table answers "loan" first; the open call is for
# capital grants and the loan side is "later this year" (page, 2026-11-03).
FUNDING_TYPE_OVERRIDES = {"tod": "grant"}
# Eligibility sentences quoted by hand from a document the page links, never fetched (the Illinois NOFO precedent):
# slug -> (date read, source, lines).
HAND_QUOTES: dict[str, tuple[str, str, list[str]]] = {
    "urban-tree": ("2026-11-03", "UTP How to Apply FY27 (PDF, last update 4.15.2026)", [
        "Eligible Applicants: Non-profit organizations; schools; community/neighborhood associations; places of "
        "worship; businesses; community business associations; homeowner associations, business service, youth and "
        "civic groups; institutions of higher education; counties; municipalities; and forest conservancy district "
        "boards.",
    ]),
}

# A card or heading that lists applicants. Not a bare "eligib": "Eligibility" heads the whole accordion and "Eligible
# Projects" lists project criteria ("... major institution (universities, hospitals ...)").
LABEL_RE = re.compile(r"who (?:may|can) apply|eligible (?:applicants?|entities|organizations|sponsors?)", re.I)
# Sentences that say who the money goes to. Not a bare "eligible": the Bikeways page says "Eligible Projects",
# "Eligible Areas" and "now eligible as minor retrofit projects" about projects, not applicants.
APPLICANT_RE = re.compile(
    r"\bassistance to\b|\bmay apply\b|\bopen to\b|\bavailable to\b"
    r"|\beligible (?:applicants?|entities|organizations|sponsors?)\b(?!\s+are encouraged)", re.I,
)
OPEN_RE = re.compile(r"\b(?:now )?accepting\b[^.]*\bapplications\b|\bapplications?\b[^.]*\b(?:are|is|will be|now) (?:open|accepted)\b", re.I)
ROLLING_RE = re.compile(r"year-round|rolling basis", re.I)
ANNOUNCED_RE = re.compile(r"\bawards?\b[^.]*\b(?:have|has) (?:now )?been announced\b|\bawards? (?:are|were) announced\b", re.I)
CLOSED_RE = re.compile(r"\bclosed for applications\b|\b(?:is|are) (?:now )?closed\b|\bno longer accepting\b", re.I)
MATCH_RE = re.compile(r"\bmatch(?:ing)? (?:fund )?requirements?\b|\bmatch(?:ing)? (?:is|are) required\b|\bmust commit a \d{1,3}% match\b|\b\d{1,3}% (?:local )?match\b", re.I)
FULL_DATE_RE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b")
CONTACT_RE = re.compile(r"@|\[email|\b\d{3}[.-]\d{3}[.-]\d{4}\b|\breach out to\b|\bplease contact\b|\bcontact us\b", re.I)


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


def _content(soup: BeautifulSoup) -> Tag:
    main = soup.select_one("main.mdgov-main") or soup.select_one("#DeltaPlaceHolderMain") or soup
    for gone in main.select("nav, table, .card-footer, form"):
        gone.decompose()
    return main


BLOCK_TAGS = {"p", "div", "ul", "ol", "li", "table", "section", "nav", "h1", "h2", "h3", "h4", "h5", "h6"}


def _own_text(el: Tag) -> str:
    """A block's text minus its nested blocks: SharePoint nests <p> inside <p> and <div class="row"> inside <p>, so
    the outer element's full text would repeat every child and fuse a banner with the paragraphs after it."""
    parts = [str(c) if not isinstance(c, Tag) else ("" if c.name in BLOCK_TAGS else c.get_text(" ")) for c in el.children]
    return clean(" ".join(parts))


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the H1), blocks [(kind, text)]: label (headings and card headers), p, li. Comments are removed first:
    the pages keep their stale banners in them. Contact lines dropped."""
    soup = BeautifulSoup(page_html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    content = _content(soup)
    h1 = content.find("h1") or soup.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    blocks: list[tuple[str, str]] = []
    for el in content.find_all(["h2", "h3", "h4", "h5", "p", "li", "div"]):
        if el.name == "div":
            if "card-header" not in (el.get("class") or []):
                continue
            kind, text = "label", clean(el.get_text(" "))
        else:
            kind = "label" if el.name.startswith("h") else el.name
            text = _own_text(el)
        if not text or CONTACT_RE.search(text) or (kind == "label" and text == title):
            continue
        if blocks and blocks[-1] == (kind, text):
            continue
        blocks.append((kind, text))
    return {"title": title, "blocks": blocks}


def applicant_lines(blocks: list[tuple[str, str]]) -> list[str]:
    """List items under an eligibility label, plus sentences that say who the money goes to."""
    out: list[str] = []
    on = False
    for kind, text in blocks:
        if kind == "label":
            on = bool(LABEL_RE.search(text))
            if on:
                out.append(text)
            continue
        if on and kind == "li":
            out.append(text)
            continue
        on = on and kind == "li"
        for s in sentences(text):
            if APPLICANT_RE.search(s) and s not in out:
                out.append(s)
    return out


def quote_lines(slug: str) -> list[str]:
    read, source, lines = HAND_QUOTES.get(slug, ("", "", []))
    return [f"{source}, read {read}: {line}" for line in lines]


def round_sentence(blocks: list[tuple[str, str]]) -> str | None:
    """The first sentence that states the round: accepting with a date, then accepting at all (year-round included),
    then awards announced, then closed."""
    sents = [s for _, text in blocks for s in sentences(text)]
    for rule in (lambda s: OPEN_RE.search(s) and not NEGATION_RE.search(s) and FULL_DATE_RE.search(s),
                 lambda s: OPEN_RE.search(s) and not NEGATION_RE.search(s),
                 lambda s: ANNOUNCED_RE.search(s),
                 lambda s: CLOSED_RE.search(s)):
        hit = next((s for s in sents if rule(s)), None)
        if hit:
            return hit
    return None


def closes_at_for(sentence: str | None) -> date | None:
    dates = [parse_date(re.sub(r"(\d)(?:st|nd|rd|th)", r"\1", m)) for m in FULL_DATE_RE.findall(sentence or "")]
    dates = [d for d in dates if d]
    return dates[-1] if dates else None


def status_for(sentence: str | None, closes_at: date | None, today: date) -> tuple[str, bool | None]:
    """(status, rolling) from the round sentence."""
    if not sentence:
        return "unknown", None
    if OPEN_RE.search(sentence) and not NEGATION_RE.search(sentence):
        if closes_at:
            return ("open" if closes_at >= today else "unknown"), None
        if ROLLING_RE.search(sentence):
            return "open", True
        return "open", None
    if ANNOUNCED_RE.search(sentence) or CLOSED_RE.search(sentence):
        return "closed", None
    return "unknown", None


def applicant_tags(lines: list[str]) -> list[ApplicantTag]:
    kept = [s for line in lines for s in sentences(line) if not NEGATION_RE.search(s)]
    return applicant_types_for(kept or None)


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    prior = prior or {}
    records: list[RawRecord] = []
    with _client() as client:
        for i, (slug, (page_id, section)) in enumerate(PAGES.items()):
            if limit and i >= limit:
                break
            if i:
                time.sleep(DELAY_S)
            try:
                page = parse_page(_get(client, URL.format(n=page_id)))
            except httpx.HTTPError:
                if slug in prior:
                    records.append(RawRecord(source_connector=CONNECTOR, source_id=slug, payload=prior[slug]))
                continue
            records.append(RawRecord(source_connector=CONNECTOR, source_id=slug,
                                     payload={"page_id": page_id, "section": section, "page": page}))
    return records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    return {"status": "unknown"}


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    page = raw.payload["page"]
    page_id = raw.payload.get("page_id") or PAGES.get(raw.source_id, (0, ""))[0]
    section = raw.payload.get("section") or PAGES.get(raw.source_id, (0, "mdot"))[1]
    today = today or date.today()
    blocks = [tuple(b) for b in page.get("blocks", [])]
    text = " ".join(t for _, t in blocks)
    name = clean(page.get("title", "")) or raw.source_id
    sentence = round_sentence(blocks)
    closes_at = closes_at_for(sentence)
    status, rolling = status_for(sentence, closes_at, today)
    lines = applicant_lines(blocks) + quote_lines(raw.source_id)
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=URL.format(n=page_id),
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=FUNDING_TYPE_OVERRIDES.get(raw.source_id) or funding_type_for(name) or "grant",
        funding_source="direct",
        amount_min=None,
        amount_max=None,
        match_required=True if MATCH_RE.search(text) else None,
        match_pct=None,
        status=status,
        opens_at=None,
        closes_at=closes_at,
        closes_at_text=sentence,
        rolling=rolling,
        summary=next((t for k, t in blocks if k == "p" and len(t) > 80 and not (sentence and sentence in t)), None),
        eligibility_text="\n".join(lines) or None,
        eligibility_structured=None,
        applicant_types=applicant_tags(lines),
        categories=[CategoryTag(value="transportation", source_code=section)],
        alns=[],
    )
