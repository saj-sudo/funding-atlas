"""Wisconsin Department of Administration connector: the State CDBG programs of its Division of Energy, Housing and
Community Resources (milestone 12.9).

Source: https://energyandhousing.wi.gov, SharePoint publishing pages; one GET per page, 3 s apart; `/robots.txt` answers
404. The reader is this module's own. The program's text is in `main#main` (the page's rich-text fields); the title is the
`h1`. SharePoint leaves zero-width spaces through the text and wraps list items in paragraphs; both are folded. The read
stops at the contact block. Status table and field mapping are the agency-page table in `connectors/hand_list.py`, with
rules of this module's own for what these pages say: "accepted on a continuous basis" and "may be submitted at any time"
are open and rolling, "Application Available: <date>" is the opening date, and a cycle stated without a date is kept as
text. The Planning page names no applicant; the hub's sentence is quoted by hand. Left out: CDBG-DR, CDBG-CV (closed,
one-time), the Flexible Facilities Program (no new awards), the housing programs for developers and agencies.
See docs/connectors/wisconsin.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors import hand_list as hl
from connectors.hand_list import AgencyPageConnector, blocks_from, soup
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "wi_doa"
BASE = "https://energyandhousing.wi.gov"
AGENCY = "Wisconsin Department of Administration, Division of Energy, Housing and Community Resources"
AGENCY_CODE = "WI-DOA"
CATEGORY_LABEL = "community development"
LABEL_MAX_CHARS = 90
_P = "/Pages/AgencyResources"

PAGES: dict[str, str] = {
    "public-facilities": f"{_P}/CDBG-PF.aspx",
    "planning": f"{_P}/CDBG-PLNG.aspx",
    "public-facilities-economic-development": f"{_P}/CDBG-PFED.aspx",
    "economic-development": f"{_P}/CDBG-ED.aspx",
    "emergency-assistance": f"{_P}/CDBG-EAP.aspx",
    "affordable-housing-conversion": f"{_P}/AffordableHousingConversion.aspx",
    # 12.11: "Towns, villages, cities with populations under 50,000, and most counties ... are eligible to apply"
    "cdbg-housing": f"{_P}/CDBG.aspx",
}
# The housing program is the one record that is not about public works (12.11).
CATEGORY_LABELS = {"cdbg-housing": "housing"}
# State CDBG is HUD money ("Funding for CDBG programs is provided by the U.S. Department of Housing and Urban Development
# (HUD)", the Community Resources hub); not every program page repeats it.
# The five CDBG records are pass-through by their names (the shared `CDBG_NAME_RE`); the conversion program's page does
# not name its HUD source.
FUNDING_SOURCES = {"affordable-housing-conversion": "pass_through"}
# The Planning page never says who may apply; the hub that links it does.
HAND_QUOTES = {"planning": ("2026-11-24", "DEHCR Community Resources page (/Pages/CommunityResources.aspx)", [
    "Planning Program (CDBG-PLNG) – provides grant funds to local governments to support planning efforts that improve "
    "community opportunities and vitality."])}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
ZERO_WIDTH_RE = re.compile("[​‌‍﻿]")
# contact lines, the mailing address, and lines that are only a document link
DROP_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|@wisconsin\s*\.gov|\[email\s*protected\]|\bPO Box\b"
                     r"|\bmailing address\b|\((?:PDF|Word|Excel)\)$", re.I)
STOP_RE = re.compile(r"^(?:contact.*|cdbg program quick links)$", re.I)
# "Application Available: January 18, 2027" (Affordable Housing Conversion's timeline)
AVAILABLE_RE = re.compile(r"^application available:", re.I)
# No dated round: "Typically applications are due in mid-May each year." (PF), "... must submit a notice of intent to apply
# within 90 days of the disaster event." (EAP)
YEARLESS_RE = re.compile(r"\btypically\b[^.]*\bdue in\b|\bwithin \d+ days of the disaster event\b", re.I)
# Who may apply, in sentence forms the shared reader does not know: "Grants are awarded to units of general local
# government", "CDBG-PFED grant funds (PDF) are awarded to local governments", "CDBG-EAP funds are used to assist local units
# of government", "... (AHC) program ... supports local governments in funding housing initiatives".
APPLICANT_RE = re.compile(r"\b(?:grants?|funds)\b[^.]{0,20}\bare (?:awarded to|used to assist)\b|\bsupports local governments\b"
                          r"|\blocal unit of government interested in applying\b", re.I)
# "... are awarded to local governments to assist businesses to create or retain jobs ...", "... to assist local units of
# government in addressing emergency housing, ... and business assistance needs", "supports local governments in funding
# housing initiatives primarily benefiting low to moderate income (LMI) individuals": what the money is for names who
# benefits, not who applies. Cut before tagging; the stored text keeps it.
PURPOSE_CUT_RE = re.compile(r"\b(?:to assist businesses|for public infrastructure projects that support business|in addressing|in funding)"
                            r"\b[^.;]*", re.I)


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and the blocks of `main#main` up to the contact block."""
    doc = soup(ZERO_WIDTH_RE.sub("", page_html.replace("&#8203;", "")))
    main = doc.find("main")
    if main is None:
        return {"title": "", "blocks": []}
    h1 = main.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    for tag in main.find_all(["span", "font"]):   # the editor splits words across spans ("F<span>or each</span>")
        tag.unwrap()
    main.smooth()
    for li in main.find_all("li"):   # "<li><p>Real Property Acquisition</p></li>" is read once, through its paragraph
        if li.find("p"):
            li.name = "div"
    for li in main.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(main, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks}


class WiDoa(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "WI"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    FUNDING_SOURCES = FUNDING_SOURCES
    CATEGORY_LABELS = CATEGORY_LABELS
    HAND_QUOTES = HAND_QUOTES
    YEARLESS_RE = YEARLESS_RE

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        sents = hl.all_sentences([tuple(b) for b in raw.payload["page"].get("blocks", [])])
        lines = [s for s in sents if APPLICANT_RE.search(s)]
        lines += [line for line in (out["eligibility_text"] or "").split("\n") if line and line not in lines]
        out["eligibility_text"] = "\n".join(lines) or None
        out["applicant_types"] = hl.applicant_tags([PURPOSE_CUT_RE.sub("", hl.clause_cut(line)) for line in lines])
        available = next((hl.first_date(s) for s in sents if AVAILABLE_RE.search(s)), None)
        if available and out["opens_at"] is None:
            out["opens_at"] = available
            if out["status"] == "open" and available > today:
                out["status"] = "forecasted"
        return out


SITE = WiDoa()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
