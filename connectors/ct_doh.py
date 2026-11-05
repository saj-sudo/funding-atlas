"""Connecticut Department of Housing connector: the CDBG Small Cities program page.

Source: https://portal.ct.gov, one GET per page in `PAGES`. Page reader in `connectors/connecticut_portal.py`; status
table and field mapping are the agency-page table in `connectors/hand_list.py`. See docs/connectors/connecticut.md.
"""

from __future__ import annotations

from connectors.connecticut_portal import BASE, CtAgency

CONNECTOR = "ct_doh"
AGENCY = "Connecticut Department of Housing"
AGENCY_CODE = "CT-DOH"
CATEGORY_LABEL = "community development"
PAGES: dict[str, str] = {
    "small-cities": "/doh/doh-1/programs/small-cities-program",
}


class CtDoh(CtAgency):
    CONNECTOR = CONNECTOR
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = CtDoh()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
__all__ = ["BASE", "CONNECTOR", "PAGES", "SITE", "fetch", "normalize", "resolve_missing"]
