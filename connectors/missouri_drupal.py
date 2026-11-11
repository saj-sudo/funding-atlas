"""The Missouri agency base: what every mo.gov Drupal 10 agency page shares (milestone 12.6e).

DED, MoDOT and DNR run the state's `mogov` Drupal 10 theme: the title is the `h1`, the page's own text sits in
`.node__content` (Layout Builder: an `.alert` block, then tabbed `h2` sections), every part in the static HTML. This
module reads `.node__content` into `(kind, text)` blocks with the hand-list helpers, stopping at the sections a page
ends with (contacts, documents, past-award lists); the status table, the applicant reader and the field mapping are
the agency-page table in `connectors/hand_list.py`. An agency module sets its constants, its host, its page dict and
its category label. See docs/connectors/missouri.md.

DED's pages name each program twice, once under "Description" and again under "Do I Qualify?", so a plain `SPLITS`
(one section per heading) would cut a program's text in two and run each description into the next tab. `records_for`
splits each tab on its own and joins the pieces by program.
"""

from __future__ import annotations

import re
from typing import Any

from connectors.hand_list import AgencyPageConnector, Blocks, blocks_from, soup, split_sections
from connectors.sam_assistance_listings import clean

JURISDICTION = "MO"
BODY_SELECTOR = ".node__content"
LABEL_MAX_CHARS = 90

# Contact lines (a phone, an e-mail, a mailing address block) and the theme's share and print links.
DROP_RE = re.compile(r"\bPhone:|\bTTY\b|\bEmail:|\bE-mail\b|@(?:ded|dnr|modot|sema|dps)\.mo\.gov|\(\d{3}\)\s?\d{3}-\d{4}|^Copy Link$", re.I)
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
# Where a page's own text ends: the help and contact section, the document and resource lists, past awards.
STOP_RE = re.compile(r"(?:need help\??|documents|hud resources|resources|related links|past (?:awards|recipients)"
                     r"|.*\bawarded projects\b|.*\bgrant recipients\b"
                     # DNR: the lists of past awards, then the theme's footer blocks that sit inside the body element
                     r"|awards|after awards|popular links|navigation|contact information|in this section:?"
                     # State Parks: the lists of past administration guides, sample projects and funded grants / recipients
                     r"|past administration guides:?|sample projects:?|fy\d{4} funded grants:?|past grant recipients:?)$", re.I)
# The tab that repeats DED's program headings.
QUALIFY_RE = re.compile(r"^do i qualify\??$", re.I)


def parse_page(page_html: str, selector: str = BODY_SELECTOR) -> dict[str, Any]:
    """title and the body's blocks, contact lines dropped, cut at the first closing section."""
    doc = soup(page_html)
    body = doc.select_one(selector)
    # DED prints the department's name in one `h1` and the program's in the next; the last `h1` is the program.
    h1s = [clean(h.get_text(" ")) for h in doc.find_all("h1")]
    title = next((t for t in reversed(h1s) if t), "")
    if body is None:
        return {"title": title, "blocks": []}
    # A bold label inside a list item ("<li><strong>Eligible Entities</strong> - Cities ...</li>") would be lost if the
    # item's own text were read, so inline tags inside an item with no nested list are unwrapped first.
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    # h5 and h6 too: State Parks heads ORLP's applicant list "Eligible Applicants Include:" with an `h5` (12.6f)
    blocks = blocks_from(body, ["h2", "h3", "h4", "h5", "h6", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


def join_tabs(blocks: Blocks, splits: list, kinds: tuple[str, ...]) -> list[tuple[str, str, Blocks]]:
    """`split_sections` over a page whose programs are named in two tabs: each tab is cut on its own and a program's
    pieces are joined in tab order. The blocks above the first tab (the alert, the intro) follow every program once."""
    cut = next((i for i, (kind, text) in enumerate(blocks) if kind == "label" and QUALIFY_RE.search(text)), None)
    if cut is None:
        return split_sections(blocks, splits, kinds)
    first = split_sections(blocks[:cut], splits, kinds)
    second = split_sections(blocks[cut + 1 :], splits, kinds)
    names = {sub for sub, _, _ in first}
    out: list[tuple[str, str, Blocks]] = []
    for sub, name, part in first:
        rest = next((b for s, _, b in second if s == sub), [])
        # the program's description, then the tab's label and the program's own qualifying text
        out.append((sub, name, part + ([blocks[cut]] + rest if rest else [])))
    out += [(sub, name, [blocks[cut]] + part) for sub, name, part in second if sub not in names]
    return out


class MoAgency(AgencyPageConnector):
    """A Missouri agency: set CONNECTOR, BASE, AGENCY, AGENCY_CODE, CATEGORY_LABEL and PAGES (slug -> path)."""

    JURISDICTION = JURISDICTION
    APPLICANT_ITEM_MAX = 400      # DNR's "Who Can Apply" items are whole sentences: "Municipalities, counties, public sewer or water districts, ..."
    # slug -> True for a page that names its programs in two tabs (DED); see `join_tabs`.
    TABBED: dict[str, bool] = {}
    # slug -> the program's name, for a page whose `h1` is not it
    NAMES: dict[str, str] = {}

    BODY_SELECTOR = BODY_SELECTOR   # SEMA's older pages keep the program in `#main-content`

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html, self.BODY_SELECTOR)

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        records = self._records(slug, spec, pages, count)
        name = self.NAMES.get(slug)
        # a page whose last `h1` is not the program's name (MoDOT's Partnership Development prints its application form's)
        return [(sid, {**payload, "name": name}) if name and "name" not in payload else (sid, payload) for sid, payload in records]

    def _records(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        splits = self.SPLITS.get(slug)
        if not (splits and self.TABBED.get(slug)):
            return super().records_for(slug, spec, pages, count)
        page = pages[0]
        blocks = [tuple(b) for b in page.get("blocks", [])]
        sections = join_tabs(blocks, splits, self.SPLIT_KINDS.get(slug, ("label",)))
        if not sections:
            return [(slug, {"path": spec, "page": page})]
        first = splits[0][0]
        return [(slug if sub == first else f"{slug}#{sub}",
                 {"path": spec, "name": name, "page": {"title": page.get("title", ""), "blocks": part}})
                for sub, name, part in sections]
