"""The Connecticut agency base: what every portal.ct.gov agency page shares (milestone 12.6b).

Connecticut's agencies are sections of one Sitecore portal with three page templates. This module finds the program
text on whichever template a page uses and reads it into `(kind, text)` blocks with the hand-list helpers; the status
table, the applicant reader and the field mapping are the agency-page table in `connectors/hand_list.py`. An agency
module sets its constants, its page dict and its category label. See docs/connectors/connecticut.md.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import Tag

from connectors.hand_list import AgencyPageConnector, Blocks, blocks_from, soup
from connectors.sam_assistance_listings import clean

JURISDICTION = "CT"
BASE = "https://portal.ct.gov"
LABEL_MAX_CHARS = 90
TAGS = ["h2", "h3", "h4", "p", "li"]
# Contact lines name a person.
DROP_RE = re.compile(r"@ct\.gov|\bPhone:|\bTel:|\bFax:", re.I)


def content_for(doc: Any) -> list[Tag]:
    """The program text's containers, by template: DEMHS's tabs, DOT's main column, DOT's sections, the older layout."""
    for selector in ("main .tabs-content", ".cg-l-main-content"):
        hit = doc.select_one(selector)
        if hit is not None:
            return [hit]
    sections = doc.select("main .content-block-section")
    if sections:
        return sections
    hit = doc.select_one("main .columns.medium-8 > .content") or doc.select_one("main .content")
    return [hit] if hit is not None else []


def parse_page(page_html: str) -> dict[str, Any]:
    """title and the program text's blocks, contact lines dropped."""
    doc = soup(page_html)
    title = clean(doc.h1.get_text(" ")) if doc.h1 else ""
    blocks: Blocks = []
    for container in content_for(doc):
        for block in blocks_from(container, TAGS, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS):
            if block not in blocks:
                blocks.append(block)
    return {"title": title, "blocks": blocks}


class CtAgency(AgencyPageConnector):
    """A Connecticut agency: set CONNECTOR, AGENCY, AGENCY_CODE, CATEGORY_LABEL and PAGES (slug -> path)."""

    JURISDICTION = JURISDICTION
    BASE = BASE

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)
