"""Missouri State Emergency Management Agency connector: the programs on its Programs pages that fund or reimburse local
governments.

Source: https://sema.dps.mo.gov, a Department of Public Safety site on an older CMS (`.php` pages, a Bootstrap layout, no
`.node__content`): the program is in `#main-content`, its name the page's `h1`, its sections `h2` headings and accordion
panels in the static HTML. The page reader is the Missouri base with that selector; status table and field mapping are
the agency-page table in `connectors/hand_list.py`. See docs/connectors/missouri.md.
"""

from __future__ import annotations

from connectors.missouri_drupal import MoAgency

CONNECTOR = "mo_sema"
BASE = "https://sema.dps.mo.gov"
AGENCY = "Missouri State Emergency Management Agency"
AGENCY_CODE = "MO-SEMA"
CATEGORY_LABEL = "emergency management"
PAGES: dict[str, str] = {
    "mdag": "/programs/mdag/index.html",
    "mitigation": "/programs/mitigation_management.php",
    "public-assistance": "/programs/state_public_assistance.php",
    "empg": "/programs/empg.php",
}
# The Mitigation Management page covers HMGP, FMA and BRIC in sections that interleave (HMGP's process is described in two
# places, between shared eligibility and planning blocks), so it stays one record, named for what it is.
NAMES = {"mitigation": "Hazard Mitigation Assistance Grants (HMGP, FMA, BRIC)"}


class MoSema(MoAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    BODY_SELECTOR = "#main-content"
    NAMES = NAMES


SITE = MoSema()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
