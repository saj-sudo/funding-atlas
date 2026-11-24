"""Louisiana Office of Community Development connector: three Local Government Assistance pages (milestone 12.9).

Source: https://locd.la.gov (the office left `www.doa.la.gov` for its own site; `robots.txt` is `Allow: /`), one GET per
page in `PAGES`, 3 s apart. The program text is in `<main>`: an `h1`, paragraphs, and `h2` sections ("Eligible
Applicants", "Grant Amounts", ...); the read stops at "Resources" (forms and archived documents). The Local Government
Assistance Program and the Community Water Enrichment Fund each state their application period in a sentence. The CDBG
page names four programs in one paragraph each, so it is four records through `SPLITS`; its CDBG-CV half (a one-time
CARES Act allocation, closed) belongs to no record. The disaster recovery programs, the Recovery Housing Program, the
Water Sector Program and the EPA programs are not read (docs/connectors/louisiana.md). Status table and field mapping
are the agency-page table in `connectors/hand_list.py`.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.hand_list import (
    _FULL_DATE,
    APPLICATION_RE,
    AgencyPageConnector,
    Blocks,
    _date,
    all_sentences,
    applicant_tags,
    blocks_from,
    soup,
)
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "la_ocd"
BASE = "https://locd.la.gov"
AGENCY = "Louisiana Office of Community Development"
AGENCY_CODE = "LA-OCD"
CATEGORY_LABEL = "community development"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "lgap": "/local-government-assistance/local-government-assistance-program",
    "cwef": "/local-government-assistance/community-water-enrichment-fund",
    "cdbg": "/local-government-assistance/cdbg-and-cdbg-cv-programs",
}
# The CDBG page gives each program one paragraph that starts with its name; the CDBG-CV section is a tail.
SPLITS = {"cdbg": [
    ("cdbg", "Community Development Block Grant (CDBG): Public Facilities Program", re.compile(r"^Public Facilities Program\b")),
    ("clearance", "Community Development Block Grant (CDBG): Clearance Program", re.compile(r"^Clearance Program\b")),
    ("economic-development", "Community Development Block Grant (CDBG): Economic Development Program",
     re.compile(r"^Economic Development Program\b")),
    ("make-a-difference", "Community Development Block Grant (CDBG): Make a Difference Program",
     re.compile(r"^Make a Difference Program\b")),
    ("cdbg-cv", None, re.compile(r"^CDBG-CV\b")),
]}
SPLIT_KINDS = {"cdbg": ("label", "p")}
# The CDBG page names no federal agency (LGAP's and CWEF's mention HUD only to define who is a non-entitlement community).
FUNDING_SOURCES = {"lgap": "direct", "cwef": "direct", "cdbg": "pass_through", "cdbg#clearance": "pass_through",
                   "cdbg#economic-development": "pass_through", "cdbg#make-a-difference": "pass_through"}
CATEGORY_LABELS = {"cwef": "drinking water"}
# "The LGAP application period is open from November 2, 2026, through February 26, 2027.": the shared window rule reads
# "date through date", not the comma this office puts after the year.
WINDOW_RE = re.compile(rf"({_FULL_DATE}),?\s*(?:-|\u2013|\u2014|to|through)\s*({_FULL_DATE})", re.I)
# The CDBG page says who applies once, above the programs ("LOCD partners with local governments to deliver projects"),
# and in the Make a Difference paragraph ("grants for non-entitlement local governments"); the Economic Development
# paragraph's "for-profit businesses" are who a project serves.
CDBG_APPLICANT_RE = re.compile(r"\bpartners with local governments\b|\bgrants for non-entitlement local governments\b", re.I)
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"@la\.gov|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}[-.]\d{3}[-.]\d{4}\b", re.I)
STOP_RE = re.compile(r"^(?:resources|archived resources)$", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and the blocks of `<main>` after it, up to "Resources"."""
    doc = soup(page_html)
    main = doc.find("main") or doc
    h1 = main.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    for tag in main.find_all(["nav", "header", "footer"]):
        tag.decompose()
    for li in main.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(main, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


class LaOcd(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "LA"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    SPLITS = SPLITS
    SPLIT_KINDS = SPLIT_KINDS
    FUNDING_SOURCES = FUNDING_SOURCES
    CATEGORY_LABELS = CATEGORY_LABELS

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def round_with_yearless(self, blocks: Blocks, today: date) -> dict[str, Any]:
        """The base's round; when it dates nothing, the office's own "open <date>, through <date>" sentence."""
        out = super().round_with_yearless(blocks, today)
        if out["closes_at"] is not None:
            return out
        for s in all_sentences(blocks):
            m = WINDOW_RE.search(s)
            start, end = (_date(m.group(1)), _date(m.group(2))) if m and APPLICATION_RE.search(s) else (None, None)
            if start and end:
                status = "unknown" if end < today else ("forecasted" if start > today else "open")
                return {"status": status, "opens_at": start, "closes_at": end, "closes_at_text": s}
        return out

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        if raw.source_id.split("#")[0] == "cdbg":
            lines = [s for s in all_sentences([tuple(b) for b in raw.payload["page"].get("blocks", [])])
                     if CDBG_APPLICANT_RE.search(s)]
            out["eligibility_text"] = "\n".join(lines) or None
            out["applicant_types"] = applicant_tags(lines)
        return out


SITE = LaOcd()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
