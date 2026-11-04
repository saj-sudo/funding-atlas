"""Vermont Emergency Management connector: the three Funding Opportunities pages.

Source: https://vem.vermont.gov, vermont.gov's Drupal 10 theme; one GET per page in `PAGES`. Page reader, status table and field mapping
are the Vermont base (`connectors/vermont_drupal.py`). See docs/connectors/vermont.md.
"""

from __future__ import annotations

from connectors.vermont_drupal import VermontAgency

CONNECTOR = "vt_vem"
BASE = "https://vem.vermont.gov"
AGENCY = "Vermont Emergency Management"
AGENCY_CODE = "VT-VEM"
CATEGORY_LABEL = "emergency management"
PAGES: dict[str, str] = {
    "empg": "/funding/empg",
    "mitigation": "/funding/mitigation",
    "pa": "/funding/pa",
}


class Vem(VermontAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = Vem()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
