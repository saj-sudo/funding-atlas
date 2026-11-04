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

from connectors.hand_list import (
    DELAY_S,
    applicant_tags,
    resolve_missing,  # noqa: F401  (the pipeline reads it from this module)
)
from connectors.hand_list import client as _client
from connectors.hand_list import get as _get
from connectors.hand_list import soup as _soup
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for, portal_categories
from pipeline.models import CategoryTag, Program, RawRecord

CONNECTOR = "de_dema"
BASE = "https://dema.delaware.gov"
GRANTS_URL = BASE + "/about/grants/"
PREP_URL = BASE + "/about/grants/index.shtml?dc=preparednessgrants"
AGENCY = "Delaware Emergency Management Agency"
AGENCY_CODE = "DE-DEMA"
JURISDICTION = "DE"
SECTION_HEADINGS = ("Preparedness Grants", "Recovery Assistance")


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
