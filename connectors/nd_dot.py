"""North Dakota Department of Transportation connector: the four state-administered local grant programs
(Flexible Transportation Fund, Transportation Alternatives, Urban Grant Program, Special Road Fund).

Source: https://www.dot.nd.gov, the state's `ndit_base` Drupal 11 theme; one GET per page in `PAGES`. Page reader
in `connectors/north_dakota_drupal.py`; status table and field mapping are the agency-page table in
`connectors/hand_list.py`. See docs/connectors/north_dakota.md.
"""

from __future__ import annotations

import re

from connectors.north_dakota_drupal import NdAgency

CONNECTOR = "nd_dot"
BASE = "https://www.dot.nd.gov"
AGENCY = "North Dakota Department of Transportation"
AGENCY_CODE = "ND-DOT"
CATEGORY_LABEL = "transportation"
PAGES: dict[str, str] = {
    "flex-fund": "/flexfund",
    "transportation-alternatives": "/construction-and-planning/transportation-plans-programs/transportation-alternatives-ta",
    "urban-grant": "/construction-and-planning/urban-grant-program-ugp",
    "special-road-fund": "/construction-and-planning/construction-planning/programs-and-planning/special-road-fund-program",
}
# The Flex Fund page holds three grants under "Flex Fund Programs", each with its own applicants; "Prairie Dog as
# Grants" is the Treasurer's note on where the money comes from and names every applicant type, so it belongs to none.
SPLITS = {
    "flex-fund": [
        ("townships", "Flex Fund: Grants for Non-Oil Townships", re.compile(r"^Grants for Non-Oil Townships", re.I)),
        ("counties-cities", "Flex Fund: Grants for Non-Oil Counties and Cities", re.compile(r"^Grants for Non-Oil Counties and Cities", re.I)),
        ("bridges", "Flex Fund: Grants for Bridges", re.compile(r"^Grants for Bridges", re.I)),
        ("funding-note", None, re.compile(r"^Prairie Dog", re.I)),
    ],
}


class NdDot(NdAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    SPLITS = SPLITS


SITE = NdDot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
