"""Vermont Emergency Management connector: the three Funding Opportunities pages.

Source: https://vem.vermont.gov, vermont.gov's Drupal 10 theme; one GET per page in `PAGES`. Page reader, status table and field mapping
are the Vermont base (`connectors/vermont_drupal.py`). See docs/connectors/vermont.md.
"""

from __future__ import annotations

import re

from connectors.vermont_drupal import VermontAgency

CONNECTOR = "vt_vem"
BASE = "https://vem.vermont.gov"
AGENCY = "Vermont Emergency Management"
AGENCY_CODE = "VT-VEM"
CATEGORY_LABEL = "emergency management"
PAGES: dict[str, str] = {
    "empg": "/funding/empg",
    "mitigation": "/funding/mitigation",
    "pa": "/funding/pa",
}
# The Hazard Mitigation page is HMGP's own body (project types, 25% match, disaster rounds) followed, under "2026 Hazard
# Mitigation Funding Opportunities", by one paragraph per program that starts with its name. HMGP is the head of the page
# and keeps the page's id (`mitigation`); the three paragraphs are FRCF, BRIC and FMA. See docs/connectors/vermont.md.
SPLITS = {
    "mitigation": [
        ("mitigation", "Hazard Mitigation Grant Program (HMGP)", None),
        ("funding-heading", None, re.compile(r"^2026 Hazard Mitigation Funding Opportunities", re.I)),
        ("frcf", "Flood Resilient Communities Fund (FRCF)", re.compile(r"^Flood Resilient Communities Fund", re.I)),
        ("bric", "Building Resilient Infrastructure and Communities (BRIC)", re.compile(r"^Building Resilient Infrastructure and Communities", re.I)),
        ("fma", "Flood Mitigation Assistance (FMA)", re.compile(r"^Flood Mitigation Assistance", re.I)),
    ],
}
SPLIT_KINDS = {"mitigation": ("label", "p")}
# The Flood Resilient Communities Fund "was established by the Vermont Legislature under Act 74" and "will prioritize
# projects that are not eligible for FEMA funding": a state fund that names FEMA, not a federal pass-through.
FUNDING_SOURCES = {"mitigation#frcf": "direct"}


class Vem(VermontAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    SPLITS = SPLITS
    SPLIT_KINDS = SPLIT_KINDS
    FUNDING_SOURCES = FUNDING_SOURCES


SITE = Vem()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
