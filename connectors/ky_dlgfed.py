"""Kentucky Department for Local Government connector: the federal grant programs it administers for cities and
counties (CDBG's program areas, Appalachian Regional Commission, Delta Regional Authority, Land and Water Conservation
Fund, Recreational Trails Program, Recovery Housing Program).

Source: https://dlg.ky.gov/grants/federal, classic SharePoint publishing; one GET per page in `PAGES`. Page reader in
`connectors/kentucky_sharepoint.py`; status table and field mapping are the agency-page table in
`connectors/hand_list.py`. The state-funded programs (LMPP, RDAAP, Line-Items, Coal Severance) are read by `ky_dlg` from
the DLG Portal and are not repeated here; CDBG-DR and the CDBG overview and training pages are not programs a town
applies to. See docs/connectors/kentucky.md.
"""

from __future__ import annotations

from connectors.kentucky_sharepoint import KyAgency

CONNECTOR = "ky_dlgfed"
BASE = "https://dlg.ky.gov"
AGENCY = "Kentucky Department for Local Government"
AGENCY_CODE = "KY-DLG"
CATEGORY_LABEL = "community development"
PAGES: dict[str, str] = {
    "arc": "/grants/federal/arc/Pages/default.aspx",
    "dra": "/grants/federal/dra/Pages/default.aspx",
    "lwcf": "/grants/federal/lwcf/Pages/default.aspx",
    "rtp": "/grants/federal/rtp/Pages/default.aspx",
    "rhp": "/grants/federal/rhp/Pages/default.aspx",
    "cdbg-community": "/grants/federal/cdbg/Pages/Community-Projects.aspx",
    "cdbg-emergency": "/grants/federal/cdbg/Pages/Community-Emergency-Relief-Fund.aspx",
    "cdbg-economic": "/grants/federal/cdbg/Pages/Economic-Development.aspx",
    "cdbg-housing": "/grants/federal/cdbg/Pages/Housing-Program.aspx",
    "cdbg-facilities": "/grants/federal/cdbg/Pages/Public-Facilities.aspx",
    "cdbg-rky": "/grants/federal/cdbg/RKY/Pages/default.aspx",
}
# One agency, several topics: the label a page's own program would carry on a portal.
CATEGORY_LABELS = {
    "lwcf": "parks and recreation", "rtp": "parks and recreation", "rhp": "housing", "cdbg-housing": "housing",
    "cdbg-emergency": "disaster recovery", "cdbg-economic": "economic development", "cdbg-facilities": "wastewater",
    "cdbg-rky": "health",
}


class KyDlgFed(KyAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    CATEGORY_LABELS = CATEGORY_LABELS


SITE = KyDlgFed()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
