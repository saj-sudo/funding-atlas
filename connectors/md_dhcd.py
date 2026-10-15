"""Maryland DHCD connector: state housing, energy, and neighborhood-revitalization programs.

Source: https://dhcd.maryland.gov (Drupal, maryland.gov platform; shared mechanics in
connectors/maryland_drupal.py). No API. Enumerate from sitemap.xml, fetch each candidate page, read the
themed "Application" box (`div.maryland-summary-box`) that program pages carry:

    <li><p><strong>Application status:</strong> Open</p></li>
    <li><p><strong>Application opens:</strong> September 22, 2026</p></li>
    <li><p><strong>Application closes:</strong> November 2, 2026</p></li>

A page becomes a record only if its box has a status-type label (Application / Registration / Funding /
Waitlist status). Pages without one are never records: a listing that doesn't know it's closed is worse
than none. The box's label and date wording varies page to page; `LABEL_KINDS` and `parse_box_date`
hold the whole normalization problem. See docs/connectors/md_dhcd.md for the live survey and mapping.

fetch(prior=...) skips a record page whose sitemap `lastmod` has not moved since the stored payload. Only
record pages are stored, so the ~170 box-less pages are refetched every run: a cold run is ~200 requests
and a warm run ~170 (about two minutes and 75 seconds at 0.3 s each). To force a full refetch:
  DELETE FROM raw_record WHERE source_connector = 'md_dhcd';

Out of scope here (no box on the page): multifamily financing programs (Rental Housing, LIHTC, HOME,
NHTF), the sub-programs of State Revitalization Programs (Community Legacy, Facade, Strategic Demolition,
BRNI, NCSED, SEED), and anything that only lives in a public notice. Individual and household programs
(home repair loans, EmPOWER, WAP, MEAP, HCVP) are ingested because their box is there; the municipal view
filters them out by applicant type.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import (  # noqa: F401  (re-exported for tests and the probe script)
    ELIGIBILITY_HEADING_RE,
    MONTH_YEAR_RE,
    MarylandDrupalConnector,
    applicant_types_for,
    body_sections,
    clean,
    match_required_for,
    needs_fetch,
    page_name,
    page_payload,
    parse_box,
    source_id_for,
)

CONNECTOR = "md_dhcd"
BASE = "https://dhcd.maryland.gov"
SITEMAP_URL = BASE + "/sitemap.xml"
AGENCY = "Maryland Department of Housing and Community Development"
AGENCY_CODE = "MD-DHCD"

# Sitemap paths that are never program pages.
SKIP_PATH = re.compile(
    r"^/(media|news-stories|contacts|about-us|public-information-and-media-inquiries|page-not-found"
    r"|google-translation-disclaimer|procurement)(/|$)"
    r"|special-loan-programs-local-contacts|program-contacts"
)

# Federal pass-throughs among the pages that carry a box, by source_id. Everything else is state money.
# ALNs verified on SAM.gov 2026-10-15; the Recovery Housing Program has no listing of its own, so no ALN.
PASS_THROUGH: dict[str, list[str]] = {
    "neighborhood-revitalization/community-development-funding/community-development-block-grant-program": ["14.228"],
    "neighborhood-revitalization/community-development-funding/community-development-block-grant-program/recovery-housing-program": [],
    "energy-home-repair/energy-grants-and-loans-residents/weatherization-assistance-program-wap": ["81.042"],
    "energy-home-repair/energy-grants-and-loans-residents/maryland-energy-assistance-program": ["93.568"],
}

# First URL segment -> categories. source_code is the segment.
SECTION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "housing": ("housing",),
    "energy-home-repair": ("energy", "housing"),
    "neighborhood-revitalization": ("housing",),
    "infrastructure": ("infrastructure",),
}

# Eligibility sections about things rather than people ("Eligible activities", "Eligible project
# locations", "Eligible use of funds", "Eligible contributions"). Applicant tags are inferred from the
# other eligibility sections only, so "serve residents of a Priority Funding Area" never tags a household.
THING_HEADING_RE = re.compile(
    r"project|activit|location|\buse|contribution|cost|expense|propert|improvement|\barea|\bwork|fund|service|item|repair",
    re.I,
)

# Box label (lowercased, colon and nbsp stripped) -> kind.
LABEL_KINDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(applications?|registration) status$"), "status"),
    (re.compile(r"^funding status$"), "funding_status"),
    (re.compile(r"^waitlist status$"), "waitlist_status"),
    (re.compile(r"^(application|registration)( period)? open(s|ed)?( \(expected\))?$"), "opens"),
    (re.compile(r"^(application|registration)( period)? close(s|d)?( \(expected\))?$|^application deadline$"), "closes"),
    (re.compile(r"^next funding cycle$"), "cycle"),
)
STATUS_KINDS = {"status", "funding_status", "waitlist_status"}
DATE_KINDS = {"opens", "closes", "cycle"}   # kept verbatim in closes_at_text; only opens/closes parse

ROLLING_RE = re.compile(r"until (available )?funds|rolling|ongoing", re.I)


# ---------- box rules (pure) ----------

def label_kind(label: str) -> str | None:
    for pattern, kind in LABEL_KINDS:
        if pattern.match(label):
            return kind
    return None


def has_status_label(lines: list[tuple[str, str]]) -> bool:
    return any(label_kind(label) in STATUS_KINDS for label, _ in lines)


def _first(lines: list[tuple[str, str]], kind: str) -> tuple[str, str] | None:
    for label, value in lines:
        if label_kind(label) == kind:
            return label, value
    return None


_weekday_re = re.compile(r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+", re.I)
_tail_re = re.compile(r"\s+(at|by)\s+.*$|\s*\(E[DS]T\).*$|,?\s+\d{1,2}:\d{2}.*$", re.I)


def parse_box_date(value: str) -> date | None:
    """'Friday, February 20, 2026 at 8:00 AM(EDT)' -> 2026-02-20. Month-only and prose -> None."""
    s = _weekday_re.sub("", clean(value))
    s = _tail_re.sub("", s).strip().rstrip(",").strip()
    return parse_date(s)


def _future_marker(value: str, today: date) -> bool:
    """Does an opens-line name a date, or a month-year, after today? Used only for the forecasted rule."""
    d = parse_box_date(value)
    if d is None:
        m = MONTH_YEAR_RE.match(clean(value))
        if m:
            d = parse_date(f"{m.group(1)} 1, {m.group(2)}")
    return d is not None and d > today


def status_for(lines: list[tuple[str, str]], today: date | None = None) -> str:
    today = today or date.today()
    for label, value in lines:
        kind = label_kind(label)
        v = value.lower()
        if kind == "status":
            if v == "open":
                return "open"
            if v == "closed":
                opens = _first(lines, "opens")
                return "forecasted" if opens and _future_marker(opens[1], today) else "closed"
            return "unknown"           # 'Varies by jurisdiction' and anything else
        if kind == "funding_status":
            return "exhausted" if re.search(r"fully spent|exhausted", v) else "unknown"
        if kind == "waitlist_status":
            return "unknown"
    return "unknown"


def opens_at_for(lines: list[tuple[str, str]]) -> date | None:
    line = _first(lines, "opens")
    return parse_box_date(line[1]) if line else None


def closes_at_for(lines: list[tuple[str, str]]) -> date | None:
    line = _first(lines, "closes")
    return parse_box_date(line[1]) if line else None


def closes_at_text_for(lines: list[tuple[str, str]]) -> str | None:
    parts = [f"{label}: {value}" for label, value in lines if label_kind(label) in DATE_KINDS]
    return "; ".join(parts) or None


def rolling_for(lines: list[tuple[str, str]]) -> bool | None:
    line = _first(lines, "closes")
    return True if line and ROLLING_RE.search(line[1]) else None


# ---------- the connector ----------

class Dhcd(MarylandDrupalConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    SKIP_PATH = SKIP_PATH
    SECTION_CATEGORIES = SECTION_CATEGORIES
    PASS_THROUGH = PASS_THROUGH
    THING_HEADING_RE = THING_HEADING_RE

    def is_record(self, payload: dict[str, Any]) -> bool:
        return has_status_label(parse_box(payload.get("main_html") or ""))

    def status_fields(self, payload: dict[str, Any], sections: list[tuple[str, str]], today: date) -> dict[str, Any]:
        lines = parse_box(payload.get("main_html") or "")
        return {
            "status": status_for(lines, today),
            "opens_at": opens_at_for(lines),
            "closes_at": closes_at_for(lines),
            "closes_at_text": closes_at_text_for(lines),
            "rolling": rolling_for(lines),
        }


SITE = Dhcd()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
classify_page = SITE.classify_page
iter_sitemap = SITE.iter_sitemap
eligibility_text_for = SITE.eligibility_text_for
applicant_text = SITE.applicant_text
categories_for = SITE.categories_for
_client = SITE.client   # probe script
