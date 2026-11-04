"""Vermont Department of Forests, Parks and Recreation connector: the three community recreation grant pages.

Source: https://fpr.vermont.gov, vermont.gov's Drupal 10 theme; one GET per page in `PAGES`. Page reader, status table and field mapping
are the Vermont base (`connectors/vermont_drupal.py`). See docs/connectors/vermont.md.
"""

from __future__ import annotations

from connectors.vermont_drupal import VermontAgency

CONNECTOR = "vt_fpr"
BASE = "https://fpr.vermont.gov"
AGENCY = "Vermont Department of Forests, Parks and Recreation"
AGENCY_CODE = "VT-FPR"
CATEGORY_LABEL = "recreation and conservation"
PAGES: dict[str, str] = {
    "vorec": "/vorec-community-grant-program",
    "rtp": "/recreational-trails-program",
    "lwcf": "/land-and-water-conservation-fund",
}


class Fpr(VermontAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = Fpr()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
