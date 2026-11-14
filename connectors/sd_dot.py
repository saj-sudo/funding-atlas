"""South Dakota Department of Transportation connector: the local-government grants SDDOT takes applications for
(milestone 12.6i).

Source: https://dot.sd.gov, Umbraco (Modern Logic); one GET per page in `PAGES`. No other South Dakota agency runs Umbraco,
so the reader is this module's own (Nebraska's NDOT is Umbraco too, on another theme). The program's text is in `<main>`;
the title is its `h1`; the breadcrumb and the menus are `div`s and are not read. The Transportation Economic Development
Grants page names three programs in its paragraphs, one record each (Industrial Park keeps the page's `source_id`); the
read stops at the Commission's award announcements. Status table and field mapping are the agency-page table in
`connectors/hand_list.py`. Left out: the Rural Access Infrastructure Fund (a formula allocation to counties), the Local
Federal Bridge Program page (documents and past awards), Urban Systems, Emergency Relief, the transit pages.
See docs/connectors/south_dakota.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean

CONNECTOR = "sd_dot"
BASE = "https://dot.sd.gov"
AGENCY = "South Dakota Department of Transportation"
AGENCY_CODE = "SD-DOT"
CATEGORY_LABEL = "transportation"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "bridge-improvement": "/doing-business/local-governments/bridge-improvement-grants/",
    "economic-development": "/doing-business/local-governments/transportation-economic-development-grants/",
    "ta": "/programs-services/programs/transportation-alternatives/",
}
SPLITS = {"economic-development": [
    ("economic-development", "Industrial Park Road Grants", re.compile(r"^The Industrial Park grants\b", re.I)),
    ("agri-business", "Agri-Business Road Grants", re.compile(r"^The Agri-Business grants\b", re.I)),
    ("community-access", "Community Access Grants", re.compile(r"^Community Access Grants are\b", re.I)),
    # the grant terms and the application checklist after the three paragraphs belong to all three; they carry no round
    ("terms", None, re.compile(r"^These programs provide\b", re.I)),
]}
SPLIT_KINDS = {"economic-development": ("label", "p")}
# TA: "uses federal transportation funds, designated by Congress"; the others are state funds.
FUNDING_SOURCES = {"ta": "pass_through"}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
# contact lines; BIG's link to the year's changed guides ("Notable changes to the 2027 Five-Year Highway Plan Guide ...")
DROP_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|@state\.sd\.us|\[email\s*protected\]|^Notable changes to\b", re.I)
STOP_RE = re.compile(r"(?:south dakota transportation commission awards.*|resources|contact.*)$", re.I)
# "Applications are due April 15, July 15, or October 15.", "Applications are due July 1 ...": no year.
YEARLESS_RE = re.compile(r"\b(?:deadlines?|due)\b[^.]*\b(?:January|February|March|April|May|June|July|August|September|October"
                         r"|November|December)\s+\d{1,2}\b", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and the blocks of `<main>`."""
    doc = soup(page_html)
    main = doc.find("main")
    if main is None:
        return {"title": "", "blocks": []}
    h1 = main.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    # A list item that wraps paragraphs ("<li><p>The Industrial Park grants ...</p></li>") is read through its paragraphs,
    # once: read as an item too, each program's sentence would land in the section before its own.
    for li in main.find_all("li"):
        if li.find("p"):
            li.name = "div"
    for li in main.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(main, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


class SdDot(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "SD"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    SPLITS = SPLITS
    SPLIT_KINDS = SPLIT_KINDS
    FUNDING_SOURCES = FUNDING_SOURCES
    YEARLESS_RE = YEARLESS_RE

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)


SITE = SdDot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
