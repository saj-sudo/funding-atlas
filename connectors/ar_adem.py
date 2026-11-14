"""Arkansas Division of Emergency Management connector: the grant pages under ADEM's "Grants & Funding" that take
applications from local governments (milestone 12.6h).

Source: https://dps.arkansas.gov (the Department of Public Safety's site), the state's WordPress; one GET per page in
`PAGES`, ten seconds apart (the robots file's `Crawl-delay: 10`). Page reader in `connectors/arkansas_wordpress.py`; status
table and field mapping are the agency-page table in `connectors/hand_list.py`. The Hazard Mitigation Grants page holds
the state's own Hazard Mitigation Grant Program and BRIC, one record each; its Shelter Rebate section (ended 2016) and its
federal HMGP section (the HMGP page's program) belong to no record. Left out: EMPG (a list of forms), NEHRP and EHP (links
to FEMA), the Non-Profit Security Grant (nonprofits), FY26 SBSRF (no applicant named), Pre-Disaster Mitigation (retired
by FEMA for BRIC), the Public Safety Equipment Grant (not funded for FY2026). See docs/connectors/arkansas.md.
"""

from __future__ import annotations

import re

from connectors.arkansas_wordpress import ArAgency

CONNECTOR = "ar_adem"
BASE = "https://dps.arkansas.gov"
AGENCY = "Arkansas Division of Emergency Management"
AGENCY_CODE = "AR-ADEM"
CATEGORY_LABEL = "emergency mitigation"
_G = "/emergency-management/adem/grants-funding"
PAGES: dict[str, str] = {
    "hmgp": f"{_G}/hazard-mitigation-grant-program/",
    "hazard-mitigation": f"{_G}/hazard-mitigation-grants/",
    "hsgp": f"{_G}/homeland-security-grant-program/",
}
SPLITS = {"hazard-mitigation": [
    ("hazard-mitigation", "State of Arkansas Hazard Mitigation Grant Program", re.compile(r"^State of Arkansas Hazard Mitigation", re.I)),
    ("bric", "Building Resilient Infrastructure and Communities (BRIC)", re.compile(r"^Building Resilient Infrastructure", re.I)),
    ("shelter-rebate", None, re.compile(r"^Shelter Rebate", re.I)),
    ("federal-hmgp", None, re.compile(r"^Hazard Mitigation Grant Program$", re.I)),
]}
CATEGORY_LABELS = {"hsgp": "emergency management"}
# The state program is the state's money ("the state reimburses 75% of the project cost"); the page's intro names FEMA.
FUNDING_SOURCES = {"hazard-mitigation": "direct", "hazard-mitigation#bric": "pass_through", "hsgp": "pass_through"}


class ArAdem(ArAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    SPLITS = SPLITS
    CATEGORY_LABELS = CATEGORY_LABELS
    FUNDING_SOURCES = FUNDING_SOURCES
    DELAY_S = 10.0


SITE = ArAdem()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
