"""Delaware Department of Transportation connector: the two programs with a call for applications from outside the
department, the Transportation Alternatives Program (overview and apply pages) and Safe Routes to School.
Hand-listed; three GETs a run. See docs/connectors/de_deldot.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup, Comment, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for
from pipeline.models import ApplicantTag, Program, RawRecord

CONNECTOR = "de_deldot"
BASE = "https://deldot.gov"
PAGES: dict[str, tuple[str, ...]] = {
    "tap": ("/Programs/tap/", "/Programs/tap/index.shtml?dc=apply"),
    "srts": ("/Programs/srts/index.shtml",),
}
AGENCY = "Department of Transportation"
AGENCY_CODE = "DE-DELDOT"
JURISDICTION = "DE"
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"
TITLE_SUFFIX = " - Delaware Department of Transportation"

LABEL_RE = re.compile(r"sponsors? may include|eligible (?:applicants?|sponsors?)|who (?:may|can) apply", re.I)
APPLICANT_RE = re.compile(r"\b(?:can receive funding|may apply|eligible to apply|eligible entity|project sponsors?)\b", re.I)
CYCLE_RE = re.compile(r"\b(?:deadline|now being accepted|applications? (?:are|will be) (?:accepted|due)|call-?out|now closed|is closed)\b", re.I)
CLOSED_RE = re.compile(r"\b(?:now closed|is closed)\b", re.I)
FEDERAL_RE = re.compile(r"\b(?:Bipartisan Infrastructure Law|Surface Transportation Block Grant|federal(?:ly)? (?:fund\w*|program)|Federal Highway Administration)\b", re.I)
MATCH_RE = re.compile(r"\bup to \d{2,3}% of (?:a|the) project\b|\bmatch(?:ing)? (?:requirement|funds?)\b", re.I)
FULL_DATE_RE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b")
CONTACT_RE = re.compile(r"\b\d{3}[.-]\d{3}[.-]\d{4}\b|@|^contact us$|^toll free", re.I)


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


def _content(soup: BeautifulSoup) -> Tag:
    main = soup.select_one("#main_content") or soup
    for side in main.select("#leftCol, .panel-group, #sidebox"):
        side.decompose()
    return main


def parse_page(page_html: str) -> dict[str, Any]:
    """title (from <title>), blocks [(kind, text)]: label, p, li. Contact lines dropped."""
    soup = BeautifulSoup(page_html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    title = clean(soup.title.get_text(" ")) if soup.title else ""
    title = title[: -len(TITLE_SUFFIX)] if title.endswith(TITLE_SUFFIX) else title
    blocks: list[tuple[str, str]] = []
    for el in _content(soup).find_all(["h2", "h3", "h4", "p", "li"]):
        text = clean(el.get_text(" ")) if el.name != "li" else clean(" ".join(el.find_all(string=True, recursive=False)) or el.get_text(" "))
        if not text or CONTACT_RE.search(text):
            continue
        blocks.append(("label" if el.name in ("h2", "h3", "h4") else el.name, text))
    return {"title": title, "blocks": blocks}


def applicant_lines(blocks: list[tuple[str, str]]) -> list[str]:
    out: list[str] = []
    on = False
    for kind, text in blocks:
        if kind == "label":
            on = bool(LABEL_RE.search(text))
            if on:
                out.append(text)
            continue
        if on and kind == "li":
            out.append(text)
            continue
        on = on and kind == "li"
        for s in sentences(text):
            if APPLICANT_RE.search(s) and s not in out:
                out.append(s)
    return out


def cycle_sentence(blocks: list[tuple[str, str]]) -> str | None:
    for _kind, text in blocks:
        for s in sentences(text):
            if CYCLE_RE.search(s):
                return s
    return None


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    prior = prior or {}
    records: list[RawRecord] = []
    with _client() as client:
        for i, (slug, paths) in enumerate(PAGES.items()):
            if limit and i >= limit:
                break
            pages = []
            try:
                for j, path in enumerate(paths):
                    if i or j:
                        time.sleep(DELAY_S)
                    pages.append(parse_page(_get(client, BASE + path)))
            except httpx.HTTPError:
                if slug in prior:
                    records.append(RawRecord(source_connector=CONNECTOR, source_id=slug, payload=prior[slug]))
                continue
            records.append(RawRecord(source_connector=CONNECTOR, source_id=slug, payload={"paths": list(paths), "pages": pages}))
    return records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    return {"status": "unknown"}


def closes_at_for(sentence: str | None) -> date | None:
    dates = [parse_date(re.sub(r"(\d)(?:st|nd|rd|th)", r"\1", m)) for m in FULL_DATE_RE.findall(sentence or "")]
    dates = [d for d in dates if d]
    return dates[-1] if dates else None


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
    pages = raw.payload["pages"]
    today = today or date.today()
    blocks = [tuple(b) for page in pages for b in page.get("blocks", [])]
    text = " ".join(t for _, t in blocks)
    name = clean(pages[0].get("title", "")) if pages else raw.source_id
    sentence = cycle_sentence(blocks)
    closes_at = closes_at_for(sentence)
    lines = applicant_lines(blocks)
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=BASE + raw.payload["paths"][0],
        external_number=None,
        name=name or raw.source_id,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(name) or "grant",
        funding_source="pass_through" if FEDERAL_RE.search(text) else "direct",
        amount_min=None,
        amount_max=None,
        match_required=True if MATCH_RE.search(text) else None,
        match_pct=None,
        status=status_for(sentence, closes_at, today),
        opens_at=None,
        closes_at=closes_at,
        closes_at_text=sentence,
        rolling=None,
        summary=next((t for k, t in blocks if k == "p"), None),
        eligibility_text="\n".join(lines) or None,
        eligibility_structured=None,
        applicant_types=applicant_tags(lines),
        categories=[],
        alns=[],
    )
