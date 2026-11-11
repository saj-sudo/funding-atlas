"""Missouri Department of Natural Resources connector: the Financial Assistance pages of its water, energy and waste
programs that take applications from local governments and public bodies.

Source: https://dnr.mo.gov, the state's Drupal 10 theme; one GET per page in `PAGES`. Page reader in
`connectors/missouri_drupal.py`; status table and field mapping are the agency-page table in `connectors/hand_list.py`.
Every program page has the same template: an "Application Period is Open" or "... is Closed" heading, then "Who Can
Apply", "Eligible Projects and Costs", "Award Amounts and Match" and "Application Process". Left out: the Grid Resilience subgrants (applicants are electric utilities and grid operators, not local governments); programs whose
applicants are not public bodies (the CWSRF on-site grant, a pass-through to nonprofits for homeowners; the scrap tire
reimbursement, nonprofits only; the operator training voucher, individuals; the wood energy and weatherization
programs, businesses and households), and pages that are a service or a forms list (Brownfields Assessments, Solid Waste
Management District Grants). State Parks and Historic Preservation grants live on mostateparks.com and are another
connector. See docs/connectors/missouri.md.
"""

from __future__ import annotations

from connectors.missouri_drupal import MoAgency

CONNECTOR = "mo_dnr"
BASE = "https://dnr.mo.gov"
AGENCY = "Missouri Department of Natural Resources"
AGENCY_CODE = "MO-DNR"
CATEGORY_LABEL = "environment and water"
_W = "/water/financial-assistance-opportunities"
_E = "/energy/financial-assistance-opportunities"
PAGES: dict[str, str] = {
    "small-borrower-loan": f"{_W}/clean-drinking-water-small-borrower-loan",
    "cwsrf-engineering-report": f"{_W}/clean-water-state-revolving-fund-cwsrf-engineering-report-grants",
    "cwsrf-integrated-management-plan": f"{_W}/clean-water-state-revolving-fund-cwsrf-integrated-management-plan-grants",
    "cwsrf-loan": f"{_W}/clean-water-state-revolving-fund-cwsrf-loan",
    "cwsrf-regionalization": f"{_W}/clean-water-state-revolving-fund-cwsrf-regionalization-incentive-grant",
    "dwsrf-engineering-report": f"{_W}/drinking-water-state-revolving-fund-dwsrf-engineering-report-grants",
    "dwsrf-lead-service-line": f"{_W}/drinking-water-state-revolving-fund-dwsrf-lead-service-line",
    "dwsrf-loan": f"{_W}/drinking-water-state-revolving-fund-dwsrf-loan",
    "flood-resiliency": f"{_W}/flood-resiliency-improvement-grants",
    "multipurpose-water-resource": f"{_W}/multipurpose-water-resource-program-fund",
    "section-319": f"{_W}/section-319-nonpoint-source-subgrants",
    "section-604b": f"{_W}/section-604b-water-quality-management-planning-grant",
    "source-water-protection": f"{_W}/source-water-protection-project-grant",
    "water-safety-security": "/water/what-were-doing/financial-assistance-opportunities/water-safety-security-act-project-grant",
    "well-plugging": f"{_W}/well-plugging-grant",
    "energy-audit": f"{_E}/audit-reimbursements",
    "energy-loans": f"{_E}/loans",
    "energy-emergency-loans": f"{_E}/emergency-loans",
    "eecbg": f"{_E}/efficiency-conservation-block-grant",
    "scrap-tire-surface": "/waste-recycling/financial-assistance-opportunities/scrap-tire-surface-material-grant",
}
# The portal-style topic each record carries (labels the shared table already knows); a record not listed here is water.
CATEGORY_LABELS: dict[str, str] = {
    "small-borrower-loan": "clean water", "cwsrf-engineering-report": "clean water", "cwsrf-integrated-management-plan": "clean water",
    "cwsrf-loan": "clean water", "cwsrf-regionalization": "clean water",
    "dwsrf-engineering-report": "drinking water", "dwsrf-lead-service-line": "drinking water", "dwsrf-loan": "drinking water",
    "source-water-protection": "drinking water", "water-safety-security": "drinking water",
    "flood-resiliency": "emergency mitigation", "section-319": "non-point source", "section-604b": "water quality",
    "well-plugging": "water quality",
    "energy-audit": "energy", "energy-loans": "energy", "energy-emergency-loans": "energy", "eecbg": "energy",
    "scrap-tire-surface": "waste and recycling",      # not a label the table knows: `other`
}
# Where the page itself names a federal source of the money (the sentence is quoted in docs/connectors/missouri.md); the
# loans and the state-funded programs name none and stay `direct`.
FUNDING_SOURCES: dict[str, str] = {slug: "pass_through" for slug in (
    "cwsrf-engineering-report", "cwsrf-integrated-management-plan", "cwsrf-regionalization",   # "capitalization grant"
    "dwsrf-engineering-report", "dwsrf-lead-service-line",                                    # "capitalization grant"; "Bipartisan Infrastructure Law"
    "section-319", "section-604b",                                                            # "Funding is provided by EPA"; the federal Clean Water Act
    "source-water-protection", "water-safety-security", "well-plugging",                      # DWSRF set-asides under the federal Safe Drinking Water Act
    "eecbg",                                                                                  # "a formula grant offered as a part of the Bipartisan Infrastructure Law"
)}


class MoDnr(MoAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    CATEGORY_LABELS = CATEGORY_LABELS
    FUNDING_SOURCES = FUNDING_SOURCES


SITE = MoDnr()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
