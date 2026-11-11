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
# Funds B, C and F say "The applicant must be a governmental agency" (Fund F: "Governmental agencies, other than federal
# agencies") and name no type; the tagger cannot read the phrase, and as a shared rule it would move about fifty federal and
# Texas records the statute does not govern. The statute defines the term, so its words are quoted here, dated and attributed
# (the MDOT, Illinois and Vermont precedent), for the three pages that use it. Fund A's page names no applicant and is not
# quoted. "but not by way of limitation" is cut with [...]: the tagger drops a sentence that holds a negation. The districts
# stay in the stored text untagged (no shared "water district" rule). Saj's call, 2026-11-11; docs/connectors/kentucky.md.
GOVERNMENTAL_AGENCY = (
    "2026-11-11", 'KRS 224A.011(21), definition of "governmental agency"', [
        '"Governmental agency" means any incorporated city or municipal corporation, or other agency, or unit of government '
        "within or a department or a cabinet of the Commonwealth of Kentucky, now having or hereafter granted, the authority "
        "and power to finance, acquire, construct, or operate infrastructure or solid waste projects.",
        "This definition shall specifically apply [...] to incorporated cities; counties, including any counties containing a "
        "metropolitan sewer district; sanitation districts; water districts; water associations; sewer construction districts; "
        "metropolitan sewer districts; sanitation taxing districts; a regional wastewater commission established under KRS "
        "65.8901 to 65.8923; and any other agencies, commissions, districts, or authorities [...].",
    ])
HAND_QUOTES = {"fund-b": GOVERNMENTAL_AGENCY, "fund-c": GOVERNMENTAL_AGENCY, "fund-f": GOVERNMENTAL_AGENCY}


class KyKia(KyAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    FUNDING_TYPES = FUNDING_TYPES
    CATEGORY_LABELS = CATEGORY_LABELS
    HAND_QUOTES = HAND_QUOTES


SITE = KyKia()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
