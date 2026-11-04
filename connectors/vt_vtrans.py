"""Vermont Agency of Transportation connector: the Municipal Assistance grant pages.

Source: https://vtrans.vermont.gov, vermont.gov's Drupal 10 theme; one GET per page in `PAGES`. Page reader, status table and field mapping
are the Vermont base (`connectors/vermont_drupal.py`). See docs/connectors/vermont.md.
"""

from __future__ import annotations

from connectors.vermont_drupal import VermontAgency

CONNECTOR = "vt_vtrans"
BASE = "https://vtrans.vermont.gov"
AGENCY = "Vermont Agency of Transportation"
AGENCY_CODE = "VT-VTRANS"
CATEGORY_LABEL = "transportation"
PAGES: dict[str, str] = {
    "transport-alt": "/highway/local-projects/transport-alt",
    "mhsmp": "/highway/Municipal-Highway-and-Stormwater-Mitigation-Program",
    "grants-in-aid": "/highway/Municipal-Grant-in-aid-Program",
    "better-roads": "/highway/better-roads",
    "bike-ped": "/highway/local-projects/bike-ped",
}


# The TAP and MHSMP pages name no applicant; their joint guidebook does, under "Eligible Applicants:" (page 6). One list
# for both programs: the guidebook does not split it. Each bullet's opening sentence, verbatim.
GUIDEBOOK = "VTrans TAP and MHSMP Grant Guidebook, October 2026 (PDF), Eligible Applicants"
GUIDEBOOK_LINES = [
    "A local government. Local government entities include any unit of local government below a State government agency.",
    "A regional transportation authority.",
    "A transit agency.",
    "A natural resource or public land agency.",
    "A school district, local education agency, or school.",
    "A Tribal government.",
    "A nonprofit entity.",
    "A State, at the request of an eligible entity listed above.",
]
HAND_QUOTES: dict[str, tuple[str, str, list[str]]] = {
    "transport-alt": ("2026-11-04", GUIDEBOOK, GUIDEBOOK_LINES),
    "mhsmp": ("2026-11-04", GUIDEBOOK, GUIDEBOOK_LINES),
}


class Vtrans(VermontAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    HAND_QUOTES = HAND_QUOTES


SITE = Vtrans()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
