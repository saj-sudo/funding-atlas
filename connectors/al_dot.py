"""Alabama Department of Transportation connector: four local transportation programs (milestone 12.9).

Source: https://www.dot.state.al.us, static pages on IIS (no robots.txt: the address redirects to the not-found page); one
GET per page in `PAGES`, 3 s apart. A program page is the `div.container` that holds the `h1`: one or two paragraphs (the
first opens with a lead-in question in a `span`, removed), then the year's documents as a list of links, whose labels are
kept as lines because they are all some pages say. The read stops at "SELECTED PROJECTS"; staff contact lines and awarded
project lists are dropped. No page dates a round except Industrial Access, whose table of board meetings and application
deadlines is read into two lines (`deadline_lines`), so that the shared cycle rule finds the deadline still ahead. Status
table and field mapping are the agency-page table in `connectors/hand_list.py`; the two sentences that name an applicant in
ALDOT's own words are added here (`OWN_APPLICANT_RE`). ADECA (CDBG, LWCF, RTP) is not read: its robots.txt disallows
`ClaudeBot`. See docs/connectors/alabama.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from bs4 import BeautifulSoup, Tag

from connectors.hand_list import (
    PARTNER_LINE_RE,
    AgencyPageConnector,
    all_sentences,
    applicant_tags,
    blocks_from,
    clause_cut,
    soup,
)
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "al_dot"
BASE = "https://www.dot.state.al.us"
AGENCY = "Alabama Department of Transportation"
AGENCY_CODE = "AL-DOT"
CATEGORY_LABEL = "transportation"
LABEL_MAX_CHARS = 90

PAGES: dict[str, str] = {
    "tap": "/programs/TAP.html",
    "atrip-ii": "/programs/ATRIPII.html",
    "raa-annual-grant": "/programs/RAAGrantProgram.html",
    "industrial-access": "/programs/IndustrialAccessProgram.html",
}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
# staff names and telephone numbers; lists of past awards; the application's file formats
DROP_RE = re.compile(r"^For questions pertaining to\b|\b\d{3}[.-]\d{3}[.-]\d{4}\b|\(\d{3}\)\s?\d{3}-\d{4}|\bAwarded Projects$"
                     r"|^(?:Microsoft Word|Adobe PDF):", re.I)
STOP_RE = re.compile(r"^selected projects$", re.I)
# TAP: "This program is application based for cities, towns, county commissions and metropolitan planning organizations."
# Industrial Access: "The project sponsor (city or county) will assume maintenance responsibilities ..."
OWN_APPLICANT_RE = re.compile(r"\bapplication based for\b|\bproject sponsor \((?:city|county|town)\b", re.I)
# what the Industrial Access sponsor takes on is not who applies: cut before tagging, the stored text keeps it
SPONSOR_DUTY_RE = re.compile(r"\bwill assume\b.*", re.I)
DEADLINE_HEADER_RE = re.compile(r"application deadline", re.I)


def deadline_lines(table: Tag) -> list[str]:
    """The Industrial Access table (year, board meeting date, time, place, application deadline) as two lines: every
    application deadline, in the words the shared cycle rule reads ("deadlines are: ..."), and every meeting date."""
    rows = [[clean(td.get_text(" ")) for td in tr.find_all("td")] for tr in table.find_all("tr")]
    rows = [[c for c in r if not re.fullmatch(r"\d{4}", c)] for r in rows]   # the year cell spans three rows
    rows = [r for r in rows if len(r) >= 2]
    if not rows:
        return []
    return ["Application deadlines are: " + "; ".join(r[-1] for r in rows),
            "Board of Directors meetings: " + "; ".join(r[0] for r in rows)]


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and the blocks of the container that holds it, up to "SELECTED PROJECTS"."""
    doc = soup(page_html)
    h1 = doc.find("h1")
    if h1 is None or h1.parent is None:
        return {"title": "", "blocks": []}
    title = clean(h1.get_text(" "))
    body = h1.parent
    for br in body.find_all("br"):   # "<span>What is the ... program?</span><br>": the lead-in question
        lead = br.find_previous_sibling()
        if lead is not None and lead.name == "span" and clean(lead.get_text(" ")).endswith("?"):
            lead.decompose()
    for table in body.find_all("table"):
        head = clean(" ".join(th.get_text(" ") for th in table.find_all("th")))
        lines = deadline_lines(table) if DEADLINE_HEADER_RE.search(head) else []
        for line in reversed(lines):
            p = BeautifulSoup("", "html.parser").new_tag("p")
            p.string = line
            table.insert_after(p)
        table.decompose()
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


class AlDot(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "AL"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        """The agency-page table, plus the sentences in which ALDOT names the applicant in words the shared reader has no
        rule for."""
        out = super().fields(raw, today)
        lines = out["eligibility_text"].split("\n") if out["eligibility_text"] else []
        blocks = [tuple(b) for b in raw.payload["page"].get("blocks", [])]
        lines += [s for s in all_sentences(blocks) if OWN_APPLICANT_RE.search(s) and s not in lines]
        out["eligibility_text"] = "\n".join(lines) or None
        out["applicant_types"] = applicant_tags([SPONSOR_DUTY_RE.sub("", clause_cut(line)) for line in lines
                                                 if not PARTNER_LINE_RE.search(line)])
        return out


SITE = AlDot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
