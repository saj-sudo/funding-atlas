"""The Vermont agency base: what every vermont.gov Drupal 10 agency page shares (milestone 12.6a).

Vermont's agencies (ACCD, VTrans, Forests Parks and Recreation, Emergency Management) all run vermont.gov's USWDS
Drupal theme: the title is the `h1`, the page's own text is the body field of the main content block. This module
reads that body into `(kind, text)` blocks with the hand-list helpers; the status table, the applicant reader and the
field mapping are the agency-page table in `connectors/hand_list.py` (moved there when Connecticut reused them). An
agency module sets its constants, its page dict and its category label. See docs/connectors/vermont.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors import hand_list
from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean

# The agency-page table now lives in hand_list.py; these names stay here because the Vermont tests and doc use them.
DATE_RE = hand_list.AGENCY_DATE_RE
deadline = hand_list.deadline
opening = hand_list.opening
round_for = hand_list.round_for
applicant_lines = hand_list.applicant_lines
funding_source_for = hand_list.funding_source_for

JURISDICTION = "VT"
BODY_SELECTOR = ".block-system-main-block .field--name-body"
LABEL_MAX_CHARS = 90

# VTrans's accessibility notice tops every page; contact lines name a person.
DROP_RE = re.compile(r"committed to ensuring accessibility|Telephone:|Tel:|E-mail|e-mail|@vermont\.gov", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title and the body's blocks, accessibility notice and contact lines dropped."""
    doc = soup(page_html)
    body = doc.select_one(BODY_SELECTOR)
    title = clean(doc.h1.get_text(" ")) if doc.h1 else ""
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS) if body else []
    return {"title": title, "blocks": blocks}


class VermontAgency(AgencyPageConnector):
    """A Vermont agency: set CONNECTOR, BASE, AGENCY, AGENCY_CODE, CATEGORY_LABEL and PAGES (slug -> path)."""

    JURISDICTION = JURISDICTION

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)
