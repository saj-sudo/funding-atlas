"""Maryland Department of Transportation connector: three hand-listed grant pages of The Secretary's Office (the
Kim Lamphier Bikeways Network Program, the Urban Tree Program, the TOD Capital Grant and Revolving Loan Fund).

The pages are the mdgov theme's Bootstrap layout (`main.mdgov-main`, `div.card` accordions), not the rich-text body
the SharePoint base reads, so this is the hand-list pattern (`connectors/hand_list.py`, whose default status table
is this connector's): three GETs a run. Every page keeps its old banners ("Applications are OPEN ...", "currently
closed for applications") inside HTML comments, which are removed before anything is read. The Urban Tree page names
no eligible applicant; its how-to-apply PDF does, and that sentence is quoted by hand, dated, in `HAND_QUOTES`. See
docs/connectors/md_mdot.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from bs4 import BeautifulSoup, Tag

from connectors.hand_list import Blocks, HandListConnector, applicant_tags, label_lines, own_text, quote_lines, soup
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for
from pipeline.models import CategoryTag, RawRecord

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
# The round sentence and the status table are the base's (HandListConnector.OPEN_RE, ROLLING_RE, ANNOUNCED_RE,
# CLOSED_RE, DATE_RE): they were written here first and became the default.
MATCH_RE = re.compile(r"\bmatch(?:ing)? (?:fund )?requirements?\b|\bmatch(?:ing)? (?:is|are) required\b|\bmust commit a \d{1,3}% match\b|\b\d{1,3}% (?:local )?match\b", re.I)
CONTACT_RE = re.compile(r"@|\[email|\b\d{3}[.-]\d{3}[.-]\d{4}\b|\breach out to\b|\bplease contact\b|\bcontact us\b", re.I)


# ---------- parsing (no I/O) ----------

def _content(doc: BeautifulSoup) -> Tag:
    main = doc.select_one("main.mdgov-main") or doc.select_one("#DeltaPlaceHolderMain") or doc
    for gone in main.select("nav, table, .card-footer, form"):
        gone.decompose()
    return main


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the H1), blocks [(kind, text)]: label (headings and card headers), p, li. Comments are removed first:
    the pages keep their stale banners in them. Contact lines dropped."""
    doc = soup(page_html)
    content = _content(doc)
    h1 = content.find("h1") or doc.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    blocks: Blocks = []
    for el in content.find_all(["h2", "h3", "h4", "h5", "p", "li", "div"]):
        if el.name == "div":
            if "card-header" not in (el.get("class") or []):
                continue
            kind, text = "label", clean(el.get_text(" "))
        else:
            kind = "label" if el.name.startswith("h") else el.name
            text = own_text(el)
        if not text or CONTACT_RE.search(text) or (kind == "label" and text == title):
            continue
        if blocks and blocks[-1] == (kind, text):
            continue
        blocks.append((kind, text))
    return {"title": title, "blocks": blocks}


def applicant_lines(blocks: Blocks) -> list[str]:
    """List items under an eligibility label, plus sentences that say who the money goes to."""
    return label_lines(blocks, LABEL_RE, APPLICANT_RE, keep_kinds=("li",), keep_label=True)


# ---------- the connector ----------

class Mdot(HandListConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = JURISDICTION
    PAGES = PAGES

    def urls_for(self, slug: str, spec: tuple[int, str]) -> list[str]:
        return [URL.format(n=spec[0])]

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: tuple[int, str], pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        page_id, section = spec
        return [(slug, {"page_id": page_id, "section": section, "page": pages[0]})]

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        page = raw.payload["page"]
        page_id = raw.payload.get("page_id") or PAGES.get(raw.source_id, (0, ""))[0]
        section = raw.payload.get("section") or PAGES.get(raw.source_id, (0, "mdot"))[1]
        blocks = [tuple(b) for b in page.get("blocks", [])]
        text = " ".join(t for _, t in blocks)
        name = clean(page.get("title", "")) or raw.source_id
        sentence = self.round_sentence(blocks)
        closes_at = self.closes_at_for(sentence)
        status, rolling = self.status_for(sentence, closes_at, today)
        lines = applicant_lines(blocks) + quote_lines(HAND_QUOTES, raw.source_id)
        return dict(
            source_url=URL.format(n=page_id),
            name=name,
            funding_type=FUNDING_TYPE_OVERRIDES.get(raw.source_id) or funding_type_for(name) or "grant",
            funding_source="direct",
            match_required=True if MATCH_RE.search(text) else None,
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
        )


SITE = Mdot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
round_sentence = SITE.round_sentence
status_for = SITE.status_for
closes_at_for = SITE.closes_at_for
