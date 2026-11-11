"""Missouri State Parks connector: the grant programs of the Department of Natural Resources' Division of State Parks
that take applications from local governments, school districts and nonprofits.

Source: https://mostateparks.com, the state's Drupal 10 theme; one GET per page in `PAGES`. Page reader in
`connectors/missouri_drupal.py`; status table and field mapping are the agency-page table in `connectors/hand_list.py`.
ORLP has no page of its own: it is a section of the Grant Opportunities hub, read through `SPLITS`, with the hub's list of
open rounds and its other programs' sections as tails that belong to no record (so LWCF's and the bus grant's deadlines
cannot reach it). Left out: the Certified Local Government page (a designation program; its money is the Historic
Preservation Fund's pass-through), Grant Workshops (an event list) and the lists of past recipients. See
docs/connectors/missouri.md.
"""

from __future__ import annotations

import re

from connectors.missouri_drupal import MoAgency

CONNECTOR = "mo_parks"
BASE = "https://mostateparks.com"
AGENCY = "Missouri Department of Natural Resources, Division of State Parks"
AGENCY_CODE = "MO-PARKS"
CATEGORY_LABEL = "parks and recreation"
PAGES: dict[str, str] = {
    "lwcf": "/basic-page/land-and-water-conservation-fund-lwcf-grants",
    "rtp": "/page/recreational-trails-program-rtp-grants",
    "orlp": "/page/grant-opportunities",
    "bus": "/page/missouri-state-parks-bus-grant-program",
    "hpf": "/page/state-historic-preservation-office/historic-preservation-fund-grants",
}
# The hub: ORLP's own section is the record; the top list of open rounds and the sections from RTP on are tails.
SPLITS = {
    "orlp": [
        ("orlp", "Outdoor Recreation Legacy Partnership Program (ORLP)", re.compile(r"^Outdoor Recreation Legacy Partnership Program \(ORLP\)$", re.I)),
        ("open-rounds", None, re.compile(r"^Grants Currently Accepting Applications:?$", re.I)),
        ("rtp", None, re.compile(r"^Recreational Trails Program$", re.I)),
    ],
}
# The pages that do not name a federal agency in a way the shared table reads. LWCF says "Federal funding" and the hub names the
# National Park Service; the RTP and HPF pages name no federal agency, and the hub says RTP is "federally funded through the
# Department of Transportation's Federal Highway Administration" and HPF "federally funded through the National Park Service";
# the bus grant is "one state-funded grant program".
FUNDING_SOURCES = {"lwcf": "pass_through", "rtp": "pass_through", "hpf": "pass_through", "bus": "direct"}


class MoParks(MoAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    SPLITS = SPLITS
    FUNDING_SOURCES = FUNDING_SOURCES
    # the trails and preservation grants carry their own portal-style topic
    CATEGORY_LABELS = {"rtp": "parks and recreation", "hpf": "parks and recreation"}


SITE = MoParks()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
