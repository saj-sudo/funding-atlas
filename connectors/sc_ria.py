"""South Carolina Rural Infrastructure Authority connector: the four state grant programs, the State Revolving Fund
loans and the Viability Improvement Program (milestone 12.9).

Source: https://ria.sc.gov, WordPress (a Foundation theme); one GET per page, 3 s apart; `/robots.txt` answers 404. The
reader is this module's own. The grants page names its four programs in titled boxes (`div.titleCell`, read as headings),
one record each; what the boxes do not say (the year's deadlines, who may apply, the match) is on the "Apply For a State
Grant" page, read with it and shared by the four, except that a line headed by another program's name stays off a record
and the Emergencies record ("may be submitted at any time") does not take the deadlines. Status table and field mapping
are the agency-page table in `connectors/hand_list.py`, with one status rule of this module's own: "may be submitted at any
time" is open and rolling. Left out: SCIIP (one-time, closed, all awarded), project management, the viability toolkit.
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

CONNECTOR = "sc_ria"
BASE = "https://ria.sc.gov"
AGENCY = "South Carolina Rural Infrastructure Authority"
AGENCY_CODE = "SC-RIA"
CATEGORY_LABEL = "drinking water"
LABEL_MAX_CHARS = 90

# slug -> path, or (the page, its how-to-apply page)
PAGES: dict[str, Any] = {
    "grants": ("/grants/", "/grants/how-to-apply/"),
    "loans": "/loans/",
    "vip": "/utility-viability/vip/",
}
SPLITS = {"grants": [
    ("grants", "RIA State Grants: Basic Infrastructure", re.compile(r"^basic infrastructure$", re.I)),
    ("economic-infrastructure", "RIA State Grants: Economic Infrastructure/Jobs", re.compile(r"^economic infrastructure", re.I)),
    ("emergencies", "RIA State Grants: Emergencies", re.compile(r"^emergencies$", re.I)),
    ("regional-planning", "RIA State Grants: Regional Planning", re.compile(r"^regional planning$", re.I)),
]}
# The how-to-apply page heads a program's own line with its name ("Regional Planning Grant : No match required."): which
# records keep a line that starts so.
OWN_LINES = [
    (re.compile(r"^basic\s*(?:&|and)\s*economic infrastructure grants?\s*:", re.I), {"grants", "grants#economic-infrastructure"}),
    (re.compile(r"^regional planning grants?\s*:", re.I), {"grants#regional-planning"}),
]
# The page's `h2` is "Loans"; the name is its first sentence's ("The State Revolving Funds (SRF) are ... loan programs").
NAMES = {"loans": "State Revolving Fund (SRF) Loans"}
FUNDING_TYPES = {"loans": "loan"}
# "The State Revolving Funds (SRF) are federally capitalized loan programs"; the state grants are state funds.
FUNDING_SOURCES = {"loans": "pass_through"}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|@ria\.sc\.gov|\[email\s*protected\]", re.I)
STOP_RE = re.compile(r"^(?:program strategy|application process|interest rates|program description|featured case study)$", re.I)
# "The application deadlines for RIA grants in FY27 are:" and, in the next paragraph, the dates.
DEADLINES_RE = re.compile(r"^[^.:]*\bdeadlines\b[^.:]*:", re.I)
# Who may apply, in two sentence forms the shared reader does not know: "Low-interest loans are made available to
# municipalities, counties and special purpose districts" (SRF) and "Eligible candidates for assistance will be local
# governments, ..." with "Non-profit water and sewer companies are not eligible for this pilot program." (VIP).
APPLICANT_RE = re.compile(r"\bloans are made available to\b|^eligible candidates for assistance\b|\bnot eligible for this pilot program\b", re.I)
# "Federal requirements such as ... disadvantaged businesses ... may apply to SRF funded projects": rules that apply, not
# applicants.
NOT_APPLICANT_RE = re.compile(r"^federal requirements\b|^eligible applicants$", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the first `h2`) and the body's blocks, each program box's title a heading, the deadline paragraph joined
    to the dates under it."""
    doc = soup(page_html)
    body = doc.find("body") or doc
    for tag in body.select("header, footer, nav"):
        tag.decompose()
    for box in body.select("div.titleCell"):
        box.name = "h3"
    h2 = body.find("h2")
    title = clean(h2.get_text(" ")) if h2 else ""
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks: Blocks = []
    for kind, text in blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS):
        if blocks and blocks[-1][0] == "p" and kind == "p" and blocks[-1][1].endswith(":") and DEADLINES_RE.match(blocks[-1][1]):
            blocks[-1] = ("p", clean(f"{blocks[-1][1]} {text}").replace(" .", "."))
        else:
            blocks.append((kind, text))
    return {"title": title, "blocks": blocks}


class ScRia(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "SC"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    SPLITS = SPLITS
    FUNDING_TYPES = FUNDING_TYPES
    FUNDING_SOURCES = FUNDING_SOURCES

    def urls_for(self, slug: str, spec: Any) -> list[str]:
        return [self.BASE + path for path in ([spec] if isinstance(spec, str) else spec)]

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: Any, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        path = spec if isinstance(spec, str) else spec[0]
        if slug != "grants":
            payload: dict[str, Any] = {"path": path, "page": pages[0]}
            if slug in NAMES:
                payload["name"] = NAMES[slug]
            return [(slug, payload)]
        # The how-to-apply page first, so that it sits above the first box and is shared by every program.
        apply = [tuple(b) for b in pages[1].get("blocks", [])] if len(pages) > 1 else []
        merged = {"title": pages[0].get("title", ""), "blocks": apply + [tuple(b) for b in pages[0].get("blocks", [])]}
        out = []
        for sid, payload in super().records_for(slug, path, [merged], count):
            rolling = any(hl.ROLLING_OPEN_RE.search(t) for _, t in payload["page"]["blocks"][:2])
            payload["page"]["blocks"] = [
                (kind, text) for kind, text in payload["page"]["blocks"]
                if not any(own.search(text) and sid not in sids for own, sids in OWN_LINES)
                and not (rolling and DEADLINES_RE.match(text))]
            out.append((sid, payload))
        return out

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        sents = hl.all_sentences([tuple(b) for b in raw.payload["page"].get("blocks", [])])
        lines = [line for line in (out["eligibility_text"] or "").split("\n") if line and not NOT_APPLICANT_RE.search(line)]
        lines += [s for s in sents if APPLICANT_RE.search(s) and s not in lines]
        out["eligibility_text"] = "\n".join(lines) or None
        out["applicant_types"] = hl.applicant_tags([hl.clause_cut(line) for line in lines])
        return out


SITE = ScRia()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
