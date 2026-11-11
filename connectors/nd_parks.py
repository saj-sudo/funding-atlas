"""North Dakota Parks and Recreation Department connector: the two federal pass-through grant pages (Land and Water
Conservation Fund, Recreational Trails Program).

Source: https://www.parkrec.nd.gov, the state's `ndit_base` Drupal 11 theme; one GET per page in `PAGES`. Page reader
in `connectors/north_dakota_drupal.py`; status table and field mapping are the agency-page table in
`connectors/hand_list.py`. Rounds the department posts on the WebGrants storefront (`grants.nd.gov`) are read by
`webgrants`. See docs/connectors/north_dakota.md.
"""

from __future__ import annotations

from connectors.north_dakota_drupal import NdAgency

CONNECTOR = "nd_parks"
BASE = "https://www.parkrec.nd.gov"
AGENCY = "North Dakota Parks and Recreation Department"
AGENCY_CODE = "ND-PARKS"
CATEGORY_LABEL = "parks and recreation"
PAGES: dict[str, str] = {
    "lwcf": "/business/grants/land-and-water-conservation-fund",
    "rtp": "/business/grants/recreational-trails-program",
}


class NdParks(NdAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = NdParks()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
