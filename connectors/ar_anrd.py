"""Arkansas Department of Agriculture, Natural Resources Division connector: the water and wastewater financing page,
the High Hazard Potential Dam grant and the Section 319 nonpoint source grants (milestone 12.6h).

Source: https://agriculture.arkansas.gov, the state's WordPress; one GET per page in `PAGES`. Page reader in
`connectors/arkansas_wordpress.py`; status table and field mapping are the agency-page table in `connectors/hand_list.py`.
The water and wastewater page is one record: five funds (CWSRF, DWSRF, WDF, WSSW, CGO) under one applicant list, one
application process and one "Application Status" line; its `h3` sections are rate tables. Left out: the department's
agricultural grants (producers and processors), the Agricultural Water Quality Loan Program (farmers), tax credits.
See docs/connectors/arkansas.md.
"""

from __future__ import annotations

import re

from connectors.arkansas_wordpress import ArAgency

CONNECTOR = "ar_anrd"
BASE = "https://agriculture.arkansas.gov"
AGENCY = "Arkansas Department of Agriculture (Natural Resources Division)"
AGENCY_CODE = "AR-ANRD"
CATEGORY_LABEL = "environment and water"
PAGES: dict[str, str] = {
    "water-wastewater": "/natural-resources/water-development/water-and-wastewater-funding/",
    "hhpd": "/natural-resources/water-management/dam-safety/high-hazard-potential-dam-grant-program/",
    "section-319": "/natural-resources/water-management/nonpoint-source-management/",
}
NAMES = {"section-319": "Section 319 Nonpoint Source Grant Program"}
# The Nonpoint Source Management page: its "319 Grant Program" section is the program; the watershed lists after it belong
# to no record (the intro above it follows the record as shared text).
SPLITS = {"section-319": [
    ("section-319", "Section 319 Nonpoint Source Grant Program", re.compile(r"^319 Grant Program$", re.I)),
    ("watersheds", None, re.compile(r"^Why Fund Watershed Projects", re.I)),
]}
CATEGORY_LABELS = {"water-wastewater": "clean water", "hhpd": "emergency mitigation", "section-319": "non-point source"}
# The loan funds ("State Revolving Loan Fund Rates", "State Program Rates") name no keyword in the page's title.
FUNDING_TYPES = {"water-wastewater": "loan"}
# Section 319: "provides federal funding through the Environmental Protection Agency" (EPA is not in the shared federal
# list). The water page says "state and federal programs" without naming the funder and stays `direct`.
FUNDING_SOURCES = {"section-319": "pass_through"}


class ArAnrd(ArAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    NAMES = NAMES
    SPLITS = SPLITS
    CATEGORY_LABELS = CATEGORY_LABELS
    FUNDING_TYPES = FUNDING_TYPES
    FUNDING_SOURCES = FUNDING_SOURCES


SITE = ArAnrd()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
