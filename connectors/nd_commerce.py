"""North Dakota Department of Commerce connector: the Division of Community Development and Rural Prosperity's (CDRP)
eight grant program pages.

Source: https://www.commerce.nd.gov, the state's `ndit_base` Drupal 11 theme; one GET per page in `PAGES`. Page reader
in `connectors/north_dakota_drupal.py`; status table and field mapping are the agency-page table in
`connectors/hand_list.py`. See docs/connectors/north_dakota.md.
"""

from __future__ import annotations

from connectors.north_dakota_drupal import NdAgency

CONNECTOR = "nd_commerce"
BASE = "https://www.commerce.nd.gov"
AGENCY = "North Dakota Department of Commerce, Community Development and Rural Prosperity"
AGENCY_CODE = "ND-COMMERCE"
CATEGORY_LABEL = "community development"
_CDRP = "/community-services/community-development-rural-prosperity/cdrp-resources"
PAGES: dict[str, str] = {
    "vibrancy": f"{_CDRP}/cdrp-grant-programs-0",
    "slum-blight": f"{_CDRP}/cdrp-grant-programs-1",
    "workforce-housing": f"{_CDRP}/cdrp-grant-programs-2",
    "facility-planning": f"{_CDRP}/cdrp-grant-programs-3",
    "partners-in-planning": f"{_CDRP}/cdrp-grant-programs-4",
    "artists-on-main-street": f"{_CDRP}/cdrp-grant-programs-5",
    "rural-catalyst": f"{_CDRP}/cdrp-grant-programs-6",
    "rural-grocery": f"{_CDRP}/cdrp-grant-programs/rural",
}


class NdCommerce(NdAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = NdCommerce()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
