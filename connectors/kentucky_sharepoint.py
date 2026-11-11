"""The Kentucky agency base: what every ky.gov SharePoint publishing page shares (milestone 12.6d).

The Department for Local Government, the Transportation Cabinet, the Energy and Environment Cabinet and the
Infrastructure Authority all run classic SharePoint publishing: the title is the page's `h1`, and the text sits in one
or more rich-text fields, `div.ms-rtestate-field` (the main one's id ends `__ControlWrapper_RichHtmlField`; the
Transportation Cabinet's pages put theirs in Content Editor web parts, so the class, not the id, is the selector). The
image field is empty; later fields hold a staff list or a "Downloads" label. This module reads every outermost field
into `(kind, text)` blocks with the hand-list helpers; the status table, the applicant reader and the field mapping are
the agency-page table in `connectors/hand_list.py`. An agency module sets its constants, its host, its page dict and its
category label. See docs/connectors/kentucky.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.maryland_drupal import sentences
from connectors.sam_assistance_listings import clean

JURISDICTION = "KY"
BODY_SELECTOR = "div.ms-rtestate-field"
LABEL_MAX_CHARS = 90

# Contact sentences (a phone, an e-mail) name a person. A sentence, not the block: RTP's "It is due on Friday, October
# 30th, 2026. If you have any questions, please contact ...@ky.gov" is one paragraph.
DROP_RE = re.compile(r"\bPhone:|\bFax:|\bE-?mail:|@ky\.gov|\b\d{3}-\d{3}-\d{4}\b", re.I)
# The lists of past awards and links some pages end with name towns as recipients, not as applicants; the read of a
# field stops there.
STOP_RE = re.compile(r"(?:past funded projects|prior year projects|.*\bawarded projects\b|.*\bgrant recipients\b|past recipients|related links)\b", re.I)


BLOCK_CHILDREN = ["div", "p", "ul", "ol", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"]


def without_contacts(blocks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Each block with its contact sentences cut; a block that was only contact is dropped."""
    out = []
    for kind, text in blocks:
        kept = " ".join(s for s in sentences(text) if not DROP_RE.search(s))
        if kept:
            out.append((kind, kept))
    return out


def parse_page(page_html: str) -> dict[str, Any]:
    """title and the blocks of every outermost rich-text field, in page order, contact sentences dropped, each field cut
    at its first past-awards heading. A `div` with no block inside it is a line of text (the Energy and Environment
    Cabinet's "Funding Source: ..." lines) and is read as a paragraph."""
    doc = soup(page_html)
    title = clean(doc.h1.get_text(" ")) if doc.h1 else ""
    blocks: list[tuple[str, str]] = []
    for field in doc.select(BODY_SELECTOR):
        if field.find_parent("div", class_="ms-rtestate-field"):
            continue
        for div in field.find_all("div"):
            if not div.find(BLOCK_CHILDREN):
                div.name = "p"
        blocks += blocks_from(field, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": without_contacts(blocks)}


class KyAgency(AgencyPageConnector):
    """A Kentucky agency: set CONNECTOR, BASE, AGENCY, AGENCY_CODE, CATEGORY_LABEL and PAGES (slug -> path)."""

    JURISDICTION = JURISDICTION

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)
