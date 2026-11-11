"""North Dakota Department of Emergency Services connector: the Recovery and Mitigation section's two FEMA
pass-through pages (Public Assistance; Unified Hazard Mitigation: HMGP, BRIC and FMA).

Source: https://www.des.nd.gov, the state's `ndit_base` Drupal 11 theme; one GET per page in `PAGES`. Page reader
in `connectors/north_dakota_drupal.py`; status table and field mapping are the agency-page table in
`connectors/hand_list.py`. DES's preparedness grants host, `grants.des.nd.gov`, serves `Disallow: /` and is not read.
See docs/connectors/north_dakota.md.
"""

from __future__ import annotations

from connectors.north_dakota_drupal import NdAgency

CONNECTOR = "nd_des"
BASE = "https://www.des.nd.gov"
AGENCY = "North Dakota Department of Emergency Services"
AGENCY_CODE = "ND-DES"
CATEGORY_LABEL = "emergency management"
PAGES: dict[str, str] = {
    "public-assistance": "/recovery-mitigation/public-assistance",
    "hazard-mitigation": "/recovery-mitigation/unified-hazard-mitigation-grant-assistance",
}


class NdDes(NdAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = NdDes()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
