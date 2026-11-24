"""Georgia Department of Community Affairs connector: the state CDBG's annual competition and set-asides, and the
OneGeorgia Authority's Equity Fund (milestone 12.9).

Source: https://dca.georgia.gov, Drupal (the state's GovHub theme, behind Cloudflare, which answered every request); one
GET per page in `PAGES`. No other Georgia agency is read, so the reader is this module's own. The program's text is in
`main.content-page__main`; the title is its `h1` (inside a `header` there). The embedded cards (`article.embedded-entity`:
a contact card with a Cloudflare-obscured address, a flyer, a regulations link, "Documents & Downloads") are dropped, but
a card that says "Apply ..." is kept as a heading ("Apply for the FY2027 CDBG Annual Competition": the only line on the page
that names a round; no date, so the status stays `unknown` and the line is kept as `closes_at_text`). The Equity Fund's
"Online Applications are accepted quarterly on the 2nd Friday of the following months:" and the four months after it are
read as one sentence. Status table and field mapping are the agency-page table in `connectors/hand_list.py`. Left out:
CDBG-DR, the Rural Downtown Redevelopment Grant (one-time, awarded in 2022), the EDGE Fund, REBA and the tax incentives
(business deals), Section 108 loans, CHIP and the regional commissions (not surveyed). See docs/connectors/georgia.md.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.hand_list import (
    AgencyPageConnector,
    Blocks,
    all_sentences,
    applicant_tags,
    blocks_from,
    clause_cut,
    soup,
)
from connectors.sam_assistance_listings import clean

CONNECTOR = "ga_dca"
BASE = "https://dca.georgia.gov"
AGENCY = "Georgia Department of Community Affairs"
AGENCY_CODE = "GA-DCA"
CATEGORY_LABEL = "community development"
LABEL_MAX_CHARS = 90
_CDBG = "/financing-tools/infrastructure/community-development-block-grants-cdbg"

PAGES: dict[str, str] = {
    "cdbg-annual": f"{_CDBG}/annual-cdbg-competition",
    "cdbg-eip": f"{_CDBG}/employment-incentive-program",
    "cdbg-redevelopment": f"{_CDBG}/redevelopment-fund",
    "cdbg-itad": f"{_CDBG}/immediate-threat-and-danger",
    "onegeorgia-equity": "/financing-tools/infrastructure/onegeorgia-authority/equity-fund",
}
# Page titles that do not say whose fund or what kind of thing it is, named as the page's own text does.
NAMES = {"Equity Fund": "OneGeorgia Equity Fund", "Immediate Threat and Danger": "Immediate Threat and Danger Program"}
# Each set-aside page says it is part of the state CDBG program without naming HUD; DCA's Infrastructure page: "The CDBG
# Program is a federally-funded grant for states". The Equity Fund is the OneGeorgia Authority's own.
FUNDING_SOURCES = {"cdbg-annual": "pass_through", "cdbg-eip": "pass_through", "cdbg-redevelopment": "pass_through",
                   "cdbg-itad": "pass_through", "onegeorgia-equity": "direct"}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
DROP_RE = re.compile(r"\[email\s*protected\]|@dca\.ga\.gov|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|^review the .* faqs\b", re.I)
STOP_RE = re.compile(r"(?:frequently asked questions|.*documents & downloads)$", re.I)
APPLY_CARD_RE = re.compile(r"^apply\b", re.I)
# "Apply for the FY2027 CDBG Annual Competition" (a fiscal year, no date); "Online Applications are accepted quarterly on
# the 2nd Friday of the following months: January, April, July, October" (no year).
YEARLESS_RE = re.compile(r"^apply for the FY\d{4}\b|\baccepted quarterly\b", re.I)
LIST_LEAD_RE = re.compile(r"\bof the following months:$", re.I)
# Who the money goes to, said without an eligibility word. RDF: "The RDF provides local governments access to flexible
# financial assistance ..."; EIP: "A provider of infrastructure financing to local governments with projects that ...".
RECIPIENT_RE = re.compile(r"\bprovides local governments access to\b|\bfinancing to local governments\b", re.I)
# HUD's term for a city, town or county ("units of general local government", "units of general purpose local government")
# is tagged as "units of local government"; what follows "excluding" (entitlement cities and urban counties) is who may not.
GENERAL_RE = re.compile(r"\bunits of general[- ](?:purpose )?local government\b", re.I)
EXCLUDING_RE = re.compile(r",?\s*\bexcluding\b.*$", re.I)
# The annual competition's match depends on the grant's size ("Grants up to $500,000 ... no matching funds required").
MATCH_VARIES = {"cdbg-annual"}


def tag_line(line: str) -> str:
    """What the shared tagger reads of an eligibility line: a recipient sentence is its matched phrase alone (both go on
    to say what the projects "cannot" do, which the tagger takes for a negation)."""
    hit = RECIPIENT_RE.search(line)
    if hit:
        return hit.group(0)
    return clause_cut(EXCLUDING_RE.sub("", GENERAL_RE.sub("units of local government", line)))


def join_month_list(blocks: Blocks) -> Blocks:
    """A paragraph that ends "... of the following months:" takes the list items after it into its sentence."""
    out: Blocks = []
    lead = False
    for kind, text in blocks:
        if lead and kind == "li":
            prev = out[-1][1]
            out[-1] = ("p", f"{prev}{' ' if prev.endswith(':') else ', '}{text}")
            continue
        lead = bool(LIST_LEAD_RE.search(text))
        out.append((kind, text))
    return out


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and the blocks of the content column, the embedded cards dropped but an "Apply ..." card's title."""
    doc = soup(page_html)
    main = doc.select_one("main.content-page__main") or doc.find("main")
    if main is None:
        return {"title": "", "blocks": []}
    h1 = main.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    for card in main.select("article.embedded-entity"):
        h2 = card.find("h2")
        if h2 is not None and APPLY_CARD_RE.search(clean(h2.get_text(" "))):
            card.replace_with(h2.extract())
        else:
            card.decompose()
    for li in main.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(main, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": NAMES.get(title, title), "blocks": join_month_list(blocks)}


class GaDca(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "GA"
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    DELAY_S = 3.0
    FUNDING_SOURCES = FUNDING_SOURCES
    YEARLESS_RE = YEARLESS_RE

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def fields(self, raw: Any, today: date) -> dict[str, Any]:
        """The agency-page fields, with this site's recipient sentences added to the eligibility lines and HUD's "units of
        general local government" tagged as local governments."""
        out = super().fields(raw, today)
        lines = out["eligibility_text"].split("\n") if out["eligibility_text"] else []
        blocks = [tuple(b) for b in raw.payload["page"].get("blocks", [])]
        lines += [s for s in all_sentences(blocks) if RECIPIENT_RE.search(s) and s not in lines]
        out["eligibility_text"] = "\n".join(lines) or None
        out["applicant_types"] = applicant_tags([tag_line(line) for line in lines])
        if raw.source_id in MATCH_VARIES:
            out["match_required"] = None
        return out


SITE = GaDca()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
