"""The Arkansas agency base: what every agency on the state's WordPress platform shares (milestone 12.6h).

Agriculture (`agriculture.arkansas.gov`), Public Safety (`dps.arkansas.gov`, ADEM's pages) and Parks, Heritage and
Tourism (`adpht.arkansas.gov`) run one state WordPress build: Elementor templates, Yoast, the same custom post types. A
page's own text sits in the theme's post-content widget (`.elementor-widget-theme-post-content`) or, on the Office of
Outdoor Recreation's pages, a Dynamic Content for Elementor widget (`.elementor-widget-dyncontel-content`); every part is
in the static HTML. The page's `h1` is the division's name (Agriculture) or missing (ADEM), so the title is the `<title>`
tag with its " - site name" cut. Status table, applicant reader and field mapping are the agency-page table in
`connectors/hand_list.py`. An agency module sets its constants, its host, its page dict and its category label.
See docs/connectors/arkansas.md.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import ELIGIBILITY_LABEL_RE, AgencyPageConnector, Blocks, blocks_from, sentences, soup
from connectors.sam_assistance_listings import clean

JURISDICTION = "AR"
BODY_SELECTOR = ".elementor-widget-theme-post-content, .elementor-widget-dyncontel-content"
LABEL_MAX_CHARS = 90
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]

# Contact lines (a phone, an e-mail, Cloudflare's "[email protected]" stand-in) and the video-transcript links.
DROP_RE = re.compile(r"\bPhone:|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|\[email\s*protected\]|@arkansas\.gov"
                     r"|^Click here to view the video"
                     r"|^\*", re.I)   # a footnote paragraph ("* While there is no maximum limit ...") repeats its list item
# Where a page's own text ends: the forms and resources lists, the grantee's project-management forms. Not "Contact
# Information": Agriculture's water funding page prints its "Application Status" after that heading (its contact lines
# are dropped one by one instead).
STOP_RE = re.compile(r"(?:forms and resources|resources|additional contacts|project management)$", re.I)
# "Office of Outdoor Recreation Grants Program - adpht.arkansas.gov": the site's name after the last " - ".
TITLE_SUFFIX_RE = re.compile(r"\s+[-–|]\s+[^-–|]*$")


def title_of(doc: Any) -> str:
    tag = doc.find("title")
    text = clean(tag.get_text(" ")) if tag else ""
    return TITLE_SUFFIX_RE.sub("", text) if text else ""


def eligibility_paragraphs(blocks: Blocks) -> Blocks:
    """Each sentence of a paragraph under an eligibility heading read as one of that heading's list items (the Nebraska
    DWEE rule): Agriculture's dam grant answers "Eligible Applicants" in a paragraph, not a list."""
    out: Blocks = []
    under = False
    for kind, text in blocks:
        if kind == "label":
            under = bool(ELIGIBILITY_LABEL_RE.search(text))
        if under and kind == "p":
            out += [("li", sentence) for sentence in sentences(text)]
        else:
            out.append((kind, text))
    return out


def parse_page(page_html: str, stop_re: re.Pattern[str] = STOP_RE, drop_re: re.Pattern[str] = DROP_RE) -> dict[str, Any]:
    """title (the `<title>` tag's) and the blocks of the page's content widgets, in page order."""
    doc = soup(page_html)
    blocks: Blocks = []
    for body in doc.select(BODY_SELECTOR):
        # "<li><strong>Eligible applicants:</strong> All municipalities ...</li>" (Outdoor Recreation): a list item's own
        # text would drop the bold label, so inline tags inside an item with no nested list are unwrapped first (the
        # Missouri reader's rule).
        for li in body.find_all("li"):
            if not li.find(["ul", "ol"]):
                for tag in li.find_all(INLINE):
                    tag.unwrap()
        blocks += blocks_from(body, ["h2", "h3", "h4", "h5", "h6", "p", "li"], stop_re=stop_re, drop_re=drop_re,
                              bold_max=LABEL_MAX_CHARS)
    # A line repeated by a second widget (Outdoor Recreation prints its "Opens: ... Due: ..." line twice) is read once.
    seen: set[tuple[str, str]] = set()
    unique = [b for b in blocks if not (b in seen or seen.add(b))]
    return {"title": title_of(doc), "blocks": eligibility_paragraphs(unique)}


class ArAgency(AgencyPageConnector):
    """An Arkansas agency on the state WordPress: set CONNECTOR, BASE, AGENCY, AGENCY_CODE, CATEGORY_LABEL and PAGES."""

    JURISDICTION = JURISDICTION
    APPLICANT_ITEM_MAX = 400      # a sentence of a paragraph under "Eligible Applicants" is read as an item
    # slug -> the program's name, where the page's title is not it
    NAMES: dict[str, str] = {}
    STOP_RE = STOP_RE
    DROP_RE = DROP_RE

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html, self.STOP_RE, self.DROP_RE)

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        records = super().records_for(slug, spec, pages, count)
        name = self.NAMES.get(slug)
        return [(sid, {**payload, "name": name}) if name and "name" not in payload else (sid, payload) for sid, payload in records]
