"""Indiana Office of Community and Rural Affairs connector: the state CDBG's planning and construction grants and
Stellar Pathways (milestone 12.9).

Source: https://www.in.gov/ocra, the state's shared CMS (dotCMS); one GET per page in `PAGES`. The program's text is in
`main article`; the title is the banner's `#subpage-main-title` (a page whose banner is an image has only a placeholder
`h1`, "Main Billboard", and is titled by its first `h2`). The breadcrumb list is dropped. A tab strip (`ul.nav-tabs` of
buttons, then one `div.tab-pane` per tab) is read as a heading per pane, so the Construction Grants page's five tabs are
five records through `SPLITS` (the Facilities Program keeps the page's `source_id`), each followed by the overview and the
round the page states for all of them. OCRA writes its deadlines as a weekday, a month and a day ("due on Sunday, Dec.
13"): no year, so no `closes_at`; the sentence is kept as `closes_at_text`. Status table and field mapping are the
agency-page table in `connectors/hand_list.py`. Left out: Owner Occupied Rehabilitation (not surveyed), the Historic
Renovation Grant (the page says no further grants will be awarded), COVID-19 Response, Recovery Housing, Disaster
Recovery. See docs/connectors/indiana.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.hand_list import (
    AgencyPageConnector,
    Blocks,
    all_sentences,
    applicant_tags,
    blocks_from,
    clause_cut,
    round_for,
    soup,
)
from connectors.sam_assistance_listings import clean

CONNECTOR = "in_ocra"
BASE = "https://www.in.gov"
AGENCY = "Indiana Office of Community and Rural Affairs"
AGENCY_CODE = "IN-OCRA"
CATEGORY_LABEL = "community development"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "cdbg-planning": "/ocra/cdbg/planning-grants",
    "cdbg-construction": "/ocra/cdbg/cdbg-construction-grants",
    "stellar": "/ocra/stellar/index",
}
# The page's titles are "Planning Grants" and "Stellar Pathways Program"; the first is named for the program it is part of.
NAMES = {"Planning Grants": "CDBG Planning Grants"}
# One record per tab of the Construction Grants page; the names are the tabs' own, with the page's "CDBG" in front.
SPLITS = {"cdbg-construction": [
    ("cdbg-construction", "CDBG Facilities Program", re.compile(r"^Facilities Program$", re.I)),
    ("blight-clearance", "CDBG Blight Clearance Program", re.compile(r"^Blight Clearance Program$", re.I)),
    ("stormwater", "CDBG Stormwater Improvements Program", re.compile(r"^Stormwater Improvements$", re.I)),
    ("main-street", "CDBG Main Street Revitalization Program", re.compile(r"^Main Street Revitalization$", re.I)),
    ("water", "CDBG Wastewater/Drinking Water Program", re.compile(r"^Wastewater/Drinking Water$", re.I)),
]}
CATEGORY_LABELS = {"cdbg-construction#stormwater": "stormwater", "cdbg-construction#water": "wastewater"}
# Stellar is state money from several agencies; its page names CDBG only to exclude entitlement communities.
FUNDING_SOURCES = {"stellar": "direct"}
# The Planning Grants page names no applicant ("communities"); the CDBG hub it sits under does.
HAND_QUOTES = {"cdbg-planning": ("2026-11-24", "OCRA's CDBG page (https://www.in.gov/ocra/cdbg/index)", [
    "The State CDBG Program provides grants exclusively to Indiana’s non-entitlement local governments.",
    "These include cities with populations under 50,000 (excluding cities of Metropolitan Statistical Areas) and counties "
    "with populations under 200,000.",
])}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"@ocra\.in\.gov|\[email\s*protected\]|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b"
                     r"|^\*?for questions regarding\b|^register for one of\b", re.I)
# Stellar: the documents list, then past designees and statistics.
STOP_RE = re.compile(r"(?:resources|stellar pathways \d{4} designees.*)$", re.I)
# "Applications are due on Sunday, July 12, by 11:59 p.m. ET", "2026 Round 2 applications are due on Sunday, Dec. 13":
# a weekday, a month and a day. Stellar: "workshops will take place on Tuesday, Oct. 27, and Friday, Oct. 30" (an
# applicant must attend one to apply; the page states no other date).
YEARLESS_RE = re.compile(r"\bapplications are due on \w+, \w+\.? \d{1,2}\b|\bworkshops will take place on\b", re.I)
# Stellar: "The lead applicant can be any county government, city, municipality, town, township, or a non-profit that ...".
LEAD_APPLICANT_RE = re.compile(r"\blead applicant can be\b", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title and the blocks of `main article`, each tab pane under a heading of its tab's name."""
    doc = soup(page_html)
    body = doc.select_one("main article") or doc.find("main")
    if body is None:
        return {"title": "", "blocks": []}
    h1 = body.select_one("#subpage-main-title") or body.find("h2") or body.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    # the tab strip's buttons name the panes that follow it
    for pane in body.select("div.tab-pane"):
        button = body.find(id=pane.get("aria-labelledby") or "-")
        if button is not None:
            heading = doc.new_tag("h4")
            heading.string = clean(button.get_text(" "))
            pane.insert_before(heading)
    for gone in body.select("#subpage-breadcrumbs, ul.nav-tabs"):
        gone.decompose()
    # A card list wraps paragraphs in list items ("<li><p>Enhancing Local Planning</p><ul><li><p>...") : read the paragraphs.
    for li in body.find_all("li"):
        if li.find("p"):
            li.name = "div"
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(body, ["h2", "h3", "h4", "h5", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    blocks = [b for b in blocks if b != ("label", title)]
    return {"title": NAMES.get(title, title), "blocks": blocks}


class InOcra(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "IN"
    CATEGORY_LABEL = CATEGORY_LABEL
    CATEGORY_LABELS = CATEGORY_LABELS
    PAGES = PAGES
    DELAY_S = 3.0
    SPLITS = SPLITS
    FUNDING_SOURCES = FUNDING_SOURCES
    HAND_QUOTES = HAND_QUOTES

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: Any, today: date) -> dict[str, Any]:
        """The agency-page fields, with the page's "lead applicant can be ..." sentence among the eligibility lines."""
        out = super().fields(raw, today)
        blocks = [tuple(b) for b in raw.payload["page"].get("blocks", [])]
        lead = [s for s in all_sentences(blocks) if LEAD_APPLICANT_RE.search(s)]
        if lead:
            lines = lead + [x for x in (out["eligibility_text"] or "").split("\n") if x and x not in lead]
            out["eligibility_text"] = "\n".join(lines)
            out["applicant_types"] = applicant_tags([clause_cut(line) for line in lines])
        return out

    def round_with_yearless(self, blocks: Blocks, today: date) -> dict[str, Any]:
        """The agency-page round; where it finds no date, the page's own yearless deadline sentence is the text kept,
        beside whatever status the page's wording gives ("now accepting applications for the 2026 Round 2": open)."""
        out = round_for(blocks, today)
        if out["closes_at"] is None:
            out["closes_at_text"] = next((s for s in all_sentences(blocks) if YEARLESS_RE.search(s)), out["closes_at_text"])
        return out


SITE = InOcra()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
