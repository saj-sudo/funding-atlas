"""Oklahoma Department of Commerce connector: the state CDBG programs and the Disaster Mitigation and Recovery Matching
Fund (milestone 12.9).

Source: https://www.okcommerce.gov, WordPress with Elementor; one GET per page in `PAGES`. No other Oklahoma agency is
read, so the reader is this module's own. The page's text is the Elementor `single` location (`h1` and content; header,
footer and pop-ups are other locations). The CDBG hub holds seven programs under "Programs", one record each (CIP keeps the
page's `source_id`); its DUNs how-to, meeting dates and State Plan hearing notice are not read, the Coronavirus Relief and
Disaster Recovery entries belong to no record, and the read stops at "Resources". No page states a round: applications
are filed in the Oklahoma Grant Exchange (a login, `Disallow: /`, never fetched). Status table and field mapping are the
agency-page table in `connectors/hand_list.py`. Left out: Main Street (no applicant stated), SITES (2023 and 2024 rounds),
Community Incentives, CSBG/ESG/Weatherization, CDBG-DR.
See docs/connectors/oklahoma.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.hand_list import AgencyPageConnector, applicant_tags, blocks_from, clause_cut, soup
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "ok_commerce"
BASE = "https://www.okcommerce.gov"
AGENCY = "Oklahoma Department of Commerce"
AGENCY_CODE = "OK-COMMERCE"
CATEGORY_LABEL = "community development"
LABEL_MAX_CHARS = 90
BODY_SELECTOR = "div.elementor-location-single"

PAGES: dict[str, str] = {
    "cdbg": "/community-development/local-governments-edos/community-development-block-grant-programs/",
    "odmrmf": "/reporting-compliance/oklahoma-disaster-mitigation-and-recovery-matching-fund-program/",
}
SPLITS = {"cdbg": [
    ("cip", "CDBG Capital Improvement Planning (CIP)", re.compile(r"^Capital Improvement Planning\b", re.I)),
    ("small-cities", "CDBG Small Cities", re.compile(r"^CDBG Small Cities$", re.I)),
    ("community-revitalization", "CDBG Community Revitalization", re.compile(r"^CDBG Community Revitalization$", re.I)),
    ("water-wastewater-construction", "CDBG Water-Wastewater Construction", re.compile(r"^CDBG Water-Wastewater Construction$", re.I)),
    ("edif", "CDBG Economic Development Infrastructure Financing (EDIF)", re.compile(r"^CDBG Economic Development Infrastructure\b", re.I)),
    ("water-wastewater-engineering", "CDBG Water + Wastewater Engineering", re.compile(r"^CDBG Water \+ Wastewater Engineering$", re.I)),
    ("reap", "CDBG Rural Economic Action Plan (REAP)", re.compile(r"^CDBG Rural Economic Action Plan\b", re.I)),
    # a closed one-time appropriation, then the three Disaster Recovery entries (no heading of theirs matches): no record
    ("cv", None, re.compile(r"^CDBG Coronavirus Relief\b", re.I)),
]}
CATEGORY_LABELS = {
    "cdbg#water-wastewater-construction": "environment and water",
    "cdbg#water-wastewater-engineering": "environment and water",
    "odmrmf": "emergency mitigation",
}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
# Sections of the hub that are not a program's text: a how-to for SAM.gov, trainings and meetings, and the State Plan
# hearing notice ("Written comments ... will be accepted until December 18, 2026" is a comment period, not a round).
SKIP_SECTION_RE = re.compile(r"^(?:DUNs Number\b|Save the Dates$|Notice:)", re.I)
DROP_RE = re.compile(r"@okcommerce\.gov|\[email\s*protected\]|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|^return to top$", re.I)
# ODMRMF's purpose ("dedicated state funding to help local governments and related entities secure ... federal ...
# funds") names who benefits; its applicants are the planning districts listed under "Eligible Applicants".
NOT_APPLICANT_RE = re.compile(r"\bfunding to help local governments\b", re.I)
STOP_RE = re.compile(r"(?:resources|policies (?:&|and) procedures|annual reporting|your .* team)$", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and the blocks of the Elementor page body, without the skipped sections, up to "Resources"."""
    doc = soup(page_html)
    body = doc.select_one(BODY_SELECTOR)
    if body is None:
        return {"title": "", "blocks": []}
    h1 = body.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    for junk in body.select("ul.elementor-icon-list-items, form, nav"):
        junk.decompose()
    skipping = False
    skipped = []
    for el in body.find_all(["h2", "h3", "h4", "p", "li"]):
        if el.name == "h2":
            skipping = bool(SKIP_SECTION_RE.match(clean(el.get_text(" "))))
        if skipping:
            skipped.append(el)
    for el in skipped:
        el.extract()
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


class OkCommerce(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "OK"
    CATEGORY_LABEL = CATEGORY_LABEL
    CATEGORY_LABELS = CATEGORY_LABELS
    PAGES = PAGES
    SPLITS = SPLITS
    DELAY_S = 3.0

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        lines = (out["eligibility_text"] or "").split("\n")
        kept = [line for line in lines if not NOT_APPLICANT_RE.search(line)]
        if kept != lines:
            out["eligibility_text"] = "\n".join(kept) or None
            out["applicant_types"] = applicant_tags([clause_cut(line) for line in kept])
        return out


SITE = OkCommerce()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
