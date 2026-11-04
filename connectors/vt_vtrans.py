"""Vermont Agency of Transportation connector: the Municipal Assistance grant pages.

Source: https://vtrans.vermont.gov, vermont.gov's Drupal 10 theme; one GET per page in `PAGES`. Page reader, status table and field mapping
are the Vermont base (`connectors/vermont_drupal.py`). See docs/connectors/vermont.md.
"""

from __future__ import annotations

from connectors.vermont_drupal import VermontAgency

CONNECTOR = "vt_vtrans"
BASE = "https://vtrans.vermont.gov"
AGENCY = "Vermont Agency of Transportation"
AGENCY_CODE = "VT-VTRANS"
CATEGORY_LABEL = "transportation"
PAGES: dict[str, str] = {
    "transport-alt": "/highway/local-projects/transport-alt",
    "mhsmp": "/highway/Municipal-Highway-and-Stormwater-Mitigation-Program",
    "grants-in-aid": "/highway/Municipal-Grant-in-aid-Program",
    "better-roads": "/highway/better-roads",
    "bike-ped": "/highway/local-projects/bike-ped",
}


class Vtrans(VermontAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = Vtrans()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
