"""Kentucky Energy and Environment Cabinet connector: the grant programs on the Cabinet's own Grants and Loans page
(Illegal Dump Cleanup, Litter Abatement, Nonpoint Source Pollution Control, Waste Tire, Recycling and Household
Hazardous Waste, Source Water Protection Assistance).

Source: https://eec.ky.gov/Environmental-Protection/resources/Pages/grants-and-loans.aspx, classic SharePoint
publishing. One page holds every program, each under an `h4` with four labelled lines (Administering Agency, Type of
Funding, Funding Source, Eligible Entities) and a paragraph, so one GET makes one record per program (`SPLITS`,
`connectors/hand_list.py`). Left out of the records: the two state revolving funds (KIA's Funds A and F, read by
`ky_kia`) and the Underground Storage Tank claim payments (reimbursement to tank owners, not a town). Page reader in
`connectors/kentucky_sharepoint.py`. See docs/connectors/kentucky.md.
"""

from __future__ import annotations

import re

from connectors.kentucky_sharepoint import KyAgency

CONNECTOR = "ky_eec"
BASE = "https://eec.ky.gov"
AGENCY = "Kentucky Energy and Environment Cabinet"
AGENCY_CODE = "KY-EEC"
CATEGORY_LABEL = "environment"
PAGES: dict[str, str] = {"illegal-dump": "/Environmental-Protection/resources/Pages/grants-and-loans.aspx"}
SPLITS = {
    "illegal-dump": [
        ("illegal-dump", "Illegal Dump Cleanup Grant Program", re.compile(r"^Illegal Dump Cleanup", re.I)),
        ("litter-abatement", "Litter Abatement Grant Program", re.compile(r"^Litter Abatement", re.I)),
        ("nonpoint-source", "Nonpoint Source Pollution Control Grant", re.compile(r"^Nonpoint Source", re.I)),
        ("waste-tire", "Waste Tire Grant Program", re.compile(r"^Waste Tire", re.I)),
        ("recycling-hhw", "Recycling and Household Hazardous Waste Grant Collection Program", re.compile(r"^Recycling and Household", re.I)),
        ("swpap", "Source Water Protection Assistance Program (SWPAP)", re.compile(r"^Source Water Protection", re.I)),
        # KIA's Funds A and F (the heading's first letter is a separate span, so it reads "C lean Water ...")
        ("cwsrf", None, re.compile(r"^C\s?lean Water State Revolving", re.I)),
        ("dwsrf", None, re.compile(r"^Drinking Water State Revolving", re.I)),
        ("ust", None, re.compile(r"^Underground Storage Tank", re.I)),
    ],
}
# The programs' own labels; the waste programs fall to `other` (the portal table has no waste or environment topic).
CATEGORY_LABELS = {"illegal-dump#nonpoint-source": "non-point source", "illegal-dump#swpap": "drinking water"}


class KyEec(KyAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    SPLITS = SPLITS
    CATEGORY_LABELS = CATEGORY_LABELS


SITE = KyEec()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
