"""Connecticut DEMHS connector: the grant program pages under Grants.

Source: https://portal.ct.gov, one GET per page in `PAGES`. Page reader in `connectors/connecticut_portal.py`; status
table and field mapping are the agency-page table in `connectors/hand_list.py`. See docs/connectors/connecticut.md.
"""

from __future__ import annotations

from connectors.connecticut_portal import BASE, CtAgency

CONNECTOR = "ct_demhs"
AGENCY = "Connecticut Division of Emergency Management and Homeland Security"
AGENCY_CODE = "CT-DEMHS"
CATEGORY_LABEL = "emergency management"
PAGES: dict[str, str] = {
    "mgp": "/demhs/grants/municipal-grant-program",
    "fma": "/demhs/grants/flood-mitigation-assistance",
    "bric": "/demhs/grants/building-resilient-infrastructure-and-communities",
    "hmgp": "/demhs/grants/hazard-mitigation-grant-program",
    "empg": "/demhs/grants/emergency-management-performance-grant",
    "hsgp": "/demhs/grants/homeland-security-grant-program",
    "slcgp": "/demhs/grants/state-and-local-cybersecurity-grant-program",
}


class CtDemhs(CtAgency):
    CONNECTOR = CONNECTOR
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = CtDemhs()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
__all__ = ["BASE", "CONNECTOR", "PAGES", "SITE", "fetch", "normalize", "resolve_missing"]
