"""Missouri Department of Economic Development connector: the Community Development Block Grants (CDBG) program pages
that take applications from communities.

Source: https://ded.mo.gov, the state's Drupal 10 theme; one GET per page in `PAGES`. Page reader in
`connectors/missouri_drupal.py`; status table and field mapping are the agency-page table in `connectors/hand_list.py`.
The Competitive Cycle and Economic Development pages each hold several programs under two tabs ("Description", then
"Do I Qualify?"), so each is one record per program (`SPLITS`, `TABBED`). Left out (Saj's call, the Kentucky CDBG-DR
precedent): the Disaster Recovery, Mitigation and COVID-19 pages, whose funds are exhausted or closed for good, and the
CDBG home page, which carries notices and no program. See docs/connectors/missouri.md.
"""

from __future__ import annotations

import re

from connectors.missouri_drupal import MoAgency

CONNECTOR = "mo_ded"
BASE = "https://ded.mo.gov"
AGENCY = "Missouri Department of Economic Development, Community Development Block Grants"
AGENCY_CODE = "MO-DED"
CATEGORY_LABEL = "community development"
_CDBG = "/programs/community/community-development-block-grants"
PAGES: dict[str, str] = {
    "competitive-cycle": f"{_CDBG}-competitive-cycle",
    "economic-development": f"{_CDBG}-economic-development",
    "emergency": f"{_CDBG}-emergency-long-term-recovery",
    "water-wastewater": f"{_CDBG}-waterwastewater",
}
# slug -> [(sub_slug, name, heading pattern)]; the first declared program keeps the page's own source_id.
SPLITS = {
    "competitive-cycle": [
        ("community-facilities", "CDBG Community Facilities", re.compile(r"^Community Facilities$", re.I)),
        ("general-infrastructure", "CDBG General Infrastructure", re.compile(r"^General Infrastructure$", re.I)),
        ("demolition", "CDBG Demolition", re.compile(r"^Demolition$", re.I)),
    ],
    "economic-development": [
        ("downtown-revitalization", "CDBG Downtown Revitalization", re.compile(r"^Downtown Revitalization$", re.I)),
        ("industrial-infrastructure", "CDBG Industrial Infrastructure", re.compile(r"^Industrial Infrastructure$", re.I)),
    ],
}


# Every DED page here is a part of the state's CDBG program: HUD money the state passes on to communities. Only the pages
# that happen to print "HUD" would say so otherwise, and one HUD program should not read as two funding sources.
SOURCE_IDS = [slug if i == 0 else f"{slug}#{sub}" for slug, parts in SPLITS.items() for i, (sub, _, _) in enumerate(parts)]
SOURCE_IDS += [slug for slug in PAGES if slug not in SPLITS]


class MoDed(MoAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    SPLITS = SPLITS
    TABBED = {slug: True for slug in SPLITS}
    FUNDING_SOURCES = {sid: "pass_through" for sid in SOURCE_IDS}


SITE = MoDed()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
