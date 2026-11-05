"""Connecticut Department of Transportation connector: the municipal funding programs under DOT Programs.

Source: https://portal.ct.gov, one GET per page in `PAGES`. Page reader in `connectors/connecticut_portal.py`; status
table and field mapping are the agency-page table in `connectors/hand_list.py`. See docs/connectors/connecticut.md.
"""

from __future__ import annotations

from connectors.connecticut_portal import BASE, CtAgency

CONNECTOR = "ct_dot"
AGENCY = "Connecticut Department of Transportation"
AGENCY_CODE = "CT-DOT"
CATEGORY_LABEL = "transportation"
PAGES: dict[str, str] = {
    "lotcip": "/dot/programs/lotcip",
    "ccgp": "/dot/programs/ccgp",
    "bsep": "/dot/programs/bsep",
    "carbon-reduction": "/dot/programs/carbon-reduction",
}


class CtDot(CtAgency):
    CONNECTOR = CONNECTOR
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = CtDot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
__all__ = ["BASE", "CONNECTOR", "PAGES", "SITE", "fetch", "normalize", "resolve_missing"]
