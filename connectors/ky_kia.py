"""Kentucky Infrastructure Authority connector: the four loan funds (A wastewater, B infrastructure, C governmental,
F drinking water) and the Cleaner Water grants.

Source: https://kia.ky.gov/FinancialAssistance, classic SharePoint publishing; one GET per page in `PAGES`. Page reader
in `connectors/kentucky_sharepoint.py`; status table and field mapping are the agency-page table in
`connectors/hand_list.py`. The fund names carry no funding-type keyword, so `FUNDING_TYPES` says `loan`. The Energy and
Environment Cabinet's index lists the two state revolving funds too; they are KIA's Funds A and F and are read here
only. See docs/connectors/kentucky.md.
"""

from __future__ import annotations

from connectors.kentucky_sharepoint import KyAgency

CONNECTOR = "ky_kia"
BASE = "https://kia.ky.gov"
AGENCY = "Kentucky Infrastructure Authority"
AGENCY_CODE = "KY-KIA"
CATEGORY_LABEL = "infrastructure"
PAGES: dict[str, str] = {
    "fund-a": "/FinancialAssistance/Pages/Fund-A---Wastewater.aspx",
    "fund-b": "/FinancialAssistance/Pages/Fund-B---Infrastructure.aspx",
    "fund-c": "/FinancialAssistance/Pages/Fund-C---Governmental.aspx",
    "fund-f": "/FinancialAssistance/Pages/Fund-F---Drinking-Water.aspx",
    "cleaner-water": "/FinancialAssistance/Pages/Cleaner-Water-Program-Grant.aspx",
}
FUNDING_TYPES = {"fund-a": "loan", "fund-b": "loan", "fund-c": "loan", "fund-f": "loan", "cleaner-water": "grant"}
CATEGORY_LABELS = {"fund-a": "wastewater", "fund-f": "drinking water", "cleaner-water": "drinking water"}


class KyKia(KyAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    FUNDING_TYPES = FUNDING_TYPES
    CATEGORY_LABELS = CATEGORY_LABELS


SITE = KyKia()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
