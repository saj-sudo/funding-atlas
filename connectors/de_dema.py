"""Delaware Emergency Management Agency connector: the FEMA pass-throughs the agency administers.

Source: https://dema.delaware.gov/about/grants/ and its preparedness tab (`?dc=preparednessgrants`). The grants page
lists ten programs as bold links with a blurb under "Preparedness Grants" and "Recovery Assistance"; the tab adds an
"Eligible Subrecipient" paragraph and an "Apply" paragraph for the four preparedness programs. No dates anywhere:
every record is unknown. Two GETs a run. See docs/connectors/de_dema.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Comment

from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for, portal_categories
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

CONNECTOR = "de_dema"
BASE = "https://dema.delaware.gov"
GRANTS_URL = BASE + "/about/grants/"
PREP_URL = BASE + "/about/grants/index.shtml?dc=preparednessgrants"
AGENCY = "Delaware Emergency Management Agency"
AGENCY_CODE = "DE-DEMA"
JURISDICTION = "DE"
DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"
SECTION_HEADINGS = ("Preparedness Grants", "Recovery Assistance")


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


def _soup(page_html: str) -> BeautifulSoup:
    soup = BeautifulSoup(page_html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return soup


def entry_id(url: str) -> str:
    parts = urlparse(url)
    if parts.fragment:
        return parts.fragment
    return parts.path.rstrip("/").rsplit("/", 1)[-1]


def parse_entries(grants_html: str) -> list[dict[str, str]]:
    """The accordion entries: id, section, name, url, blurb, in page order."""
    soup = _soup(grants_html)
    out: list[dict[str, str]] = []
    for h2 in soup.find_all("h2"):
        section = clean(h2.get_text(" "))
        if section not in SECTION_HEADINGS:
            continue
        box = h2.find_next_sibling("div")
        if box is None:
            continue
        for p in box.find_all("p"):
            link = p.find("a", href=True)
            if link is None or p.find("strong") is None or link.find_parent("strong") is None:
                continue
            name = clean(link.get_text(" "))
            blurb = clean(p.get_text(" ")).replace(name, "", 1).strip()
            url = urljoin(GRANTS_URL, link["href"])
            out.append({"id": entry_id(url), "section": section, "name": name, "url": url, "blurb": blurb})
    return out


def parse_preparedness(prep_html: str) -> dict[str, dict[str, str]]:
    """anchor id -> {eligible, projects, apply} from the preparedness tab's blocks."""
    soup = _soup(prep_html)
    out: dict[str, dict[str, str]] = {}
    for button in soup.find_all("button", id=re.compile(r"^[A-Z]{3,6}$")):
        block = button.find_next_sibling("div")        # the accordion content follows the labelled button
        if block is None:
            continue
        fields: dict[str, str] = {}
        current = None
        for el in block.find_all(["h5", "p"]):
            text = clean(el.get_text(" "))
            if not text:
                continue
            low = text.lower()
            if el.name == "h5":
                current = ("eligible" if "subrecipient" in low or "eligible applicant" in low else
                           "projects" if "eligible project" in low else "apply" if low.startswith("apply") else None)
                continue
            if current and el.find("a", class_="btn") is None:
                fields[current] = (fields.get(current, "") + " " + text).strip()
        if fields:
            out[button["id"]] = fields
    return out


def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    with _client() as client:
        entries = parse_entries(_get(client, GRANTS_URL))
        time.sleep(DELAY_S)
        try:
            prep = parse_preparedness(_get(client, PREP_URL))
        except httpx.HTTPError:
            prep = {e["id"]: (prior or {}).get(e["id"], {}).get("details") for e in entries}
    records = [RawRecord(source_connector=CONNECTOR, source_id=e["id"], payload={"entry": e, "details": prep.get(e["id"])})
               for e in entries]
    return records[:limit] if limit else records


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    return {"status": "unknown"}


def applicant_tags(lines: list[str]) -> list[ApplicantTag]:
    kept = [s for line in lines for s in sentences(line) if not NEGATION_RE.search(s)]
    return applicant_types_for(kept or None)


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    entry, details = raw.payload["entry"], raw.payload.get("details") or {}
    name = clean(entry["name"])
    lines = [details["eligible"]] if details.get("eligible") else []
    structured: dict[str, Any] = {}
    if details.get("projects"):
        structured["eligible_projects"] = details["projects"]
    if "invitation only" in (details.get("eligible", "") + " " + details.get("apply", "")).lower():
        structured["invitation_only"] = True
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=entry["url"],
        external_number=None,
        name=name,
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=AGENCY_CODE,
        funding_type=funding_type_for(name) or "grant",
        funding_source="pass_through",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status="unknown",
        opens_at=None,
        closes_at=None,
        closes_at_text=details.get("apply") or None,
        rolling=None,
        summary=entry.get("blurb") or None,
        eligibility_text="\n".join(lines) or None,
        eligibility_structured=structured or None,
        applicant_types=applicant_tags(lines),
        categories=[CategoryTag(value=v, source_code=entry["section"]) for v in portal_categories(entry["section"])],
        alns=[],
    )
