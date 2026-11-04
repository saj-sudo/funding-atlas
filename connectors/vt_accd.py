"""Vermont Agency of Commerce and Community Development connector: the Department of Housing and Community Development's
grant pages under Funding and Incentives.

Source: https://accd.vermont.gov, vermont.gov's Drupal 10 theme; one GET per page in `PAGES`. Page reader, status table and field mapping
are the Vermont base (`connectors/vermont_drupal.py`). See docs/connectors/vermont.md.
"""

from __future__ import annotations

from connectors.vermont_drupal import VermontAgency

CONNECTOR = "vt_accd"
BASE = "https://accd.vermont.gov"
AGENCY = "Agency of Commerce and Community Development, Department of Housing and Community Development"
AGENCY_CODE = "VT-ACCD"
CATEGORY_LABEL = "community development"
PAGES: dict[str, str] = {
    "vcdp": "/community-development/funding-incentives/vcdp",
    "disaster-recovery": "/community-development/funding-incentives/disaster-recovery",
    "downtown-transportation-fund": "/community-development/funding-incentives/downtown-transportation-fund",
    "evse": "/community-development/funding-incentives/electric-vehicle-supply-equipment-evse-grant-program",
    "municipal-planning-grant": "/community-development/funding-incentives/municipal-planning-grant",
    "bylaw-modernization-grants": "/content/bylaw-modernization-grants",
}


class Accd(VermontAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = Accd()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
