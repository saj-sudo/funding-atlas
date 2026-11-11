"""Kentucky Transportation Cabinet connector: the Office of Local Programs' two federal-aid programs (Transportation
Alternatives Program, Congestion Mitigation and Air Quality).

Source: https://transportation.ky.gov/LocalPrograms, classic SharePoint publishing with the text in Content Editor web
parts; one GET per page in `PAGES`. Page reader in `connectors/kentucky_sharepoint.py`; status table and field mapping
are the agency-page table in `connectors/hand_list.py`. See docs/connectors/kentucky.md.
"""

from __future__ import annotations

from connectors.kentucky_sharepoint import KyAgency

CONNECTOR = "ky_tc"
BASE = "https://transportation.ky.gov"
AGENCY = "Kentucky Transportation Cabinet, Office of Local Programs"
AGENCY_CODE = "KY-KYTC"
CATEGORY_LABEL = "transportation"
PAGES: dict[str, str] = {
    "tap": "/LocalPrograms/Pages/TAP.aspx",
    "cmaq": "/LocalPrograms/Pages/CMAQ.aspx",
}


class KyTc(KyAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES


SITE = KyTc()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
