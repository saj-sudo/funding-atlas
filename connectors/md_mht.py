"""Maryland Historical Trust connector: historic preservation grants, loans, and tax credits.

Source: https://mht.maryland.gov/funding/ plus the Maryland Heritage Areas Program grants under
/planning-protection/ (Drupal, maryland.gov platform; shared mechanics in connectors/maryland_drupal.py).
12 program pages carry a `<h2>Timeline</h2>` section, but its bullets name months, not years:

    <li>Application opens: February</li><li>Application deadline: March</li><li>Awards announced: June</li>

so nothing on a program page says whether the current round is open. Two things on the site do, and
status comes only from them: the "Open funding opportunities" list on /funding/how-apply-grant (fetched
once per run and stamped onto every payload as `listed_open`; a failed fetch aborts the run), and the
platform summary box with an "Applications now open" heading on the open program's page. Year-round and
rolling programs are open by their own wording. Everything else is closed. Months without years are never
turned into dates; the Timeline is kept verbatim in closes_at_text. See docs/connectors/md_mht.md.

Local governments are eligible on seven of the twelve programs, which makes this the most municipal of the
three Maryland agencies so far. This connector is also the first to fill amount_max, from the regular
"Applicants may request up to $X" wording of the "Available funding" section.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import (
    ELIGIBILITY_HEADING_RE,
    MarylandDrupalConnector,
    body_sections,
    clean,
    section_lines,
    sentences,
    source_id_for,
)

CONNECTOR = "md_mht"
BASE = "https://mht.maryland.gov"
AGENCY = "Maryland Historical Trust"
AGENCY_CODE = "MD-MHT"

KEEP_PATH = re.compile(r"^/(funding|planning-protection)(/|$)")
INDEX_PATH = "funding/how-apply-grant"
OPEN_LIST_HEADING_RE = re.compile(r"open funding opportunities", re.I)
TIMELINE_RE = re.compile(r"^timeline$", re.I)
FUNDING_RE = re.compile(r"^available funding$", re.I)

# The Maritime Heritage Grant Program re-grants National Park Service money (the page says "federal
# requirements" and "non-federal match"); listing 15.925 verified on SAM.gov 2026-10-15.
PASS_THROUGH: dict[str, list[str]] = {
    "funding/maritime-heritage-grant-program": ["15.925"],
}

NOW_OPEN_RE = re.compile(r"now open", re.I)
YEAR_ROUND_RE = re.compile(r"year-round|rolling", re.I)
TIMING_RE = re.compile(r"year-round|rolling|open|clos|accept|deadline|due", re.I)
DATE = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
BOX_CLOSES_RE = re.compile(rf"applications? closes? on ({DATE})", re.I)
UP_TO_RE = re.compile(r"up to \$([\d,]+)")
RANGE_RE = re.compile(r"\$([\d,]+)\s*(?:to|-|–)\s*\$([\d,]+)")
MUST_MATCH_RE = re.compile(r"must provide (?:a )?[\d:]*\s*(?:cash |in-kind )?match", re.I)
MATCH_NOT_REQUIRED_RE = re.compile(r"match is not required", re.I)
MATCH_REQUIRED_RE = re.compile(r"match is required", re.I)


def open_paths(main_html: str) -> set[str]:
    """Paths linked under the 'Open funding opportunities' heading of the how-to-apply page. The links
    point at mht.prod.maryland.gov, so match on path only."""
    soup = BeautifulSoup(main_html, "html.parser")
    prose = soup.select_one(".usa-prose.maryland-toc-target") or soup
    out: set[str] = set()
    inside = False
    for el in prose.children:
        if isinstance(el, Tag) and el.name == "h2":
            if inside:
                break
            inside = bool(OPEN_LIST_HEADING_RE.search(el.get_text(" ")))
        elif inside and isinstance(el, Tag) and el.name in ("ul", "ol"):
            for a in el.find_all("a", href=True):
                path = urlparse(a["href"]).path.strip("/")
                if path:
                    out.add(path)
    return out


def _section(sections: list[tuple[str, str]], heading_re: re.Pattern[str]) -> str | None:
    for heading, text in sections:
        if heading_re.match(heading):
            return text or None
    return None


def box_text(main_html: str) -> str:
    """The platform summary box as one cleaned string (heading and bullets), '' when there is none."""
    box = BeautifulSoup(main_html, "html.parser").select_one(".maryland-summary-box")
    return clean(box.get_text(" ")) if box else ""


def closes_at_for(box: str) -> date | None:
    m = BOX_CLOSES_RE.search(box)
    return parse_date(m.group(1)) if m else None


def timeline_text_for(main_html: str, box: str) -> str | None:
    """Bullets joined with '; ', or the first sentence of a prose timeline; plus the box close sentence."""
    lines = section_lines(main_html, TIMELINE_RE)
    bullets = [text for tag, text in lines if tag == "li"]
    parts: list[str] = []
    if bullets:
        parts.append("; ".join(bullets))
    else:
        prose = sentences(" ".join(text for tag, text in lines if tag == "p"))
        timing = [s for s in prose if TIMING_RE.search(s)]
        if timing or prose:
            parts.append((timing or prose)[0])
    m = re.search(rf"applications? closes? on {DATE}[^.]*\.?", box, re.I)
    if m:
        parts.append(clean(m.group(0)))
    return "; ".join(parts) or None


def amounts_for(funding_text: str | None) -> tuple[int | None, int | None]:
    """'up to $X' -> (None, X). Else exactly one '$A to $B' range outside a project-cost sentence -> (A, B).
    Two ranges on one page (MHAA's capital and non-capital tiers) -> nothing, rather than a guess."""
    if not funding_text:
        return None, None
    up_to = UP_TO_RE.findall(funding_text)
    if len(up_to) == 1:
        return None, int(up_to[0].replace(",", ""))
    ranges = [
        m for s in sentences(funding_text) if "project cost" not in s.lower()
        for m in RANGE_RE.finditer(s)
    ]
    if len(ranges) == 1:
        return int(ranges[0].group(1).replace(",", "")), int(ranges[0].group(2).replace(",", ""))
    return None, None


def match_required_for(funding_text: str | None) -> bool | None:
    if not funding_text:
        return None
    if MATCH_NOT_REQUIRED_RE.search(funding_text):
        return False
    if MATCH_REQUIRED_RE.search(funding_text) or MUST_MATCH_RE.search(funding_text):
        return True
    return None


class Mht(MarylandDrupalConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    KEEP_PATH = KEEP_PATH
    PASS_THROUGH = PASS_THROUGH
    CATEGORY_CODE = "historic-preservation"
    # "Eligible applicants" on grant pages; the tax credit pages fold applicants into one "Eligibility"
    # section. "Eligible projects/properties/activities" are kept verbatim but never scanned for people.
    APPLICANT_HEADING_RE = re.compile(r"^eligible applicants|^eligibility$", re.I)

    def before_fetch(self, client: httpx.Client) -> dict[str, Any]:
        resp = client.get(f"{self.BASE}/{INDEX_PATH}")
        resp.raise_for_status()                      # no open list, no run: every status would be a guess
        return {"open_paths": sorted(open_paths(resp.text))}

    def annotate(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        listed = source_id_for(payload.get("url") or "") in set(context.get("open_paths") or [])
        return {**payload, "listed_open": listed}

    def is_record(self, payload: dict[str, Any]) -> bool:
        sections = body_sections(payload.get("main_html") or "")
        return (_section(sections, TIMELINE_RE) is not None
                and any(ELIGIBILITY_HEADING_RE.search(h) for h, _ in sections))

    def status_fields(self, payload: dict[str, Any], sections: list[tuple[str, str]], today: date) -> dict[str, Any]:
        main_html = payload.get("main_html") or ""
        box = box_text(main_html)
        timeline = _section(sections, TIMELINE_RE) or ""
        rolling = bool(YEAR_ROUND_RE.search(timeline))
        is_open = bool(payload.get("listed_open")) or bool(NOW_OPEN_RE.search(box)) or rolling
        return {
            "status": "open" if is_open else "closed",
            "opens_at": None,
            "closes_at": closes_at_for(box),
            "closes_at_text": timeline_text_for(main_html, box),
            "rolling": True if rolling else None,
        }

    def amounts(self, sections: list[tuple[str, str]]) -> tuple[int | None, int | None]:
        return amounts_for(_section(sections, FUNDING_RE))

    def match_text(self, sections: list[tuple[str, str]]) -> str:
        return _section(sections, FUNDING_RE) or ""

    def match_required_for(self, text: str) -> bool | None:
        return match_required_for(text or None)


SITE = Mht()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
classify_page = SITE.classify_page
iter_sitemap = SITE.iter_sitemap
