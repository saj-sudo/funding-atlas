"""Tennessee ECD connector: four Community and Rural Development program pages (milestone 12.9).

Source: https://www.tn.gov, the state's one Adobe Experience Manager site, one GET per page in `PAGES`, 6 s apart. The
site's AWS load balancer refused this User-Agent after about sixty requests in fifteen minutes on 2026-11-17, and
answered every page from the GitHub Actions runner on 2026-11-24 (docs/connectors/tennessee.md); the pace here is
deliberate, and a refused request falls back to the stored record. The title is `.tn-pagetitle h1`; the program text
is the `.tn-rte` and `.textimage-text` blocks under `#main` (a tabbed page has one per tab; the left menu, the link-button tabs and the
image tiles hold no program text). A paragraph that lists dates one to a line (`<br>`) is read as one block per line,
so a deadline is not read off its neighbour's date. `parse_page` is shared with `tn_tdot`. Contact lines are dropped.
Site Development is left out (its page is three image tiles and no text), and the Historic Development Grant while its
page says no further round is funded. Status table and field mapping are the agency-page table in
`connectors/hand_list.py`.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean

CONNECTOR = "tn_ecd"
BASE = "https://www.tn.gov"
AGENCY = "Tennessee Department of Economic and Community Development"
AGENCY_CODE = "TN-ECD"
CATEGORY_LABEL = "community development"
DELAY_S = 6.0
LABEL_MAX_CHARS = 90
# The rich-text component, and the text half of a text-and-image component (TDOT's TAP page).
BODY_SELECTOR = ".tn-rte, .textimage-text"

PAGES: dict[str, str] = {
    "cdbg": "/ecd/community-development-block-grant/cdbg/cdbg-community-development-regular-round.html",
    "infrastructure-planning": "/ecd/rural-development/infrastructure-planning-grant.html",
    "downtown-improvement": "/ecd/rural-development/tennessee-main-street/downtown-improvement-grant-program.html",
    "threestar": "/ecd/rural-development/threestar.html",
    # Left out while its page says "This funding has been allocated ... The grant program will not have any additional
    # rounds of grants." (the Missouri funds-exhausted rule, 2026-11-11); one line to restore if a round is funded:
    # "historic-development": "/ecd/rural-development/historic-development-grant-program.html",
}
# The page titles are the programs' names but for CDBG's, which is the round's nickname.
NAMES = {"cdbg": "Community Development Block Grant (CDBG): Community Development Regular Round"}
# The regular-round page names no federal agency; the CDBG hub above it says HUD funds the program.
FUNDING_SOURCES = {"cdbg": "pass_through"}

INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
# Contacts: a named officer's line, an address, a telephone number, an e-mail address.
DROP_RE = re.compile(r"@tn\.gov|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-{1,2}\d{3}-\d{4}\b|^questions about\b", re.I)
# The read ends where a page turns to how an application is assembled and scored, or to its contacts.
STOP_RE = re.compile(r"^(?:downtown improvement program application process|contact information|materials (?:&|and) resources"
                     r"|related materials)\b", re.I)


BR_RE = re.compile(r"<br\s*/?>", re.I)


def split_breaks(rte: Tag) -> None:
    """Each `<br>`-separated line of a paragraph becomes its own paragraph ("August 28, 2026 - Application Due <br>
    October 20, 2026 - Grants Announced")."""
    for p in rte.find_all("p"):
        if p.find("br") is None or p.find(["ul", "ol", "p"]):
            continue
        parts = [part for part in BR_RE.split(p.decode_contents()) if part.strip()]
        if len(parts) < 2:
            continue
        fresh = BeautifulSoup("".join(f"<p>{part}</p>" for part in parts), "html.parser")
        p.replace_with(*list(fresh.contents))


def parse_page(page_html: str) -> dict[str, Any]:
    """title (`.tn-pagetitle h1`) and the blocks of every text component under `#main`, in page order, up to `STOP_RE`."""
    doc = soup(page_html)
    h1 = doc.select_one(".tn-pagetitle h1") or doc.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    main = doc.select_one("#main") or doc
    blocks: list[tuple[str, str]] = []
    for rte in main.select(BODY_SELECTOR):
        if rte.find_parent(class_="tn-leftnav") or rte.find_parent(class_="tn-linkbuttons"):
            continue
        split_breaks(rte)
        for li in rte.find_all("li"):
            if not li.find(["ul", "ol"]):
                for tag in li.find_all(INLINE):
                    tag.unwrap()
        got = blocks_from(rte, ["h2", "h3", "h4", "h5", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
        blocks.extend(got)
        if any(el.name.startswith("h") and STOP_RE.match(clean(el.get_text(" "))) for el in rte.find_all(["h2", "h3", "h4", "h5"])):
            break
    return {"title": title, "blocks": blocks}


class TnAgency(AgencyPageConnector):
    """A Tennessee agency on www.tn.gov: constants, `PAGES` and optional `NAMES` (slug -> the program's name)."""

    BASE = BASE
    JURISDICTION = "TN"
    DELAY_S = DELAY_S
    NAMES: dict[str, str] = {}

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        out = super().records_for(slug, spec, pages, count)
        name = self.NAMES.get(slug)
        return [(sid, {**payload, "name": payload.get("name") or name} if name else payload) for sid, payload in out]


class TnEcd(TnAgency):
    CONNECTOR = CONNECTOR
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    NAMES = NAMES
    FUNDING_SOURCES = FUNDING_SOURCES


SITE = TnEcd()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
