"""South Dakota Governor's Office of Economic Development connector: the state CDBG and the Local Infrastructure
Improvement Program (milestone 12.6i).

Source: https://sdgoed.com, WordPress (a Tailwind theme); one GET per page in `PAGES`. No other South Dakota agency runs
WordPress, so the reader is this module's own. The program's text is in `<main>`; the theme prints each tabbed section
twice (a tab strip and an accordion for phones), so a repeated line is read once. The CDBG page's CAPER notice (a comment
period, with dates) is dropped and the read stops at its "Planning Districts" tab (forms and manuals). Status table and
field mapping are the agency-page table in `connectors/hand_list.py`. Left out: the Community Based Child Care Grant (closed,
one-time), CDBG-DR, REDI and the bond and loan programs (businesses), BEAD (broadband providers).
See docs/connectors/south_dakota.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import AgencyPageConnector, Blocks, blocks_from, soup
from connectors.sam_assistance_listings import clean

CONNECTOR = "sd_goed"
BASE = "https://sdgoed.com"
AGENCY = "South Dakota Governor's Office of Economic Development"
AGENCY_CODE = "SD-GOED"
CATEGORY_LABEL = "community development"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "cdbg": "/program/community-development-block-grants/",
    "liip": "/program/local-infrastructure-improvement/",
}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"\bCAPER\b|\bpublic comment\b|\bno later than\b|@state\.sd\.us|\[email\s*protected\]"
                     r"|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b", re.I)
STOP_RE = re.compile(r"(?:planning districts|manual|reports)$", re.I)
# "Deadlines are April 1 and October 1.", "January 31 for consideration at the March board meeting": no year.
_MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
YEARLESS_RE = re.compile(rf"\b(?:deadlines?|due)\b[^.]*\b{_MONTH}\s+\d{{1,2}}\b|^{_MONTH}\s+\d{{1,2}}\s+for consideration\b", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and the blocks of `<main>`, each line once."""
    doc = soup(page_html)
    h1 = doc.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    main = doc.find("main")
    if main is None:
        return {"title": title, "blocks": []}
    for li in main.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(main, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    seen: set[tuple[str, str]] = set()
    unique: Blocks = [b for b in blocks if not (b in seen or seen.add(b))]
    return {"title": title, "blocks": unique}


class SdGoed(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "SD"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    YEARLESS_RE = YEARLESS_RE

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)


SITE = SdGoed()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
