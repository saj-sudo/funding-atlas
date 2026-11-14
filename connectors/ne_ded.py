"""Nebraska Department of Economic Development connector: the programs of its Programs section that take applications
from local governments (milestone 12.6g).

Source: https://opportunity.nebraska.gov, WordPress; one GET per page in `PAGES`, three seconds apart (the robots file
asks for `Crawl-delay: 3`, and disallows every URL with a query string, so only plain paths are read). The program's own
text sits in `div.entry-content`. Status table and field mapping are the agency-page table in `connectors/hand_list.py`.
The CDBG page holds six funding opportunities under one heading ("CDBG Funding Opportunities & Application Deadlines"),
so it is one record per opportunity (`SPLITS`). Left out: the programs whose applicants are nonprofits, developers or
CHDOs (HOME, the Housing Trust Fund, the two workforce housing funds), tax credits and designations, the Municipal Inland
Port Authority Act (a statute that creates authorities; its money is an SBDF subaccount) and the one-time ARPA pages that
accept "public and private entities". See docs/connectors/nebraska.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "ne_ded"
BASE = "https://opportunity.nebraska.gov"
AGENCY = "Nebraska Department of Economic Development"
AGENCY_CODE = "NE-DED"
CATEGORY_LABEL = "community development"
BODY_SELECTOR = "div.entry-content"
LABEL_MAX_CHARS = 90
CRAWL_DELAY_S = 3.0

PAGES: dict[str, str] = {
    "cdbg": "/programs/community/cdbg/",
    "cccff": "/programs/community/cccff/",
    "nahtf": "/programs/housing/nahtf/",
    "rcrp": "/programs/housing/rcrp/",
    "sbdf": "/programs/business/sbdf/",
}

# slug -> [(sub_slug, name, heading pattern)]; the first declared program keeps the page's own source_id.
SPLITS = {
    "cdbg": [
        ("economic-development", "CDBG Economic Development", re.compile(r"^Economic Development$", re.I)),
        ("public-works-infrastructure", "CDBG Public Works - Infrastructure", re.compile(r"^Public Works\s*[-–]\s*Infrastructure$", re.I)),
        ("planning", "CDBG Planning", re.compile(r"^Planning$", re.I)),
        ("tourism-development", "CDBG Tourism Development", re.compile(r"^Tourism Development$", re.I)),
        ("public-works-facilities", "CDBG Public Works - Facilities", re.compile(r"^Public Works\s*[-–]\s*Facilities$", re.I)),
        ("downtown-revitalization", "CDBG Downtown Revitalization", re.compile(r"^Downtown Revitalization$", re.I)),
    ],
}
SOURCE_IDS = [slug if i == 0 else f"{slug}#{sub}" for slug, parts in SPLITS.items() for i, (sub, _, _) in enumerate(parts)]

# The breadcrumb line, contact lines, and the page's calls to action.
DROP_RE = re.compile(r"^Home\s*/|@nebraska\.gov|\b\d{3}-\d{3}-\d{4}\b|\(\d{3}\)\s?\d{3}-\d{4}", re.I)
# Where a program's own text ends: its resources, news and contact blocks (press-release dates would read as rounds).
STOP_RE = re.compile(r"(?:program resources|grant management resources|press releases|make sure you hear from us\.?"
                     r"|have questions\??|need help with .*|questions about .*)$", re.I)


# "Application Deadline: Sept. 15": a deadline word, a month and a day, no year.
YEARLESS_DEADLINE_RE = re.compile(r"^application deadline:\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\s*$", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the first `h1` of the body: CCCFF's photo captions are `h1`s too) and the body's blocks."""
    doc = soup(page_html)
    body = doc.select_one(BODY_SELECTOR)
    if body is None:
        h1 = doc.find("h1")
        return {"title": clean(h1.get_text(" ")) if h1 else "", "blocks": []}
    h1 = body.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    # A short paragraph ending in a colon ("Who is eligible to apply? Eligible applicants include:") is the page's label
    # for the list after it (NAHTF); the North Dakota reader does the same.
    blocks = [("label" if k == "p" and t.endswith(":") and len(t) <= LABEL_MAX_CHARS else k, t) for k, t in blocks]
    return {"title": title, "blocks": blocks}


class NeDed(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "NE"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    SPLITS = SPLITS
    DELAY_S = CRAWL_DELAY_S
    # CDBG is HUD money the state passes on to communities; the four CDBG opportunities share one page that says so once.
    # RCRP's page: "established ... pursuant to the American Rescue Plan Act of 2021 (ARPA)", which the shared federal-agency
    # words do not name; the Trust Fund, CCCFF and SBDF are state money and stay `direct`.
    FUNDING_SOURCES = {**{sid: "pass_through" for sid in SOURCE_IDS}, "rcrp": "pass_through"}
    CATEGORY_LABELS = {"nahtf": "housing", "rcrp": "housing"}

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        # CDBG states "Application Deadline: Sept. 15" with no year: not a date, so the status stays `unknown` and
        # `closes_at` null, but the sentence is kept for the reader.
        if out["status"] == "unknown" and not out["closes_at_text"]:
            blocks = [tuple(b) for b in raw.payload["page"].get("blocks", [])]
            out["closes_at_text"] = next((t for _, t in blocks if YEARLESS_DEADLINE_RE.search(t)), None)
        return out


SITE = NeDed()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
