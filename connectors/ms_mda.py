"""Mississippi Development Authority connector: the Community Incentives cards (milestone 12.9).

Source: https://mississippi.org/community-resources/incentives/, WordPress; one GET. The page is a grid of cards inside
`#community-incentives-results`: a program name (`h3.c-card__title`), one paragraph, a link to a one-page PDF (not read).
One page, one record per card through `SPLITS`, built from the titles in `CARDS`; the first card keeps the page's
`source_id`. A card that is not in `CARDS` (the Mississippi Rail Grant Program, which railroads apply for, and any card
added later) is a tail: no record, and its text joins no other record. The page's pager loads two more cards by a form POST
to admin-ajax.php, which the hand-list base does not make: they are not read. No card states a round, so every record is
`unknown`. The sentence that gives a division's telephone number is removed from the paragraph. Status table and field
mapping are the agency-page table in `connectors/hand_list.py`; the sentences that name an applicant in MDA's own words are
added here (`OWN_APPLICANT_RE`). See docs/connectors/mississippi.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.hand_list import PARTNER_LINE_RE, AgencyPageConnector, all_sentences, applicant_tags, clause_cut, soup
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "ms_mda"
BASE = "https://mississippi.org"
AGENCY = "Mississippi Development Authority"
AGENCY_CODE = "MS-MDA"
CATEGORY_LABEL = "community development"
RESULTS_SELECTOR = "#community-incentives-results"

PAGES: dict[str, str] = {"community-incentives": "/community-resources/incentives/"}
# sub-slug -> the card's title as printed, in page order. The first keeps the page's `source_id`.
CARDS: dict[str, str] = {
    "cap": "Capital Improvements Revolving Loan Program (CAP)",
    "cdbg-public-facilities": "Community Development Block Grants (CDBG) for Public Facilities Projects",
    "smlpc": "Small Municipal and Limited Population Counties Grant Program",
    "airport-loan": "Airport Revitalization Revolving Loan Program",
    "freight-rail-loan": "Freight Rail Service Revolving Loan Program",
    "port-loan": "Port Revitalization Revolving Loan Program",
    "cdbg-economic-development": "Community Development Block Grants (CDBG) Economic Development Program",
    "dip": "Development Infrastructure Grant Program (DIP)",
}
SPLITS = {"community-incentives": [
    *[(sub, title, re.compile(rf"^{re.escape(title)}$")) for sub, title in CARDS.items()],
    # any other card ("Mississippi Rail Grant Program": railroads apply) is a tail
    ("other", None, re.compile(r"^(?!(?:" + "|".join(re.escape(t) for t in CARDS.values()) + r")$)")),
]}
# The Public Facilities card names HUD; this one is the same block grant and names only its "national objectives".
FUNDING_SOURCES = {"community-incentives#cdbg-economic-development": "pass_through"}
CATEGORY_LABELS = {"community-incentives#freight-rail-loan": "rail and freight"}
# "For more information on Airport and Port Revolving Loans, contact MDA's Financial Resources Division at 601.359.3552."
CONTACT_RE = re.compile(r"(?:For more information[^.]*?|To learn more),? contact\b.*?\d{3}[.-]\d{3}[.-]\d{4}\.?", re.I)
# "CAP provides loans to municipalities and counties ...", "provides municipalities and counties funding ...", "Funding
# ... can be used by small municipalities ... and counties ...", "provides loans to local units of government ..."
OWN_APPLICANT_RE = re.compile(
    r"\bprovides?\s+(?:(?:loans?|grants?|funds|funding)\s+to\s+)?(?:municipalities|counties|local units? of government)\b"
    r"|\bcan be used by\s+(?:small\s+)?(?:municipalities|counties)\b", re.I)
# What the money is for names who a project serves, not who applies ("to assist with the location, expansion or retention
# of businesses", "to finance public infrastructure projects that promote economic growth"). Cut before tagging only.
USE_RE = re.compile(r"\bto (?:assist|finance)\b.*|\bfor (?:public infrastructure|the airport authority)\b.*", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and, for each card of the results grid, a label (its title) and its paragraphs."""
    doc = soup(page_html)
    h1 = doc.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    blocks: list[tuple[str, str]] = []
    grid = doc.select_one(RESULTS_SELECTOR)
    for card in grid.select(".c-card") if grid else []:
        name = card.select_one(".c-card__title")
        if name is None:
            continue
        blocks.append(("label", clean(name.get_text(" "))))
        for p in card.select(".excerpt-wrapper p"):
            text = clean(CONTACT_RE.sub("", clean(p.get_text(" "))).strip("\u201c\u201d "))   # DIP's card is wrapped in stray quotes
            if text:
                blocks.append(("p", text))
    return {"title": title, "blocks": blocks}


class MsMda(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "MS"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    SPLITS = SPLITS
    FUNDING_SOURCES = FUNDING_SOURCES
    CATEGORY_LABELS = CATEGORY_LABELS

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        """The agency-page table, plus the sentences in which MDA names the applicant in words the shared reader has no
        rule for; what the money is for is cut before tagging."""
        out = super().fields(raw, today)
        lines = out["eligibility_text"].split("\n") if out["eligibility_text"] else []
        blocks = [tuple(b) for b in raw.payload["page"].get("blocks", [])]
        lines += [s for s in all_sentences(blocks) if OWN_APPLICANT_RE.search(s) and s not in lines]
        out["eligibility_text"] = "\n".join(lines) or None
        out["applicant_types"] = applicant_tags([USE_RE.sub("", clause_cut(line)) for line in lines
                                                 if not PARTNER_LINE_RE.search(line)])
        return out


SITE = MsMda()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
