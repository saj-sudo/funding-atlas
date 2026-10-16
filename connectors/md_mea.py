"""Maryland Energy Administration connector: energy grants, rebates, loans and one tax credit.

Source: https://energy.maryland.gov (SharePoint, the state's `mdgov` theme; shared mechanics in
connectors/maryland_sharepoint.py). There is no single linked index: `/Pages/all-incentives.aspx` lists the FY27
programs in sector tables whose rows are unlinked. The five category pages (Renewables, Energy Efficiency,
Transportation, Resiliency, Communities) each link their programs as a table of `<a>` title + description under
`<h3>` headings ("Grants", "Rebates", "Tax Credits", "Archived Programs"); the union is 34 paths, 6 of them 404 on
2026-10-16 (every archived program and one rebate). The union is the enumeration; which indexes list a page, and
under which heading, is stamped onto its payload.

Program pages are prose with labeled lines, bold label then colon then value, in one block or split over two:

    Online Application Portal Status: Open to new applications
    Application Deadline: 3:00 PM ET, November 18, 2026 through the JotForm application portal.
    Program Launch Date: September 9, 2026          (or: Funding Opportunity Announcement Issue Date)
    Target Audience: Maryland counties, cities, towns, and other Authorities Having Jurisdiction (AHJs) ...
    Anticipated Program Budget: MEA anticipates up to $3,800,000 ...   (a pot, never an award size)

Older pages say it in prose instead: "The Local Government Energy Modernization Program (L-GEM) is CLOSED",
"Now Open! FY27 Commercial & Community Buildings Grant Program", "FY26 PROGRAM NOW ACCEPTING APPLICATIONS".
Status is read in that order (first status line; else closed prose, which beats open prose; else open prose), then
a stated launch date in the future turns a closed or undecided page into `forecasted`, and a page that states only
a deadline is `open` while the deadline is ahead and `unknown` once it has passed. Everything else is `unknown`.
See docs/connectors/md_mea.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import Tag

from connectors.maryland_drupal import NEGATION_RE, PAGE_DELAY_S, clean, funding_type_for
from connectors.maryland_sharepoint import (
    BODY_SELECTOR,
    MONTH,
    MarylandSharePointConnector,
    canonical_url,
    leaf_lines,
    main_section,
    page_h1,
    page_sentences,
    parse_text_date,
    source_id_for,
)
from pipeline.models import CategoryTag

CONNECTOR = "md_mea"
BASE = "https://energy.maryland.gov"
AGENCY = "Maryland Energy Administration"
AGENCY_CODE = "MD-MEA"

# The hand-curated category indexes, as lowercase paths.
INDEX_PATHS: tuple[str, ...] = (
    "pages/renewables.aspx",
    "pages/energyefficiency.aspx",
    "transportation/pages/incentives.aspx",
    "pages/resiliency.aspx",
    "pages/communities.aspx",
)
# Linked from the indexes but not programs: the news page, the EmPOWER fact page, the home page.
SKIP_PATH = re.compile(r"^pages/(?:news|default|all-incentives|facts/)", re.I)
ARCHIVED_RE = re.compile(r"archived", re.I)

# The SolarAPP+ page says the money is U.S. Department of Energy State Energy Program funding; 81.041 verified on
# SAM.gov 2026-10-16. Maryland RISE says "federally-funded" without naming the program: direct until it does.
PASS_THROUGH: dict[str, list[str]] = {
    "govt/pages/solarapp.aspx": ["81.041"],
}

# Labeled lines: `<strong>Label:</strong> value` in one block, or the value in the next block. Labels are
# lowercased with a leading fiscal-year prefix ("FY27 ") stripped before matching.
LABEL_RE = re.compile(r"^([A-Za-z][^:]{2,70}?)\s*:\s*(.*)$", re.S)
FY_PREFIX_RE = re.compile(r"^fy\s?\d{2,4}\s+", re.I)
LABEL_KINDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("status", re.compile(r"^(?:online )?(?:application |program )?(?:portal )?status$")),
    ("deadline", re.compile(r"^(?:program |anticipated )?(?:program )?application deadline$|^deadline$")),
    ("launch", re.compile(r"^(?:program |estimated |anticipated )?launch date$"
                          r"|^funding opportunity announcement issue date$")),
    ("audience", re.compile(r"^(?:target )?audience$|^eligible (?:entity types|applicants|entities)(?: are| include)?$")),
    ("program_type", re.compile(r"^(?:program type|type of (?:grant )?program)$")),
)

CLOSED_VALUE_RE = re.compile(r"\b(?:closed|inactive)\b", re.I)
OPEN_VALUE_RE = re.compile(r"\bopen\b", re.I)
CLOSED_RE = re.compile(
    r"\bis (?:now )?(?:closed|inactive)\b|\bare (?:now )?closed\b|\bnow closed\b|closed to new applications"
    r"|no longer accepting|program is closed",
    re.I,
)
DEPLETED_RE = re.compile(r"deplet|exhaust|fully (?:reserved|awarded|expended|subscribed)", re.I)
OPEN_RE = re.compile(r"\bnow open\b|\bis (?:currently )?open\b|\bnow accepting\b|accepting applications|remains open", re.I)
ROLLING_RE = re.compile(r"ongoing|remains open|until (?:funding|funds)|first-come|rolling", re.I)
OPENS_RE = re.compile(rf"\b(?:opens|will open|launch(?:es)?)\b[^.]{{0,40}}?({MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})", re.I)
APPLICANT_SENTENCE_RE = re.compile(
    r"\bmay apply\b|\beligible (?:applicants?|entit\w*|to apply)\b|\b(?:is|are) open to\b|\bavailable to\b", re.I
)


# ---------- pure helpers (no I/O) ----------

def label_kind(label: str) -> str | None:
    key = FY_PREFIX_RE.sub("", label.strip().lower())
    key = re.sub(r"\s+", " ", key)
    for kind, pattern in LABEL_KINDS:
        if pattern.match(key):
            return kind
    return None


def labeled_lines(main_html: str) -> list[tuple[str, str, str]]:
    """(kind, label, value) for every line of the form `Label: value` whose label is one of LABEL_KINDS, in page
    order. An empty value takes the next line unless that line is itself a known label."""
    lines = leaf_lines(main_html)
    out: list[tuple[str, str, str]] = []
    for i, text in enumerate(lines):
        m = LABEL_RE.match(text)
        if not m:
            continue
        kind = label_kind(m.group(1))
        if kind is None:
            continue
        value = clean(m.group(2))
        if not value and i + 1 < len(lines):
            nxt = LABEL_RE.match(lines[i + 1])
            if not (nxt and label_kind(nxt.group(1))):
                value = lines[i + 1]
        out.append((kind, clean(m.group(1)), value))
    return out


def first_value(lines: list[tuple[str, str, str]], kind: str) -> str | None:
    return next((value for k, _, value in lines if k == kind and value), None)


def status_from_lines(lines: list[tuple[str, str, str]]) -> str | None:
    """The first status line decides: closed/inactive wording -> closed, open wording -> open, else undecided."""
    value = first_value(lines, "status")
    if not value:
        return None
    if CLOSED_VALUE_RE.search(value):
        return "closed"
    if OPEN_VALUE_RE.search(value):
        return "open"
    return None


def status_from_prose(sents: list[str]) -> str | None:
    """Closed wording beats open wording; a closed sentence that blames funding is `exhausted`."""
    for s in sents:
        if CLOSED_RE.search(s):
            return "exhausted" if DEPLETED_RE.search(s) else "closed"
    for s in sents:
        if OPEN_RE.search(s):
            return "open"
    return None


def status_fields_for(main_html: str, index: dict[str, str], today: date) -> dict[str, Any]:
    lines = labeled_lines(main_html)
    sents = page_sentences(main_html)
    archived_only = bool(index) and all(ARCHIVED_RE.search(h or "") for h in index.values())

    status = "closed" if archived_only else None
    if status is None:
        status = status_from_lines(lines)
    if status is None:
        status = status_from_prose(sents)

    deadline = first_value(lines, "deadline")
    closes_at = parse_text_date(deadline)
    launch = first_value(lines, "launch")
    opens_at = parse_text_date(launch)
    if opens_at is None and not launch:
        m = next((m for s in sents for m in [OPENS_RE.search(s)] if m), None)
        opens_at = parse_text_date(m.group(1)) if m else None

    if status in (None, "closed") and opens_at and opens_at > today:
        status = "forecasted"
    if status is None and closes_at:
        status = "open" if closes_at >= today else "unknown"
    if status is None:
        status = "unknown"

    timing = [f"{label}: {value}" for kind, label, value in lines if kind in ("status", "deadline", "launch")]
    return {
        "status": status,
        "opens_at": opens_at,
        "closes_at": closes_at,
        "closes_at_text": "; ".join(timing) or None,
        "rolling": True if status == "open" and deadline and ROLLING_RE.search(deadline) else None,
    }


def applicant_lines_for(main_html: str) -> list[str]:
    """The audience lines plus the body sentences that say who may apply, minus negated ones."""
    lines = labeled_lines(main_html)
    out = [f"{label}: {value}" for kind, label, value in lines if kind == "audience" and value]
    for s in page_sentences(main_html):
        if APPLICANT_SENTENCE_RE.search(s) and not NEGATION_RE.search(s) and s not in out:
            out.append(s)
    return out


def funding_type_for_page(name: str, main_html: str) -> str | None:
    if "rebate" in name.lower():
        return "rebate"
    ft = funding_type_for(name)
    if ft:
        return ft
    for kind, label, value in labeled_lines(main_html):
        if kind != "program_type":
            continue
        pt = f"{label} {value}".lower()
        for keyword, kind_ft in (("rebate", "rebate"), ("tax credit", "tax_credit"), ("loan", "loan"),
                                 ("grant", "grant"), ("challenge", "other"), ("prize", "other"), ("auction", "other")):
            if keyword in pt:
                return kind_ft
    return None


def program_name(main_html: str, title: str | None) -> str:
    name = page_h1(main_html) or clean(title)
    return FY_PREFIX_RE.sub("", name).strip() or name


def index_links(index_url: str, html_text: str) -> dict[str, dict[str, Any]]:
    """source_id -> {url, heading} for every on-site .aspx link in the body of one index page, with the text of
    the nearest preceding heading ("Grants", "Archived Programs", or '' before the first heading)."""
    section = main_section(html_text)
    if section is None:
        return {}
    body = section.select_one(BODY_SELECTOR) or section
    host = urlparse(BASE).netloc
    out: dict[str, dict[str, Any]] = {}
    heading = ""
    for el in body.descendants:
        if not isinstance(el, Tag):
            continue
        if el.name in ("h2", "h3", "h4"):
            text = clean(el.get_text(" "))
            if text:
                heading = text
        elif el.name == "a" and el.get("href"):
            url = canonical_url(el["href"], index_url)
            parsed = urlparse(url)
            if parsed.netloc.lower().removeprefix("www.") != host or not parsed.path.lower().endswith(".aspx"):
                continue
            sid = source_id_for(url)
            if not sid or sid in INDEX_PATHS or SKIP_PATH.search(sid):
                continue
            out.setdefault(sid, {"url": url, "heading": heading})
    return out


# ---------- the connector ----------

class Mea(MarylandSharePointConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    PASS_THROUGH = PASS_THROUGH

    def index_entries(self, client: httpx.Client) -> dict[str, dict[str, Any]]:
        """source_id -> {url, index: {index_path: heading}} across the five indexes."""
        entries: dict[str, dict[str, Any]] = {}
        for path in INDEX_PATHS:
            url = f"{BASE}/{path}"
            resp = client.get(url)
            resp.raise_for_status()
            time.sleep(PAGE_DELAY_S)
            for sid, link in index_links(url, resp.text).items():
                entry = entries.setdefault(sid, {"url": link["url"], "index": {}})
                entry["index"][path] = link["heading"]
        return entries

    def name_for(self, payload: dict[str, Any]) -> str:
        return program_name(payload.get("main_html") or "", payload.get("title"))

    def status_fields(self, payload: dict[str, Any], today: date) -> dict[str, Any]:
        return status_fields_for(payload.get("main_html") or "", payload.get("index") or {}, today)

    def applicant_lines(self, payload: dict[str, Any]) -> list[str]:
        return applicant_lines_for(payload.get("main_html") or "")

    def categories_for(self, payload: dict[str, Any]) -> list[CategoryTag]:
        tags = [CategoryTag(value="energy", source_code="mea")]
        if any(path.startswith("transportation/") for path in payload.get("index") or {}):
            tags.append(CategoryTag(value="transportation", source_code="transportation/pages/incentives.aspx"))
        return tags

    def funding_type_for(self, name: str, payload: dict[str, Any]) -> str | None:
        return funding_type_for_page(name, payload.get("main_html") or "")


SITE = Mea()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
classify_page = SITE.classify_page
