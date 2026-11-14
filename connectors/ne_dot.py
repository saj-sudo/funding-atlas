"""Nebraska Department of Transportation connector: the local-assistance programs that take applications, and the
public transit funding page (milestone 12.6g).

Source: https://dot.nebraska.gov, Umbraco (no `robots.txt`); one GET per page in `PAGES`. The page's text is `div#main`
(or `div.mainContent` on the two older pages; the contact block and resources sit in the footer), the title the `<title>` without its " - NDOT" suffix (Umbraco pages
here have no `h1`). Status table and field mapping are the agency-page table in `connectors/hand_list.py`. The transit
funding page holds four programs (Sections 5311, 5311(f), 5310 and 5339), so it is one record per program (`SPLITS`).
Left out: the programs that have no application (the Federal Funds Purchase Program is an exchange of federal funds for
state cash, County Soft Match is a list of monthly balances, the Accelerated Capital Improvement Program is NDOT's own
expressway construction), the pages that carry no program text (the Off-System Bridge Program announces a selection and
links documents; the State Recreation Road Fund's page links guidelines). See docs/connectors/nebraska.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.hand_list import AgencyPageConnector, blocks_from, sentences, soup
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "ne_dot"
BASE = "https://dot.nebraska.gov"
AGENCY = "Nebraska Department of Transportation"
AGENCY_CODE = "NE-DOT"
CATEGORY_LABEL = "transportation"
BODY_SELECTOR = "div#main, div.mainContent"      # the newer template, and the older one TA and HSIP are on
LABEL_MAX_CHARS = 90
POLITE_DELAY_S = 1.0

PAGES: dict[str, str] = {
    "ta": "/business-center/local-public-assistance/projects/tap/",
    "hsip": "/business-center/local-public-assistance/projects/programs/hsip/",
    "county-bridge-match": "/projects/tia/bridge-match/",
    "economic-opportunity": "/projects/tia/eco-opp/",
    "transit": "/public-transit/funding-applications/",
}
# slug -> [(sub_slug, name, heading pattern)]; the first declared program keeps the page's own source_id.
SPLITS = {
    "transit": [
        ("5311", "Section 5311 Rural Public Transportation", re.compile(r"^5311 Rural Public Transportation$", re.I)),
        ("5311f", "Section 5311(f) Intercity Bus", re.compile(r"^5311\(f\) Intercity Bus Application$", re.I)),
        ("5310", "Section 5310 Enhanced Mobility of Seniors and Individuals with Disabilities", re.compile(r"^5310 Enhanced Mobility Transportation$", re.I)),
        ("5339", "Section 5339 Bus and Bus Facilities", re.compile(r"^5339 Bus and Bus Facilities$", re.I)),
    ],
}
SOURCE_IDS = [slug if i == 0 else f"{slug}#{sub}" for slug, parts in SPLITS.items() for i, (sub, _, _) in enumerate(parts)]
# Where the page itself says the money is federal ("$47 million of federal TAP funds", "This program provides Federal funding",
# "Provides federal funding to support public transportation", "A federal grant program"); the state's County Bridge Match
# and Economic Opportunity programs are paid from state funds and name no federal source.
FUNDING_SOURCES = {"ta": "pass_through", "hsip": "pass_through", **{sid: "pass_through" for sid in SOURCE_IDS}}

DROP_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|@nebraska\.gov", re.I)
TITLE_SUFFIX_RE = re.compile(r"\s*-\s*NDOT\s*$", re.I)
# "Applications accepted Oct. 31 to Nov. 30", "HSIP applications received by January 31st each year": a window or a deadline with a
# month and a day and no year. Not a date, so the status stays `unknown` and `closes_at` null, but the sentence is kept.
YEARLESS_ROUND_RE = re.compile(r"\b(?:accepted|received by|deadline)\b[^.]*\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `<title>` without " - NDOT") and the blocks of the page body."""
    doc = soup(page_html)
    title = TITLE_SUFFIX_RE.sub("", clean(doc.title.get_text(" "))) if doc.title else ""
    body = doc.select_one(BODY_SELECTOR)
    if body is None:
        return {"title": title, "blocks": []}
    return {"title": title, "blocks": blocks_from(body, ["h2", "h3", "h4", "p", "li"], drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)}


class NeDot(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "NE"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    SPLITS = SPLITS
    DELAY_S = POLITE_DELAY_S
    FUNDING_SOURCES = FUNDING_SOURCES

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        if out["status"] == "unknown" and not out["closes_at_text"]:
            blocks = [tuple(b) for b in raw.payload["page"].get("blocks", [])]
            out["closes_at_text"] = next((x for _, t in blocks for x in sentences(t)
                                          if YEARLESS_ROUND_RE.search(x) and not re.search(r"\b\d{4}\b", x)), None)
        return out


SITE = NeDot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
