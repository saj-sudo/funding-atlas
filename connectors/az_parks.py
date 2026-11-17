"""Arizona State Parks and Trails connector: five grant program pages (milestone 12.6j).

Source: https://azstateparks.com, one GET per page in `PAGES`, 3 s apart. The only Arizona agency the registry reads:
Housing, ADOT, DEMA, Commerce and State Parks' own WebGrants storefront answer a Cloudflare challenge, and WIFA disallows
`ClaudeBot` (docs/connectors/arizona.md). The program text is in the `div.content.container .col-md-12` column; the page
has two `h1`s (the first is the site logo), so the title is the column's first `h2`. Each page has a description, a
labelled list ("Available Funds:", "Eligible Applicants:", "Eligible Projects:"), a FAQ and contact line (dropped), then
"Start Here Before You Apply" (manuals, maps and the apply link), where the read stops. No page states a round: timing is
announced in the WebGrants storefront, so a record is `unknown` unless its page dates a round (Route 66's pre-application deadline). SLIF and both Heritage Fund
pages are left out while they state $0 available for FY27. Status table and field mapping are the agency-page
table in `connectors/hand_list.py`.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean

CONNECTOR = "az_parks"
BASE = "https://azstateparks.com"
AGENCY = "Arizona State Parks and Trails"
AGENCY_CODE = "AZ-ASPT"
CATEGORY_LABEL = "parks and recreation"
BODY_SELECTOR = ".content.container .col-md-12"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "lwcf": "/lwcf-grants",
    "competitive-lwcf": "/competitive-LWCF-grants",
    "ohv": "/off-highway-vehicle-fund-grants",
    "rtp": "/recreational-trails-program-grants",
    "route-66": "/route-66-historic-revitalization-grant",
    # Left out while each says "Available Funds: $0 (Arizona State Parks and Trails did not receive any additional FY27
    # ... funds for grant funding opportunities this year.)" (the Missouri funds-exhausted rule, 2026-11-11); one line
    # each to restore when the FY28 pages name an amount:
    # "slif": "/state-lake-improvement-fund-grants",
    # "heritage": "/heritage-fund-grants",
    # "heritage-historic": "/heritage-fund-historic-preservation-grants",
}
# The LWCF page names no federal agency ("established by Congress in 1964"); the grants hub says "Funded by the federal
# Land and Water Conservation Fund" (Missouri State Parks' RTP and HPF precedent: the hub's sentence, per record).
FUNDING_SOURCES = {"lwcf": "pass_through"}
# "ORLP grants are opened by National Park Service once per year, typically in June and closing in October": no year.
YEARLESS_RE = re.compile(r"\btypically in \w+ and closing in \w+", re.I)
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"^have questions about\b|@azstateparks\.gov|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b", re.I)
STOP_RE = re.compile(r"^(?:start here before you apply|frequently asked questions)$", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the page's last `h1`; the first is the site logo) and the content column's blocks, up to "Start Here
    Before You Apply" or the FAQ."""
    doc = soup(page_html)
    body = doc.select_one(BODY_SELECTOR)
    h1s = doc.find_all("h1")
    title = clean(h1s[-1].get_text(" ")) if h1s else ""
    if body is None:
        return {"title": title, "blocks": []}
    for nav in body.find_all("nav"):
        nav.decompose()
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


class AzParks(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "AZ"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    FUNDING_SOURCES = FUNDING_SOURCES
    YEARLESS_RE = YEARLESS_RE

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)


SITE = AzParks()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
