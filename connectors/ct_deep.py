"""Connecticut DEEP connector: the two open space grant programs for municipalities.

Source: https://portal.ct.gov, one GET per page in `PAGES`. Page reader in `connectors/connecticut_portal.py`; status
table and field mapping are the agency-page table in `connectors/hand_list.py`. See docs/connectors/connecticut.md.
"""

from __future__ import annotations

from connectors.connecticut_portal import BASE, CtAgency

CONNECTOR = "ct_deep"
AGENCY = "Connecticut Department of Energy and Environmental Protection"
AGENCY_CODE = "CT-DEEP"
CATEGORY_LABEL = "recreation and conservation"
PAGES: dict[str, str] = {
    "oswa": "/deep/open-space/open-space-and-watershed-land-acquisition-grant-program",
    "ugcg": "/deep/open-space/urban-green-and-community-garden-grant-program",
}


class CtDeep(CtAgency):
    CONNECTOR = CONNECTOR
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = CtDeep()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
__all__ = ["BASE", "CONNECTOR", "PAGES", "SITE", "fetch", "normalize", "resolve_missing"]
