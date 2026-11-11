"""Missouri Department of Transportation connector: the two pages of its Local Public Agency (LPA) section that are
funding programs open to applications, the Transportation Alternatives Program and Partnership Development.

Source: https://www.modot.org, the state's Drupal 10 theme; one GET per page in `PAGES`. Page reader in
`connectors/missouri_drupal.py`; status table and field mapping are the agency-page table in `connectors/hand_list.py`.
MoDOT's other money for local governments (the surface transportation block grant, off-system bridges, FTA formula funds)
is allocated to metropolitan planning organizations and counties by formula and has no application page, and its
aviation, transit, freight, rail and waterways pages describe the sections and name no round, so none is read. See
docs/connectors/missouri.md.
"""

from __future__ import annotations

from connectors.missouri_drupal import MoAgency

CONNECTOR = "mo_modot"
BASE = "https://www.modot.org"
AGENCY = "Missouri Department of Transportation"
AGENCY_CODE = "MO-MODOT"
CATEGORY_LABEL = "transportation"
PAGES: dict[str, str] = {
    "tap": "/transportation-alternatives-program-tap",
    "partnership-development": "/partnership-development",
}
# The page's last `h1` is its application form's heading ("Partnership Development Application").
NAMES = {"partnership-development": "Partnership Development"}


class MoModot(MoAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    NAMES = NAMES


SITE = MoModot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
