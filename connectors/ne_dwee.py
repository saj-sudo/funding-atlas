"""Nebraska Department of Water, Energy, and Environment connector: the pages of its "Aid" section (loans, grants and
rebates) that take applications from local governments and public bodies (milestone 12.6g).

Source: https://dwee.nebraska.gov, Drupal 10 (the merged environment and natural resources agencies; `dee.nebraska.gov`
and `dnr.nebraska.gov` redirect here); one GET per page in `PAGES`. The program's text sits in one of two body fields
(`field--name-body`, or `field--name-field-full-width-paragraph` on the waste pages), the larger of the two, because the
theme repeats small copies of the first in its menus. Status table and field mapping are the agency-page table in
`connectors/hand_list.py`. Left out: Litter Reduction (public and private entities, no local government named), the
electric grid resilience grants (utilities, closed), the State Energy Program and ONE RED (programs still being set up),
the VW trust and clean diesel rebates (school buses, past rounds), lead testing for schools and childcare facilities.
See docs/connectors/nebraska.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import ELIGIBILITY_LABEL_RE, AgencyPageConnector, blocks_from, sentences, soup
from connectors.sam_assistance_listings import clean

CONNECTOR = "ne_dwee"
BASE = "https://dwee.nebraska.gov"
AGENCY = "Nebraska Department of Water, Energy, and Environment"
AGENCY_CODE = "NE-DWEE"
CATEGORY_LABEL = "environment and water"
BODY_SELECTOR = "div.field--name-body, div.field--name-field-full-width-paragraph"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "cwsrf": "/aid/water-loans-grants-rebates/clean-water-state-revolving-loan-fund-wastewater-treatment-facilities-and-sanitary-sewer-collection-systems",
    "dwsrf": "/aid/water-loans-grants-rebates/drinking-water-state-revolving-loan-fund",
    "dw-planning": "/aid/water-loans-grants-rebates/planning-grants-drinking-water-preliminary-engineering-reports",
    "section-319": "/aid/water-loans-grants-rebates/nonpoint-source-water-quality-grants-section-319",
    "deconstruction": "/aid/waste-grants-rebates/deconstruction-grants-program",
    "illegal-dumpsite": "/aid/waste-loans-grants-rebates/illegal-dumpsite-cleanup-program",
    "scrap-tire": "/aid/waste-grants-rebates/scrap-tire-management-grant-programs",
    "eecbg": "/aid/energy-loans-grants-rebates/energy-efficiency-and-conservation-block-grant-program",
    "eerlf": "/aid/energy-loans-grants-rebates/energy-efficiency-revolving-loan-fund-capitalization-grant-program",
}
# The portal-style topic each record carries (labels the shared table already knows); waste is not one: `other`.
CATEGORY_LABELS = {
    "cwsrf": "clean water", "dwsrf": "drinking water", "dw-planning": "drinking water", "section-319": "non-point source",
    "deconstruction": "waste and recycling", "illegal-dumpsite": "waste and recycling", "scrap-tire": "waste and recycling",
    "eecbg": "energy", "eerlf": "energy",
}
# Where the page names a federal source of the money (quoted in docs/connectors/nebraska.md); the rest name none and stay
# `direct`, the school energy loans among them ("capitalization grants to States" does not say whose).
FUNDING_SOURCES = {"dwsrf": "pass_through", "section-319": "pass_through", "eecbg": "pass_through"}
# "Energy Efficiency Revolving Loan Fund Capitalization Grant Program": the name says grant, the page says loans.
FUNDING_TYPES = {"eerlf": "loan"}

DROP_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|@nebraska\.gov|^Official Nebraska Government Website", re.I)
STOP_RE = re.compile(r"(?:related information|related links|related resources|nebraska department of ?water, energy, and environment)$", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the page's `h1`) and the blocks of the larger body field."""
    doc = soup(page_html)
    h1 = doc.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    fields = doc.select(BODY_SELECTOR)
    if not fields:
        return {"title": title, "blocks": []}
    body = max(fields, key=lambda e: len(e.get_text()))
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    # The waste and planning pages answer "Who's Eligible" in a paragraph, not a list: each sentence of a paragraph under an
    # eligibility heading is read as one of that heading's list items (the page's own words, in its own order).
    out: list[tuple[str, str]] = []
    under = False
    for kind, text in blocks:
        if kind == "label":
            under = bool(ELIGIBILITY_LABEL_RE.search(text))
        if under and kind == "p":
            out += [("li", sentence) for sentence in sentences(text)]
        else:
            out.append((kind, text))
    return {"title": title, "blocks": out}


class NeDwee(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "NE"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    APPLICANT_ITEM_MAX = 400      # an answer under "Who's Eligible" is a whole sentence or two
    CATEGORY_LABELS = CATEGORY_LABELS
    FUNDING_SOURCES = FUNDING_SOURCES
    FUNDING_TYPES = FUNDING_TYPES

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)


SITE = NeDwee()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
