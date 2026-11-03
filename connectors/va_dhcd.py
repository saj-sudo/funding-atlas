"""Virginia Department of Housing and Community Development connector: the program pages its menus reach.

Source: https://www.dhcd.virginia.gov (Drupal 10, no index, no sitemap). Three section pages lead by "Click Here"
teasers to landing pages and program pages; the crawl follows teasers on the host to depth three, fetching each page
once (about 90 requests a run). A page is a program when one of its detail boxes is labelled "Eligibility" (22 on
2026-11-03): the agency's own marker, since the template also serves resource and council pages. Applicants come from
that box; dates from the one sentence that states a cycle; the contact block's people are never read. See
docs/connectors/va_dhcd.md.
"""

from __future__ import annotations

import re
import time
from collections import deque
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Comment, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for
from pipeline.models import ApplicantTag, Program, RawRecord

CONNECTOR = "va_dhcd"
BASE = "https://www.dhcd.virginia.gov"
HOSTS = {"www.dhcd.virginia.gov", "dhcd.virginia.gov"}
SECTIONS = ("/communities", "/housing", "/businesses")
MAX_DEPTH = 3
CHROME = {"/", "/about", "/housing", "/businesses", "/communities", "/codes", "/broadband", "/foia", "/contact-us",
          "/getting-started", "/results", "/user/login"}
AGENCY = "Department of Housing and Community Development"
AGENCY_CODE = "VA-DHCD"
JURISDICTION = "VA"
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

ELIGIBILITY_LABEL = "eligibility"
CYCLE_RE = re.compile(
    r"\b(?:deadline|(?:are|is|be) due\b|due (?:date|on|by)\b|application period|timeline for submission"
    r"|applications? (?:are|will be) (?:accepted|due)|(?:submitted|received)(?: to \w+)? by\b|accepting applications"
    r"|now closed|is closed|are closed|closed to new"
    r"|open for submitting|open basis|rolling basis)", re.I)
CLOSED_RE = re.compile(r"\b(?:now closed|is closed|are closed|closed to new)\b", re.I)
ROLLING_RE = re.compile(r"\b(?:rolling|open basis)\b", re.I)
RANGE_RE = re.compile(r"\bfrom\b.*\b(?:to|through|until)\b", re.I)
DUE_RE = re.compile(r"\b(?:due|deadline|by|through|until|no later than)\b", re.I)
FULL_DATE_RE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b")


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


# ---------- parsing (no I/O) ----------

def _soup(page_html: str) -> BeautifulSoup:
    soup = BeautifulSoup(page_html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return soup


def page_path(href: str) -> str | None:
    """`http://www.dhcd.virginia.gov/irf`, `/irf` -> `/irf`; None for other hosts, files, anchors and the chrome."""
    full = urljoin(BASE + "/", href.strip())
    parts = urlparse(full)
    if parts.netloc not in HOSTS or parts.scheme not in ("http", "https"):
        return None
    path = parts.path.rstrip("/") or "/"
    if path in CHROME or "." in path.rsplit("/", 1)[-1] or not re.fullmatch(r"/[a-z0-9-]+", path):
        return None
    return path


def parse_teasers(page_html: str) -> list[str]:
    """The paths the page's "Click Here" / "Learn More" buttons point at, in page order, each once."""
    soup = _soup(page_html)
    main = soup.find("main") or soup
    out: list[str] = []
    for a in main.select("a.button[href], .orange-tabs a[href], a .orange-tabs"):
        link = a if a.name == "a" else a.find_parent("a")
        if link is None:
            continue
        path = page_path(link.get("href", ""))
        if path and path not in out:
            out.append(path)
    return out


def _lines(el: Tag | None) -> list[str]:
    if el is None:
        return []
    blocks = el.find_all(["p", "li", "h2", "h3", "h4", "h5"]) or [el]
    out = []
    for b in blocks:
        text = clean(b.get_text(" ")) if b.name != "li" else clean(" ".join(b.find_all(string=True, recursive=False)) or b.get_text(" "))
        if text:
            out.append(text)
    return out


def parse_program(page_html: str) -> dict[str, Any]:
    """title, intro (lines), body (lines), boxes [{label, lines}]. Nothing from the contact block's people."""
    soup = _soup(page_html)
    title = soup.title.get_text(" ") if soup.title else ""
    title = clean(title.split("|")[0]) if "|" in title else clean(title)
    contact = soup.select_one("div.programcontact")
    intro = _lines(contact.select_one("div.content")) if contact else []
    body = _lines(soup.select_one("article .field--name-body"))
    boxes = []
    for box in soup.select("div.detail_box"):
        label = box.select_one(".header .text")
        boxes.append({"label": clean(label.get_text(" ")) if label else "", "lines": _lines(box.select_one("div.content"))})
    return {"title": title, "intro": intro, "body": body, "boxes": boxes}


def is_program(program: dict[str, Any]) -> bool:
    return any(b["label"].lower() == ELIGIBILITY_LABEL for b in program.get("boxes", []))


def eligibility_lines(program: dict[str, Any]) -> list[str]:
    return [line for b in program.get("boxes", []) if b["label"].lower() == ELIGIBILITY_LABEL for line in b["lines"]]


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """Crawl the three sections to depth three, each page once; a page with an Eligibility box is a record."""
    prior = prior or {}
    records: list[RawRecord] = []
    queue: deque[tuple[str, int]] = deque((s, 0) for s in SECTIONS)
    seen: set[str] = set(SECTIONS)
    with _client() as client:
        while queue:
            path, depth = queue.popleft()
            slug = path.strip("/")
            try:
                if depth:
                    time.sleep(DELAY_S)
                page_html = _get(client, BASE + path)
            except httpx.HTTPError:
                if depth == 0:
                    raise
                if slug in prior:
                    records.append(RawRecord(source_connector=CONNECTOR, source_id=slug, payload=prior[slug]))
                continue
            program = parse_program(page_html)
            if depth and is_program(program):
                records.append(RawRecord(source_connector=CONNECTOR, source_id=slug,
                                         payload={"path": path, "depth": depth, "program": program}))
                if limit and len(records) >= limit:
                    break
            if depth < MAX_DEPTH:
                for child in parse_teasers(page_html):
                    if child not in seen:
                        seen.add(child)
                        queue.append((child, depth + 1))
    return records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A page the menus no longer reach: not a closure the agency stated, and the page has no status to read back."""
    return {"status": "unknown"}


# ---------- normalize ----------

def cycle_sentence(program: dict[str, Any]) -> str | None:
    """The first sentence anywhere on the page that states a deadline, an application period or a closed round."""
    lines = program.get("intro", []) + program.get("body", []) + [line for b in program.get("boxes", []) for line in b["lines"]]
    for line in lines:
        for s in sentences(line):
            if CYCLE_RE.search(s):
                return s
    return None


def cycle_dates(sentence: str | None) -> tuple[date | None, date | None]:
    """(opens_at, closes_at) from the full dates in the cycle sentence: a `from ... to` range gives both, a due
    phrase gives the close alone."""
    if not sentence:
        return None, None
    dates = [parse_date(re.sub(r"(\d)(?:st|nd|rd|th)", r"\1", m)) for m in FULL_DATE_RE.findall(sentence)]
    dates = [d for d in dates if d]
    if not dates:
        return None, None
    if RANGE_RE.search(sentence) and len(dates) >= 2:
        return dates[0], dates[-1]
    if DUE_RE.search(sentence):
        return None, dates[-1]
    return None, None


def status_for(sentence: str | None, closes_at: date | None, today: date) -> str:
    if sentence and CLOSED_RE.search(sentence):
        return "closed"
    if closes_at and closes_at >= today:
        return "open"
    return "unknown"


def applicant_tags(lines: list[str]) -> list[ApplicantTag]:
    kept = [s for line in lines for s in sentences(line) if not NEGATION_RE.search(s)]
    return applicant_types_for(kept or None)


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    program = raw.payload["program"]
    today = today or date.today()
    name = clean(program.get("title", "")) or raw.source_id
    sentence = cycle_sentence(program)
    opens_at, closes_at = cycle_dates(sentence)
    elig = eligibility_lines(program)
    labels = [b["label"] for b in program.get("boxes", []) if b["label"]]
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=BASE + raw.payload.get("path", "/" + raw.source_id),
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(name),
        funding_source="direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status=status_for(sentence, closes_at, today),
        opens_at=opens_at,
        closes_at=closes_at,
        closes_at_text=sentence,
        rolling=True if sentence and ROLLING_RE.search(sentence) else None,
        summary=program["intro"][0] if program.get("intro") else None,
        eligibility_text="\n".join(elig) or None,
        eligibility_structured={"boxes": labels} if labels else None,
        applicant_types=applicant_tags(elig),
        categories=[],
        alns=[],
    )
