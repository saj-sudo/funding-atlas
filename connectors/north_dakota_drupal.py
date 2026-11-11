"""The North Dakota agency base: what every nd.gov Drupal 11 agency page shares (milestone 12.6c part 2).

Commerce, NDDOT, DES and Parks and Recreation all run the state's `ndit_base` theme on Layout Builder: the title is
the `h1`, the page's own text sits in `.node__content` as WYSIWYG, accordion and tab blocks, every one of them in the
static HTML. `main` is not the container: DES puts its side menu inside it. This module reads `.node__content` into
`(kind, text)` blocks with the hand-list helpers, stopping at the past-award lists several pages end with; the status
table, the applicant reader and the field mapping are the agency-page table in `connectors/hand_list.py`. An agency
module sets its constants, its host, its page dict and its category label. See docs/connectors/north_dakota.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean

JURISDICTION = "ND"
BODY_SELECTOR = ".node__content"
LABEL_MAX_CHARS = 90

# Contact lines (a phone, a TTY, an e-mail, DES's "T: 701.328.8100" address blocks) and the theme's "Copy Link".
DROP_RE = re.compile(r"\bPhone:|\bTTY\b|\bEmail:|\bE-mail\b|@nd\.gov|\bT: \d{3}\.\d{3}|^Copy Link$", re.I)
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
# The lists of past awards several pages end with name towns as recipients, not as applicants; the read stops there.
STOP_RE = re.compile(r"(?:prior year projects|.*\bawarded projects\b|.*\bgrant recipients\b|past recipients|resources|related links)\b", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title and the body's blocks, contact lines dropped, cut at the first past-awards heading."""
    doc = soup(page_html)
    body = doc.select_one(BODY_SELECTOR)
    title = clean(doc.h1.get_text(" ")) if doc.h1 else ""
    if body is None:
        return {"title": title, "blocks": []}
    # Commerce writes "<li><strong>Eligible Entities</strong> – City, County, ...</li>": a list item's own text would
    # lose the bold label, so inline tags inside an item with no nested list are unwrapped before reading.
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    # Parks heads its applicant list with a plain paragraph, "The following entities are eligible to apply:"; a short
    # paragraph ending in a colon is the page's label for the list after it.
    blocks = [("label" if k == "p" and t.endswith(":") and len(t) <= LABEL_MAX_CHARS else k, t) for k, t in blocks]
    return {"title": title, "blocks": blocks}


class NdAgency(AgencyPageConnector):
    """A North Dakota agency: set CONNECTOR, BASE, AGENCY, AGENCY_CODE, CATEGORY_LABEL and PAGES (slug -> path)."""

    JURISDICTION = JURISDICTION

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)
