"""Florida Department of Environmental Protection connector: the recreation grants and water financing a local
government applies for (milestone 12.9).

Source: https://floridadep.gov, Drupal; one GET per page in `PAGES`, 3 s apart. The program's text is the `article`
inside `main#main-content` (the "Quick links" menu sits outside it). LWCF and RTP are read from their "Application
Process, Submission Cycles, and Funded Projects" pages, where the applicants, the match and the cycle are, and take their
names from `NAMES`. Body cells and bare `div`s are read as paragraphs (the cycle is printed in a table). The State
Revolving Fund page holds two programs, one record each; its "Eligibility" and "How to Apply" sections are about both
and are read with each. Status table and field mapping are the agency-page table in `connectors/hand_list.py`, plus
rules of this module's own, all read under the page's own words: a window under a "Submission Cycle" heading
("November 15 - December 15, 2025"), a cycle the page calls closed ("Closed on October 15, 2026", "(Closed)") is
`closed`, a request "submitted any time during the year" is `open` and rolling. See docs/connectors/florida.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from bs4 import Tag

from connectors.hand_list import (
    AGENCY_DATE_RE,
    BLOCK_TAGS,
    AgencyPageConnector,
    Blocks,
    _date,
    all_sentences,
    applicant_tags,
    blocks_from,
    clause_cut,
    soup,
)
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "fl_dep"
BASE = "https://floridadep.gov"
AGENCY = "Florida Department of Environmental Protection"
AGENCY_CODE = "FL-DEP"
CATEGORY_LABEL = "parks and recreation"
LABEL_MAX_CHARS = 90
_GRANTS = "/lands/land-and-recreation-grants/content"

PAGES: dict[str, str] = {
    "frdap": _GRANTS + "/florida-recreation-development-assistance-program",
    "lwcf": _GRANTS + "/lwcf-application-process-submission-cycles-and-funded",
    "rtp": _GRANTS + "/rtp-application-process-submission-cycles-and-funded-0",
    "fct-parks": _GRANTS + "/parks-and-open-space-florida-forever-grant-program",
    "srf": "/wra/srf",
    "water-quality": "/wra/wra/content/wastewater-grant-program",
}
# The two cycle pages are titled "LWCF: Application Process, ..."; the name is the program page's own title.
NAMES = {"lwcf": "Land and Water Conservation Fund Program", "rtp": "Recreational Trails Program"}
SPLITS = {"srf": [
    ("srf", "Clean Water State Revolving Fund", re.compile(r"^Clean Water State Revolving Fund$", re.I)),
    ("drinking-water", "Drinking Water State Revolving Fund", re.compile(r"^Drinking Water State Revolving Fund$", re.I)),
    # the office that writes the loan agreements: no program
    ("management", None, re.compile(r"^State Revolving Fund Management$", re.I)),
]}
# Sections of a several-program page that are about every program on it: moved above the first program's heading, where
# `split_sections` shares them.
SHARED_RE = re.compile(r"^(?:eligibility|how to apply)$", re.I)
FUNDING_TYPES = {"srf": "loan", "srf#drinking-water": "loan"}
# SRF: "funded through money received from federal grants as well as state contributions"; LWCF: "Grant awards are
# contingent upon appropriation by the federal government" (NPS is named only by its initials).
FUNDING_SOURCES = {"srf": "pass_through", "srf#drinking-water": "pass_through", "lwcf": "pass_through"}
CATEGORY_LABELS = {"srf": "clean water", "srf#drinking-water": "drinking water", "water-quality": "water quality"}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"@floridadep\.gov|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|^open dashboard\b|^image$"
                     r"|^learn more about\b|\bforms and documents$|\bother resources$|^contact us\b|\bdashboard\b", re.I)
STOP_RE = re.compile(r"(?:.*\b(?:webinar materials|application materials|priority lists?|funded projects)|more information"
                     r"|contact us|contacts?)$", re.I)
SUMMARY_MIN_CHARS = 60
_MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
# The heading a cycle is printed under: "FY2025-2026 Submission Cycle and Webinar", "Application Cycle and Portal Access".
CYCLE_LABEL_RE = re.compile(r"\b(?:submission|application) cycle\b", re.I)
# "November 15 - December 15, 2025" (the year once), "April 13, 2026-May 28, 2026"
WINDOW_RE = re.compile(rf"({_MONTH}\s+\d{{1,2}})(?:,?\s+(\d{{4}}))?\s*(?:-|\u2013|\u2014|to|through)\s*({_MONTH}\s+\d{{1,2}},?\s+(\d{{4}}))")
# "The 2027-2028 FRDAP Application Cycle Closed Oct. 15, 2026", "Closed on October 15, 2026": the page's own word.
CLOSED_ON_RE = re.compile(r"\bclosed\s+(?:on\s+)?(?=[a-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})", re.I)
CLOSED_CYCLE_RE = re.compile(r"\bcycle\s*\(\s*closed\s*\)", re.I)
# "a Request for Inclusion form, which can be submitted any time during the year"
ANY_TIME_RE = re.compile(r"\bsubmitted\s+(?:at\s+)?any\s?time\s+(?:during|throughout)\s+the\s+year\b", re.I)
# Who applies, in this agency's words: "provides low-interest loans to local governments and private utilities", "local
# governments (city and county) and special districts are eligible loan sponsors",
# "All local governments ... may submit FRDAP applications", "A local government entity is a county government, ...",
# "provides funding to Florida's governmental entities (cities, counties, municipalities, etc.)".
APPLICANT_RE = re.compile(r"\bloans?\s+to\s+(?:[\w-]+\s+){0,2}(?:local governments?|municipalit\w+|cities|counties)\b"
                          r"|\bare eligible loan sponsors\b|\blocal governments?\b[^.]*\bmay submit\b"
                          r"|^a local government entity is\b|\bfunding to\b[^.]*\bgovernmental entities\b", re.I)
# What the money is for is not who applies, and its "not attaining ... standards" would drop the line: cut before tagging.
TO_DO_RE = re.compile(r"\s+to (?:address|plan)\b.*$", re.I)
# "provided on a 50:50 (Program: Grantee) matching basis"
MATCH_BASIS_RE = re.compile(r"\bmatching basis\b", re.I)


def shared_first(blocks: Blocks) -> Blocks:
    """The blocks with every `SHARED_RE` section (its heading to the next heading) moved to the front."""
    shared: Blocks = []
    rest: Blocks = []
    on = False
    for kind, text in blocks:
        if kind == "label":
            on = bool(SHARED_RE.match(text))
        (shared if on else rest).append((kind, text))
    return shared + rest


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and the article's blocks; a body cell or a `div` with no block inside it is a paragraph."""
    doc = soup(page_html)
    h1 = doc.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    body = (doc.find("main") or doc).find("article")
    if body is None:
        return {"title": title, "blocks": []}
    for head in body.find_all("thead"):
        head.decompose()
    for el in body.find_all(["div", "td", "th"]):
        if el.find_parent("li") is None and not any(isinstance(c, Tag) and c.name in BLOCK_TAGS for c in el.descendants):
            el.name = "p"
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    # a heading that repeats the title says nothing
    blocks = [(k, t) for k, t in blocks if not (k == "label" and t == title)]
    # only a page this module splits has sections shared by its programs
    if any(k == "label" and pattern and pattern.search(t) for k, t in blocks for sp in SPLITS.values() for _, _, pattern in sp):
        blocks = shared_first(blocks)
    return {"title": title, "blocks": blocks}


def cycle_window(blocks: Blocks) -> tuple[str, date | None, date | None] | None:
    """(text, opens, closes) for the first date range under a cycle heading; a cycle stated as "TBD" is the heading and
    that word, no dates."""
    on = False
    head = ""
    for kind, text in blocks:
        if kind == "label":
            on, head = bool(CYCLE_LABEL_RE.search(text)), text
        if on and text == "TBD":
            return f"{head}: TBD", None, None
        m = WINDOW_RE.search(text) if on else None
        if m:
            closes = _date(m.group(3))
            opens = _date(f"{m.group(1)}, {m.group(2) or m.group(4)}")
            if opens and closes and opens > closes and not m.group(2):
                opens = opens.replace(year=opens.year - 1)   # "November 15 - January 15, 2026"
            if opens and closes:
                return text, opens, closes
    return None


class FlDep(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "FL"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    SPLITS = SPLITS
    FUNDING_TYPES = FUNDING_TYPES
    FUNDING_SOURCES = FUNDING_SOURCES
    CATEGORY_LABELS = CATEGORY_LABELS

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        out = super().records_for(slug, spec, pages, count)
        return [(sid, {**payload, "name": NAMES[sid]} if sid in NAMES else payload) for sid, payload in out]

    def round_with_yearless(self, blocks: Blocks, today: date) -> dict[str, Any]:
        out = super().round_with_yearless(blocks, today)
        sents = all_sentences(blocks)
        window = cycle_window(blocks)
        if window and not out["closes_at"] and window[2] is None:
            out = {**out, "closes_at_text": out["closes_at_text"] or window[0]}
        elif window and not out["closes_at"]:
            text, opens, closes = window
            status = "forecasted" if today < opens else "open" if today <= closes else "unknown"
            out = {"status": status, "opens_at": opens, "closes_at": closes, "closes_at_text": text}
        if out["status"] != "unknown":
            return out
        # the page's own word that the cycle is over: with its date, or beside the window already read
        for s in (t for _, t in blocks):
            m = CLOSED_ON_RE.search(s)
            d = m and next((x for x in (_date(g.group(0)) for g in AGENCY_DATE_RE.finditer(s, m.end())) if x), None)
            if d and d <= today:
                return {"status": "closed", "opens_at": out["opens_at"], "closes_at": d, "closes_at_text": s}
        closed = next((s for s in sents if CLOSED_CYCLE_RE.search(s)), None)
        if closed and out["closes_at"] and out["closes_at"] < today:
            return {**out, "status": "closed", "closes_at_text": f"{closed}: {out['closes_at_text']}"}
        rolling = next((s for s in sents if ANY_TIME_RE.search(s)), None)
        if rolling and not out["closes_at"]:
            return {"status": "open", "opens_at": None, "closes_at": None, "closes_at_text": rolling}
        return out

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        blocks = [tuple(b) for b in raw.payload["page"].get("blocks", [])]
        sents = all_sentences(blocks)
        if out["status"] == "open" and out["closes_at"] is None and ANY_TIME_RE.search(out["closes_at_text"] or ""):
            out["rolling"] = True
        if out["match_required"] is None and any(MATCH_BASIS_RE.search(s) for s in sents):
            out["match_required"] = True
        if len(out["summary"] or "") < SUMMARY_MIN_CHARS:
            out["summary"] = next((t for k, t in blocks if k == "p" and len(t) >= SUMMARY_MIN_CHARS), out["summary"])
        have = out["eligibility_text"].split("\n") if out["eligibility_text"] else []
        lines = have + [s for s in sents if APPLICANT_RE.search(s) and s not in have]
        out["eligibility_text"] = "\n".join(lines) or None
        tags = applicant_tags([TO_DO_RE.sub("", clause_cut(line)) for line in lines])
        out["applicant_types"] = list({t.value: t for t in reversed(tags)}.values())[::-1]   # one tag per type, first kept
        return out


SITE = FlDep()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
