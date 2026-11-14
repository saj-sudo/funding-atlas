"""South Dakota Department of Agriculture and Natural Resources connector: the Environmental Funding pages for drinking
water, sanitary and storm sewer, and solid waste projects (milestone 12.6i).

Source: https://danr.sd.gov, the department's own ASP.NET pages (Bootstrap); one GET per page in `PAGES`. No other South
Dakota agency shares the platform, so the reader is this module's own. The text is in the main column
(`.row-offcanvas > .col-xs-12`); the page's `h1` is the division ("Environmental Funding"), so the title is the first `h2`.
Each page offers grants and low-interest loans from the Board of Water and Natural Resources (the SRFs and the state's
Consolidated Water Facilities Construction Program), taken quarterly with no year stated. Status table and field mapping are
the agency-page table in `connectors/hand_list.py`. Left out: Section 319 (no program page), the Petroleum Release
Compensation Fund, the Specialty Crop Block Grant. See docs/connectors/south_dakota.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean

CONNECTOR = "sd_danr"
BASE = "https://danr.sd.gov"
AGENCY = "South Dakota Department of Agriculture and Natural Resources"
AGENCY_CODE = "SD-DANR"
CATEGORY_LABEL = "environment and water"
BODY_SELECTOR = ".row-offcanvas > .col-xs-12"
LABEL_MAX_CHARS = 90

_F = "/Funding/EnviromentalFunding"
PAGES: dict[str, str] = {
    "drinking-water": f"{_F}/DrinkingWater.aspx",
    "sanitary-sewer": f"{_F}/Sanitary.aspx",
    "solid-waste": f"{_F}/SolidWaste.aspx",
}
CATEGORY_LABELS = {"drinking-water": "drinking water", "sanitary-sewer": "clean water", "solid-waste": "waste and recycling"}
# "Applicants should expect to receive some portion of funding as a loan" (the grants are principal forgiveness and
# subsidy on top of the loans).
FUNDING_TYPES = {slug: "loan" for slug in PAGES}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|@state\.sd\.us|\[email\s*protected\]|^E-mail:", re.I)
STOP_RE = re.compile(r"(?:related links|resources)$", re.I)
# "... must be postmarked or received by the department on or before the first day of January, April, July, and October."
# The State Water Plan's own deadline ("on or before the first day of October") is a plan listing, not the application.
YEARLESS_RE = re.compile(r"\bon or before the first day of January\b", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the first `h2` of the main column) and its blocks."""
    doc = soup(page_html)
    body = doc.select_one(BODY_SELECTOR)
    if body is None:
        return {"title": "", "blocks": []}
    h2 = body.find("h2")
    title = clean(h2.get_text(" ")) if h2 else ""
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


class SdDanr(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "SD"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    APPLICANT_ITEM_MAX = 400      # "Be sponsored by one of the following entities: a special purpose district ...; a municipality, county, or township; ..."
    CATEGORY_LABELS = CATEGORY_LABELS
    FUNDING_TYPES = FUNDING_TYPES
    YEARLESS_RE = YEARLESS_RE

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)


SITE = SdDanr()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
