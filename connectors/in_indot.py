"""Indiana Department of Transportation connector: the Community Crossings Matching Grant (milestone 12.9).

Source: https://www.in.gov/indot, the state's shared CMS (dotCMS); one GET per page in `PAGES`. OCRA is on the same CMS
(`in_ocra`), with a reader of its own: this page needs neither its tabs nor its card lists. The program's text is in
`main article`: the title is the banner's `#subpage-main-title`, the breadcrumb list is dropped, and the read stops at
the accordion that follows the call for projects (FAQ, guidance, past awards, asset-management and Title VI requirements,
a 2025 newsletter article whose dates are a past call's, and staff contacts). The page states no open call today ("awards
were announced on ..."; "INDOT plans to issue the ... call each September"): `unknown`, the September sentence kept.
Status table and field mapping are the agency-page table in `connectors/hand_list.py`. Left out: the Federal Grant
Opportunities page (federal programs, not INDOT's), the railroad grants (not surveyed). See docs/connectors/indiana.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean

CONNECTOR = "in_indot"
BASE = "https://www.in.gov"
AGENCY = "Indiana Department of Transportation"
AGENCY_CODE = "IN-INDOT"
CATEGORY_LABEL = "transportation"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "community-crossings": "/indot/doing-business-with-indot/local-public-agency-programs/community-crossing-matching-grant-program",
}
# Community Crossings is the state's Local Road and Bridge Matching Grant Fund; the page names no federal source.
FUNDING_SOURCES = {"community-crossings": "direct"}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"@indot\.in\.gov|@purdue\.edu|\[email\s*protected\]|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b", re.I)
STOP_RE = re.compile(r"frequently asked questions.*$", re.I)
# "Moving forward, INDOT plans to issue the Community Crossings Matching Grant call each September on an annual basis."
YEARLESS_RE = re.compile(r"\bcall each (?:January|February|March|April|May|June|July|August|September|October|November|December)\b", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the banner's `h1`) and the blocks of `main article` above the accordion."""
    doc = soup(page_html)
    body = doc.select_one("main article") or doc.find("main")
    if body is None:
        return {"title": "", "blocks": []}
    h1 = body.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    for gone in body.select("#subpage-breadcrumbs, div.accordion-container"):
        gone.decompose()
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


class InIndot(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "IN"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    FUNDING_SOURCES = FUNDING_SOURCES
    YEARLESS_RE = YEARLESS_RE

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)


SITE = InIndot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
