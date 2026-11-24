"""Kansas Department of Commerce connector: the ten programs of the state CDBG (milestone 12.9).

Source: https://www.kansascommerce.gov, WordPress (the theme's CDBG template); one GET per page in `PAGES`, **ten seconds
apart** (the site's `Crawl-delay: 10`). No other Kansas agency is read, so the reader is this module's own. A detail page
is read in three parts of `section.body-content`: the hero's description, the `#deadline` strip (each cell one line: "MATCH:
25% of the CDBG grant request", the "Qualify" checklist as a label and its items) and the `#overview` section (its labelled
paragraphs, the status headline as a paragraph). The FAQs and "How to Apply" (a script-run community picker and a sign-up
form) are not read. The name is the hero's headline; the template's `h1` is "CDBG Interior Page". Status table and field
mapping are the agency-page table in `connectors/hand_list.py`. Left out:
Commerce's other grants (HEAL, SEED, Towns and the rest of the Grants Calendar), tax credits, RHID, STAR Bonds.
See docs/connectors/kansas.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.hand_list import AgencyPageConnector, Blocks, applicant_tags, blocks_from, clause_cut, soup
from connectors.maryland_drupal import sentences
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "ks_commerce"
BASE = "https://www.kansascommerce.gov"
AGENCY = "Kansas Department of Commerce"
AGENCY_CODE = "KS-COMMERCE"
CATEGORY_LABEL = "community development"

PAGES: dict[str, str] = {
    "large-grants": "/cdbg/large-grants/",
    "small-grants": "/cdbg/small-grants/",
    "water-sewer": "/cdbg/water-sewer/",
    "commercial-rehab": "/cdbg/commercial-rehab/",
    "blueprint-to-build": "/cdbg/blueprint-to-build/",
    "housing": "/cdbg/housing/",
    "youth-job-training": "/cdbg/youth-job-training/",
    "economic-development": "/cdbg/economic-development/",
    "regional-water": "/cdbg/regional-water/",
    "urgent-need": "/cdbg/urgent-need/",
}
CATEGORY_LABELS = {
    "water-sewer": "environment and water",
    "regional-water": "environment and water",
    "housing": "housing",
    "youth-job-training": "workforce development",
}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"@ks\.gov|\[email\s*protected\]|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b", re.I)
# "Only cities and counties (units of local government) can apply for CDBG grants." sits under this label on every page; the
# shared applicant sentence rule does not know "can apply", so the label's paragraphs are read whole here.
APPLICANTS_LABEL_RE = re.compile(r"^eligible applicants:?$", re.I)
STOP_RE = re.compile(r"additional resources$", re.I)      # Blueprint to Build's links to its FAQ and three designs
# The names the theme prints in capitals ("URGENT NEED FOR DISASTERS") are set in title case.
SMALL_WORDS = {"for", "of", "and", "to", "the", "in"}
# Two pages have no "Eligible Applicants" section; the CDBG hub, which links all ten, says who is awarded.
_HUB = ("2026-11-24", "Kansas Commerce CDBG page (www.kansascommerce.gov/cdbg/)",
        ["CDBG grants are awarded to local units of government in cities or counties in Kansas, excluding the federal "
         "entitlement areas: Kansas City, Lawrence, Leavenworth, Manhattan, Overland Park, Topeka, Wichita, and all of "
         "Johnson County."])
HAND_QUOTES = {"blueprint-to-build": _HUB, "youth-job-training": _HUB}
# "Unlike other CDBG grants, the Economic Development Grant Program operates as a loan that must be repaid."
# The hub's sentence ends ", excluding the federal entitlement areas: ..."; the exclusion is cut before tagging (the stored
# text keeps it), or the shared tagger drops the whole sentence as a negation.
EXCLUDING_RE = re.compile(r",\s*excluding\b.*$", re.I)
FUNDING_TYPES = {"economic-development": "loan"}


def program_name(headline: str) -> str:
    """The hero's headline with "CDBG" in front (a page's own name is "Housing" or "Economic Development")."""
    if headline.isupper():
        words = headline.lower().split()
        headline = " ".join(w if i and w in SMALL_WORDS else w.capitalize() for i, w in enumerate(words))
    return f"CDBG {headline}" if headline else ""


def strip_blocks(section: Any) -> Blocks:
    """The `#deadline` strip: one line per cell (title, colon, text), the checklist cell as a label and its items."""
    blocks: Blocks = []
    for cell in section.select(".im-cdbg-deadline-cell-item"):
        head = cell.select_one(".im-cdbg-deadline-title")
        title = clean(head.get_text(" ")) if head else ""
        items = cell.find_all("li")
        if items:
            for icon in cell.select(".im-cdbg-deadline-icon"):
                icon.decompose()
            blocks.append(("label", title))
            blocks += [("li", t) for t in (clean(li.get_text(" ")) for li in items) if t]
            continue
        rest = " ".join(t for t in (clean(p.get_text(" ")) for p in cell.find_all("p") if p is not head) if t)
        if title and rest and not DROP_RE.search(rest):
            blocks.append(("p", f"{title}: {rest}"))
    return blocks


def under_label(blocks: Blocks, label_re: re.Pattern[str]) -> list[str]:
    """The sentences of the first paragraph (and the items after it) under the first label that matches: a second
    paragraph under "Eligible Applicants" is about the buildings or the businesses a project may assist."""
    out: list[str] = []
    on = False
    for kind, text in blocks:
        if kind == "label":
            if on:
                break
            on = bool(label_re.search(text))
        elif on:
            if kind == "p" and out:
                break
            out += sentences(text)
    return out


def cut_after(root: Any, el: Any) -> None:
    """Remove `el` and everything after it inside `root` (two pages leave a tag open, so `#overview` swallows the FAQs)."""
    node = el
    while node is not None and node is not root:
        for later in node.find_next_siblings():
            later.decompose()
        node = node.parent
    el.decompose()


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the hero's headline) and the blocks of the hero description, the deadline strip and the overview."""
    doc = soup(page_html)
    body = doc.select_one("section.body-content") or doc
    head = body.select_one("p.im-cdbg-hero-headline")
    title = program_name(clean(head.get_text(" "))) if head else ""
    blocks: Blocks = []
    desc = body.select_one("p.im-cdbg-hero-desc")
    if desc and clean(desc.get_text(" ")):
        blocks.append(("p", clean(desc.get_text(" "))))
    strip = body.select_one("#deadline")
    if strip is not None:
        blocks += strip_blocks(strip)
    overview = body.select_one("#overview")
    if overview is not None:
        faqs = overview.select_one("#faqs, #apply")
        if faqs is not None:
            cut_after(overview, faqs)
        for h2 in overview.select("h2.im-cdbg-page-title"):
            h2.decompose()
        for sub in overview.select(".im-cdbg-overview-subtitle"):
            sub.name = "p" if sub.name == "h1" else "h3"      # the status headline is a sentence; the others are labels
        for li in overview.find_all("li"):
            if not li.find(["ul", "ol"]):
                for tag in li.find_all(INLINE):
                    tag.unwrap()
        blocks += blocks_from(overview, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE)
    return {"title": title, "blocks": blocks}


class KsCommerce(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "KS"
    CATEGORY_LABEL = CATEGORY_LABEL
    CATEGORY_LABELS = CATEGORY_LABELS
    PAGES = PAGES
    HAND_QUOTES = HAND_QUOTES
    FUNDING_TYPES = FUNDING_TYPES
    DELAY_S = 10.0

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        lines = under_label([tuple(b) for b in raw.payload["page"].get("blocks", [])], APPLICANTS_LABEL_RE)
        if lines:
            out["eligibility_text"] = "\n".join(lines)
            out["applicant_types"] = applicant_tags([clause_cut(line) for line in lines])
        elif out["eligibility_text"]:
            lines = out["eligibility_text"].split("\n")
            out["applicant_types"] = applicant_tags([EXCLUDING_RE.sub("", clause_cut(line)) for line in lines])
        return out


SITE = KsCommerce()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
