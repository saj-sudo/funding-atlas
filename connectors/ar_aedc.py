"""Arkansas Economic Development Commission connector: the state CDBG, the Site Development Program and the Division of
Rural Services' three grants (milestone 12.6h).

Source: https://www.arkansasedc.com, Sitefinity 15.2; one GET per page in `PAGES`. No other Arkansas agency runs Sitefinity,
so the reader is this module's own (the Nebraska rule: no base until a second site on the platform forces it). The page's
text sits in the first `.page-content` block; Sitefinity writes many paragraphs as bare `div`s, so a `div` with no block
inside it is read as a paragraph, and a list whose every item is one link (the Rural Services side menu) is dropped. The
page's first `h1` is the program (the Rural Services pages have none; their names are set here). Status table and field
mapping are the agency-page table in `connectors/hand_list.py`. Left out: the EDA Statewide Planning Grant (a one-time ARPA
site study), Arkansas Rural Connect (the 2020 broadband program), CDBG-DR (now the Development Finance Authority's).
See docs/connectors/arkansas.md.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import Tag

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean

CONNECTOR = "ar_aedc"
BASE = "https://www.arkansasedc.com"
AGENCY = "Arkansas Economic Development Commission"
AGENCY_CODE = "AR-AEDC"
CATEGORY_LABEL = "community development"
BODY_SELECTOR = ".page-content"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "cdbg": "/community-resources/community-development-block-grant",
    "site-development": "/community-resources/arkansas-site-development-program",
    "rural-community": "/Rural-Services/division/grants/rural-community-grant",
    "rural-block-grant": "/Rural-Services/division/grants/rural-services-block-grant",
    "wildlife-education": "/Rural-Services/division/grants/wildlife-education-grant",
}
NAMES = {
    "rural-community": "Rural Community Grant Program",
    "rural-block-grant": "Rural Services Block Grant Program",
    "wildlife-education": "Wildlife Education Grant Program",
}
CATEGORY_LABELS = {"wildlife-education": "education"}
# CDBG: "the State receives federal funds from the United States Department of Housing and Urban Development (HUD)" (the
# shared rule finds HUD). The Rural Services Block Grant is "made possible through a partnership with" the state's
# rural development commission and names no federal funder; the rest are state programs.

INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
BLOCKS = {"p", "div", "ul", "ol", "li", "table", "section", "h1", "h2", "h3", "h4", "h5", "h6"}
# The CDBG page's annual-report notice at the top (not program text), contact lines, the site survey's prompt.
DROP_RE = re.compile(r"\bCAPER\b|\bPR28\b|\(\d{3}\)\s?\d{3}-\d{4}|\[email\s*protected\]|^Answer 5 questions|^ASK AWAY$"
                     r"|^No thank you", re.I)
# Where the program's text ends: the contact block, CDBG's administration manual and report lists.
STOP_RE = re.compile(r"(?:contact us|administrative procedures manual|for questions contact:?)$", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the first non-empty `h1`) and the blocks of the first `.page-content`."""
    doc = soup(page_html)
    title = next((t for t in (clean(h.get_text(" ")) for h in doc.find_all("h1")) if t), "")
    body = doc.select_one(BODY_SELECTOR)
    if body is None:
        return {"title": title, "blocks": []}
    for ul in body.find_all(["ul", "ol"]):
        items = ul.find_all("li", recursive=False)
        if items and all(len(li.find_all("a")) == 1 and clean(li.get_text(" ")) == clean(li.a.get_text(" ")) for li in items):
            ul.decompose()
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    for div in body.find_all("div"):
        if isinstance(div, Tag) and not div.find(list(BLOCKS)):
            div.name = "p"
    blocks = blocks_from(body, ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE,
                         bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


class ArAedc(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "AR"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    CATEGORY_LABELS = CATEGORY_LABELS

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        name = NAMES.get(slug)
        return [(sid, {**payload, "name": name} if name else payload) for sid, payload in super().records_for(slug, spec, pages, count)]


SITE = ArAedc()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
