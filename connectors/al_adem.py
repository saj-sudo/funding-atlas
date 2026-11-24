"""Alabama Department of Environmental Management connector: the funding programs a town applies to (milestone 12.9).

Source: https://adem.alabama.gov, Drupal; one GET per page in `PAGES`, 3 s apart. The program's text is in `<main>`; the
title is the page's `h1` (in the banner, outside `<main>`). Three records: the State Revolving Fund (the Clean Water and
Drinking Water loan funds, described together on one page), the Alabama Recycling Fund grants (the "Recycling Grants"
section of the Recycling Program page; the rest of that page is facility regulation and is cut away as tails of the split,
while the "Recycling Announcements" list above it dates the round and stays), and the Section 319(h) nonpoint source grant.
Status table and field mapping are the agency-page table in `connectors/hand_list.py`. ADECA (CDBG, LWCF, RTP) is not read:
its robots.txt disallows `ClaudeBot`. See docs/connectors/alabama.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean

CONNECTOR = "al_adem"
BASE = "https://adem.alabama.gov"
AGENCY = "Alabama Department of Environmental Management"
AGENCY_CODE = "AL-ADEM"
CATEGORY_LABEL = "environment and water"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "srf": "/water/state-revolving-fund-srf",
    "recycling": "/waste/recycling-program",
    "319": "/water/nonpoint-source-pollution-program/section-319-grant-resources",
}
SPLITS = {"recycling": [
    ("recycling", "Alabama Recycling Fund Grants", re.compile(r"^Recycling Grants$", re.I)),
    # the rest of the page regulates recycling facilities: no program
    ("facilities", None, re.compile(r"^(?:General Overview|Recycling Facility Regulations|Recycling Facility Reporting Requirements)$", re.I)),
]}
FUNDING_TYPES = {"srf": "loan"}   # "low interest loan programs"; the name carries no keyword
# SRF: "funded with a blend of state and federal capitalization funds"; 319: a Clean Water Act Section 319(h) subaward with
# a "non-federal match". The shared rule looks for FHWA, FEMA, HUD or NPS by name, and neither page names one of those.
FUNDING_SOURCES = {"srf": "pass_through", "319": "pass_through", "recycling": "direct"}
CATEGORY_LABELS = {"recycling": "solid waste"}   # names none of our categories: `other`, not `water`
# "Grant Announcement - FY2027 Grant Request for Proposals (Priority Deadline is July 1st)": no year.
YEARLESS_RE = re.compile(r"\bdeadline is (?:January|February|March|April|May|June|July|August|September|October|November"
                         r"|December)\s+\d{1,2}", re.I)
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
# contact blocks, and the recycling page's closing link list
DROP_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|@adem\.alabama\.gov|^Contact Information\b|^Helpful Links\b"
                     r"|^A Plan for Boosting\b|^Can.t find the answers\b", re.I)
# SRF: needs surveys, business cases, forms, reports and the contact block follow; 319: three lists of links.
STOP_RE = re.compile(r"^(?:technical assistance|epa grant resources)$", re.I)
# "Who is Eligible for Funding:", "How to Apply:": a short paragraph that ends in a colon heads the list under it.
COLON_LABEL_RE = re.compile(r"^[^.]{3,60}:$")


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the page's `h1`) and the blocks of `<main>`, up to the first heading in `STOP_RE`."""
    doc = soup(page_html)
    h1 = doc.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    main = doc.find("main")
    if main is None:
        return {"title": title, "blocks": []}
    for li in main.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(main, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    blocks = [("label" if kind == "p" and COLON_LABEL_RE.match(text) else kind, text) for kind, text in blocks]
    return {"title": title, "blocks": blocks}


class AlAdem(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "AL"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    SPLITS = SPLITS
    FUNDING_TYPES = FUNDING_TYPES
    FUNDING_SOURCES = FUNDING_SOURCES
    CATEGORY_LABELS = CATEGORY_LABELS
    YEARLESS_RE = YEARLESS_RE
    APPLICANT_ITEM_MAX = 400   # "Local governments – any municipality, county, or district or authority ..." is one long item

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)


SITE = AlAdem()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
