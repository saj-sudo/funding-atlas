"""Maryland Department of Commerce connector: business grants, loans, and tax incentives.

Source: https://commerce.maryland.gov/financial-incentives/ (Drupal, maryland.gov platform; shared
mechanics in connectors/maryland_drupal.py). 36 program pages, each opening with a `<h2>Program Status</h2>`
section whose first sentences are formulaic prose:

    The program is currently active. Applications are accepted on a rolling basis ...
    The program is active but between funding rounds. The most recent application period closed January 30, 2026.
    Applications are not being accepted at this time. Check this page for the next application window (August 2, 2027).

A page becomes a record only if it has that section. "Active" in Commerce's usage means the program exists
in statute, so closed wording beats active wording and a page with neither is `unknown`. Dates are read from
the status text sentence by sentence, never from sunset sentences ("remains in effect until January 1,
2032"). See docs/connectors/md_commerce.md for the survey and every opening sentence seen.

Mostly business-facing. Advantage Maryland names counties and municipalities; the rest reach the registry
for breadth and are filtered out of the municipal view by their applicant types.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import (
    MarylandDrupalConnector,
    body_sections,
    funding_type_for,
    sentences,
)
from pipeline.models import CategoryTag

CONNECTOR = "md_commerce"
BASE = "https://commerce.maryland.gov"
AGENCY = "Maryland Department of Commerce"
AGENCY_CODE = "MD-COMMERCE"

KEEP_PATH = re.compile(r"^/financial-incentives/")
STATUS_HEADING_RE = re.compile(r"^program status$", re.I)

# ExportMD is funded through the SBA State Trade Expansion Program cooperative agreement (the page says so;
# ALN verified on SAM.gov 2026-10-15). MSBDFA mentions SSBCI money but is a state authority: direct.
PASS_THROUGH: dict[str, list[str]] = {
    "financial-incentives/grants/exportmd-program": ["59.061"],
}

# URL section -> funding_type when the name has no keyword.
SECTION_FUNDING_TYPE = {"grants": "grant", "loans-financing": "loan", "tax-incentives": "tax_credit"}

CLOSED_RE = re.compile(
    r"not being accepted|between funding rounds|currently closed|\bis closed\b|closed to new|window has closed"
    r"|deadline has passed|dates have passed|sunsetted|no later round",
    re.I,
)
OPEN_RE = re.compile(
    r"currently active|\bis active\b|\bis ongoing\b|\bis open\b|now open|accepting (?:new )?applications"
    r"|accepts applications|applications are accepted|are accepting",
    re.I,
)
ROLLING_RE = re.compile(
    r"rolling basis|no fixed deadline|no fixed application window|no annual deadline"
    r"|no statewide application deadline|every month|year-round",
    re.I,
)
# Sentences about when the program itself expires, not when applications are due.
SUNSET_RE = re.compile(r"sunset|in effect|taxable years|terminates", re.I)
DATE = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},\s+\d{4}"
)
OPENS_RE = re.compile(rf"\b(?:opened|opens)(?: on)?\s+({DATE})|\bfrom\s+({DATE})", re.I)
CLOSES_RE = re.compile(rf"\b(?:closed|closes|through|until(?: the)?)(?: on)?\s+({DATE})|\bdeadline\b.{{0,80}}?({DATE})", re.I)
NEXT_RE = re.compile(rf"\bnext\b[^.]*?({DATE})", re.I)
TIMING_WORD_RE = re.compile(r"rolling|deadline|round|window|every month|year-round|\bdue\b|opened|closed|opens|closes", re.I)


def parse_text_date(value: str) -> date | None:
    """'Aug. 3, 2026' / 'August 3, 2026' -> 2026-08-03."""
    return parse_date(re.sub(r"^([A-Za-z]+)\.", r"\1", value.strip()))


def status_text_for(sections: list[tuple[str, str]]) -> str | None:
    for heading, text in sections:
        if STATUS_HEADING_RE.match(heading):
            return text or None
    return None


def timing_sentences(status_text: str) -> list[str]:
    """The sentences of the status text that talk about timing (a date alone is not enough: "amended by
    the DECADE Act effective July 1, 2026" is not a deadline), minus sunset sentences."""
    return [s for s in sentences(status_text) if not SUNSET_RE.search(s) and TIMING_WORD_RE.search(s)]


def _first_date(pattern: re.Pattern[str], text: str) -> date | None:
    m = pattern.search(text)
    if not m:
        return None
    return parse_text_date(next(g for g in m.groups() if g))


def status_for(status_text: str, today: date) -> str:
    if CLOSED_RE.search(status_text):
        nxt = _first_date(NEXT_RE, " ".join(timing_sentences(status_text)))
        return "forecasted" if nxt and nxt > today else "closed"
    if OPEN_RE.search(status_text):
        return "open"
    return "unknown"


def fields_for(status_text: str | None, today: date) -> dict[str, Any]:
    if not status_text:
        return {"status": "unknown"}
    status = status_for(status_text, today)
    timing = " ".join(timing_sentences(status_text))
    out: dict[str, Any] = {"status": status, "closes_at_text": timing or None}
    if status == "forecasted":
        out["opens_at"] = _first_date(NEXT_RE, timing)        # the announced next window, not the last one
    else:
        out["opens_at"] = _first_date(OPENS_RE, timing)
        out["closes_at"] = _first_date(CLOSES_RE, timing)
    if status == "open" and ROLLING_RE.search(status_text):
        out["rolling"] = True
    return out


class Commerce(MarylandDrupalConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    KEEP_PATH = KEEP_PATH
    PASS_THROUGH = PASS_THROUGH
    # "Who Can Apply" / "Who This Is For" / "Who's Eligible" name the applicants. "Key Eligibility
    # Requirements" is kept verbatim but not scanned: "locate in a Tier 1 county" would tag a county.
    ELIGIBILITY_HEADING_RE = re.compile(r"eligib|^who\b", re.I)
    APPLICANT_HEADING_RE = re.compile(r"^who\b", re.I)

    def is_record(self, payload: dict[str, Any]) -> bool:
        return status_text_for(body_sections(payload.get("main_html") or "")) is not None

    def status_fields(self, payload: dict[str, Any], sections: list[tuple[str, str]], today: date) -> dict[str, Any]:
        return fields_for(status_text_for(sections), today)

    def funding_type_for(self, name: str, source_id: str) -> str | None:
        if "exemption" in name.lower():
            return "other"
        return funding_type_for(name) or SECTION_FUNDING_TYPE.get(_section(source_id))

    def categories_for(self, source_id: str) -> list[CategoryTag]:
        return [CategoryTag(value="other", source_code=_section(source_id))]


def _section(source_id: str) -> str:
    parts = source_id.split("/")
    return parts[1] if len(parts) > 1 else parts[0]


SITE = Commerce()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
classify_page = SITE.classify_page
iter_sitemap = SITE.iter_sitemap
