"""South Carolina Department of Commerce connector: the State CDBG categories, ARC, SCRC and the Rural Development
Initiative (milestone 12.9).

Source: https://www.sccommerce.com, Drupal (Layout Builder); one GET per page, 3 s apart. The reader is this module's own
(the only South Carolina agency on Drupal that is read). The program's text is in `<main>`; the title is the `h1`'s
`<strong>` (the rest of the `h1` is a tagline). The CDBG program page names no funding category: the "How to apply" page
does, each under its round, so CDBG is read from both pages and is one record per category, the program page's text
followed by the category's round. The ARC page holds two programs under two `h2`s. Status table and field mapping are the
agency-page table in `connectors/hand_list.py`, with three status rules of this module's own (rolling wording is open and
rolling; "no open ... funding opportunity at this time" is closed; "deadlines vary by funding cycle" is kept as text).
Left out: export incentives, the Relentless Challenge and Fraunhofer grants, every tax incentive, CDBG-DR (another agency).
See docs/connectors/south_carolina.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors import hand_list as hl
from connectors.hand_list import AgencyPageConnector, Blocks, blocks_from, soup
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "sc_commerce"
BASE = "https://www.sccommerce.com"
AGENCY = "South Carolina Department of Commerce"
AGENCY_CODE = "SC-COMMERCE"
CATEGORY_LABEL = "community development"
LABEL_MAX_CHARS = 90
_G = "/incentives-grants/grants"

# slug -> path, or (program page, how-to-apply page) for CDBG
PAGES: dict[str, Any] = {
    "cdbg": (f"{_G}/community-development-block-grant-cdbg", f"{_G}/community-development-block-grant/how-apply"),
    "arc": f"{_G}/appalachian-regional-commission-arc",
    "scrc": f"{_G}/southeast-crescent-regional-commission-scrc",
    "rdi": f"{_G}/rural-development-initiative-rdi",
}
# The funding categories the how-to-apply page names, in its order: (sub_slug, the name as the page prints it). The first
# keeps the page's `source_id`.
CDBG_CATEGORIES = [
    ("cdbg", "Community Infrastructure"),
    ("community-enrichment", "Community Enrichment"),
    ("local-priorities", "Local Priorities"),
    ("business-development", "Business Development"),
    ("ready-to-go", "Ready to Go"),
]
# The how-to-apply page's round sections: each `h3` under "2026 funding deadlines".
ROUND_HEADING_RE = re.compile(r"\bfunding round$|^rolling applications$", re.I)
SPLITS = {"arc": [
    ("arc", "Appalachian Regional Commission (ARC): Area Development Program", re.compile(r"\barea development program\b", re.I)),
    ("local-access-road", "Appalachian Regional Commission (ARC): Local Access Road Program (LAR)",
     re.compile(r"\blocal access road program\b", re.I)),
]}
# ARC ("an economic development agency of the federal government and 13 state governments") and SCRC ("a federal-state
# partnership") are federal commissions the shared rule has no name for.
FUNDING_SOURCES = {"arc": "pass_through", "scrc": "pass_through"}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|@sccommerce\.com|\[email\s*protected\]", re.I)
STOP_RE = re.compile(r"^(?:national objectives|why is an application request required\??|partner programs.*"
                     r"|.*documents (?:&|and) resources|questions about .*|do you have questions.*|need help.*"
                     r"|looking for additional.*|find incentives.*)$", re.I)
# "Application requests ... may be submitted at any time", "LAR applications may be submitted anytime throughout the year",
# "Applications can be submitted to the State Program Manager at any time throughout the year".
# "There is no open SCRC funding opportunity at this time."
NONE_OPEN_RE = re.compile(r"\bno open\b[^.]*\bfunding opportunity\b", re.I)
# "Application timelines and deadlines vary by funding cycle." (ARC Area Development): no date, kept as the round's text.
YEARLESS_RE = re.compile(r"\bdeadlines vary by funding cycle\b", re.I)
# "Applicants are limited to governmental entities" (ARC's road program)
LIMITED_TO_RE = re.compile(r"^applicants are limited to\b", re.I)
# "... governments in counties with fewer than 20,000 residents" (RDI): a population threshold, not residents who apply. Cut
# before tagging; the stored text keeps it.
POPULATION_RE = re.compile(r"\bwith fewer than [\d,]+ residents\b", re.I)
# "5 p.m. Oct. 30, 2026": the shared sentence splitter breaks after "p.m." before a capital, parting the deadline word from
# its date. Folded to "5 pm" (the site's own other spelling: "by 5 pm").
MERIDIEM_RE = re.compile(r"\b([ap])\.m\.(?=\s+[A-Z])", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`'s `<strong>`, else the `h1`) and the blocks of `<main>` up to the first closing heading."""
    doc = soup(page_html)
    main = doc.find("main")
    if main is None:
        return {"title": "", "blocks": []}
    h1 = main.find("h1")
    strong = h1.find("strong") if h1 else None
    title = clean((strong or h1).get_text(" ")) if h1 else ""
    for nav in main.find_all("nav"):   # the breadcrumb
        nav.decompose()
    for li in main.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(main, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    # "Eligible applicants include:" over a list is the list's label
    blocks = [("label" if kind == "p" and text.endswith(":") and len(text) <= LABEL_MAX_CHARS
               and hl.ELIGIBILITY_LABEL_RE.search(text) else kind, MERIDIEM_RE.sub(r"\1m", text)) for kind, text in blocks]
    return {"title": title, "blocks": blocks}


def round_sections(blocks: Blocks) -> list[Blocks]:
    """The how-to-apply page's round sections: from a round `h3` to the next round `h3` (the category under it is a bold
    line, a label too) or to where the read stops."""
    out: list[Blocks] = []
    for kind, text in blocks:
        if kind == "label" and ROUND_HEADING_RE.search(text):
            out.append([])
        if out:
            out[-1].append((kind, text))
    return out


class ScCommerce(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "SC"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    SPLITS = SPLITS
    FUNDING_SOURCES = FUNDING_SOURCES
    YEARLESS_RE = YEARLESS_RE

    def urls_for(self, slug: str, spec: Any) -> list[str]:
        return [self.BASE + path for path in ([spec] if isinstance(spec, str) else spec)]

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: Any, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        if slug != "cdbg":
            return super().records_for(slug, spec, pages, count)
        program, apply = pages[0], (pages[1] if len(pages) > 1 else {"blocks": []})
        rounds = round_sections([tuple(b) for b in apply.get("blocks", [])])
        out = []
        for sub, category in CDBG_CATEGORIES:
            # the round whose own lines name the category
            own = next((r for r in rounds if any(category.lower() in text.lower() for _, text in r[1:])), [])
            page = {"title": program.get("title", ""), "blocks": [tuple(b) for b in program.get("blocks", [])] + own}
            out.append((slug if sub == slug else f"{slug}#{sub}",
                        {"path": spec[0], "name": f"{program.get('title', '')}: {category}", "page": page}))
        return out

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        blocks = [tuple(b) for b in raw.payload["page"].get("blocks", [])]
        sents = hl.all_sentences(blocks)
        lines = [line for line in (out["eligibility_text"] or "").split("\n") if line]
        lines += [s for s in sents if LIMITED_TO_RE.search(s) and s not in lines]
        out["eligibility_text"] = "\n".join(lines) or None
        out["applicant_types"] = hl.applicant_tags([POPULATION_RE.sub("", hl.clause_cut(line)) for line in lines])
        # "no open ... funding opportunity" outranks the base's rolling reading, as it did when both were local
        if (out["status"] == "unknown" or out.get("rolling")) and out["closes_at"] is None:
            none_open = next((s for s in sents if NONE_OPEN_RE.search(s)), None)
            if none_open:
                out.update(status="closed", closes_at_text=none_open, rolling=None)
        return out


SITE = ScCommerce()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
