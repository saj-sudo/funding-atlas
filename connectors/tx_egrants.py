"""Texas Office of the Governor eGrants connector: the funding announcements the office lists publicly.

Source: https://egrants.gov.texas.gov. `/fundingopp` ("Active Opportunities", 4 cards on 2026-10-28) and the archive
(`/fundingopp/archive`, then `/archive/P25`, `/P50`, ...: 25 cards a page, 143 cards) share one server-rendered card
markup: name, Available and Due dates, Purpose, Eligible Organizations (free text) and Total Funds. A round's own page
holds none of that to a plain GET, so only the cards are read. About 7 requests a run.

The Active page lists a round eight months past its due date, so status comes from the card's dates, never from which
page lists it. Applicants come from the Eligible Organizations text, sentence by sentence. See
docs/connectors/tx_egrants.md.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for, funding_type_for
from pipeline.models import ApplicantTag, Program, RawRecord

CONNECTOR = "tx_egrants"
BASE = "https://egrants.gov.texas.gov"
ACTIVE_URL = BASE + "/fundingopp"
ARCHIVE_URL = BASE + "/fundingopp/archive"
PAGE_SIZE = 25
MAX_ARCHIVE_PAGES = 20
AGENCY = "Office of the Governor"
JURISDICTION = "TX"
DELAY_S = 0.3
TIMEOUT_S = 30.0
TRIES = 3
RETRY_WAIT_S = 1.5
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"
INVITATION_ONLY = "invitation only"


# ---------- HTTP ----------

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def _get(client: httpx.Client, url: str) -> str:
    """The page text. A dropped connection is retried; an HTTP error status is not."""
    for attempt in range(TRIES):
        try:
            resp = client.get(url)
        except httpx.TransportError:
            if attempt == TRIES - 1:
                raise
            time.sleep(RETRY_WAIT_S)
            continue
        resp.raise_for_status()
        return resp.text
    raise AssertionError("unreachable")


def archive_url(page: int) -> str:
    """Archive page 0 is `/archive`; page n is `/archive/P<25n>`."""
    return ARCHIVE_URL if page == 0 else f"{ARCHIVE_URL}/P{PAGE_SIZE * page}"


# ---------- parsing (no I/O) ----------

def _paragraphs(block: Tag | None) -> list[str]:
    if block is None:
        return []
    detail = block.select_one(".opp-detail")
    if detail is None:
        return []
    paragraphs = [clean(p.get_text(" ")) for p in detail.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    return paragraphs or ([clean(detail.get_text(" "))] if clean(detail.get_text(" ")) else [])


def parse_cards(page_html: str) -> list[dict[str, Any]]:
    """One dict per card: slug, name, available, due, purpose and eligible (lists of paragraphs), total_funds."""
    soup = BeautifulSoup(page_html, "html.parser")
    cards: list[dict[str, Any]] = []
    for card in soup.select("div.opp-list-item"):
        slug = card.get("id")
        title = card.select_one(".opp-title")
        if not slug or title is None:
            continue
        dates = {clean(box.select_one(".opp-date-name").get_text(" ")).lower(): clean(box.select_one(".opp-date").get_text(" "))
                 for box in card.select(".opp-date-box") if box.select_one(".opp-date-name") and box.select_one(".opp-date")}
        blocks = {clean(b.select_one(".opp-label").get_text(" ")).rstrip(":").lower(): b
                  for b in card.select(".opp-list-details") if b.select_one(".opp-label")}
        total = card.select_one(".total-value")
        cards.append({
            "slug": str(slug), "name": clean(title.get_text(" ")),
            "available": dates.get("available", ""), "due": dates.get("due date", ""),
            "purpose": _paragraphs(blocks.get("purpose")),
            "eligible": _paragraphs(blocks.get("eligible organizations")),
            "total_funds": clean(total.get_text(" ")) if total else "",
        })
    return cards


# ---------- fetch ----------

def fetch(limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
    """The Active page, then archive pages until one has no cards. Any page that cannot be read aborts the run (every
    archived round would otherwise look missing); an archive longer than the cap aborts it too, loudly."""
    found: list[tuple[str, dict[str, Any]]] = []
    with _client() as client:
        found += [("active", c) for c in parse_cards(_get(client, ACTIVE_URL))]
        for page in range(MAX_ARCHIVE_PAGES):
            time.sleep(DELAY_S)
            cards = parse_cards(_get(client, archive_url(page)))
            if not cards:
                break
            found += [("archive", c) for c in cards]
        else:
            raise RuntimeError(f"the archive has more than {MAX_ARCHIVE_PAGES} pages; raise MAX_ARCHIVE_PAGES")
    records: dict[str, RawRecord] = {}
    for listed, card in found:
        records.setdefault(card["slug"], RawRecord(source_connector=CONNECTOR, source_id=card["slug"],
                                                   payload={"listed": listed, "card": card}))
    out = list(records.values())
    return out[:limit] if limit else out


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A round on neither list. Rounds move to the archive rather than disappear, so this was taken down, which the
    source does not state as a closure; and a round's own page holds nothing to read back: unknown."""
    return {"status": "unknown"}


# ---------- normalize ----------

def status_for(available: date | None, due: date | None, today: date) -> str:
    if available and available > today:
        return "forecasted"
    if due and due < today:
        return "closed"
    return "open"


def applicant_tags(paragraphs: list[str]) -> list[ApplicantTag]:
    """Tags from the sentences that do not negate: "Volunteer Fire Departments are not eligible" tags nothing."""
    lines = [s for p in paragraphs for s in sentences(p) if not NEGATION_RE.search(s)]
    return applicant_types_for(lines or None)


def closes_text_for(card: dict[str, Any]) -> str | None:
    """A date cell that is not a date, verbatim (none seen)."""
    parts = []
    if card["due"] and not parse_date(card["due"]):
        parts.append(f"Due date: {card['due']}")
    if card["available"] and not parse_date(card["available"]):
        parts.append(f"Available: {card['available']}")
    return "; ".join(parts) or None


def structured_for(card: dict[str, Any]) -> dict[str, Any] | None:
    out: dict[str, Any] = {}
    if card["total_funds"].strip("$ "):
        out["total_funds"] = card["total_funds"]
    if card["eligible"] and card["eligible"][0].lower().startswith(INVITATION_ONLY):
        out["invitation_only"] = True
    return out or None


def normalize(raw: RawRecord, today: date | None = None) -> Program:
    card = raw.payload["card"]
    today = today or date.today()
    available, due = parse_date(card["available"]), parse_date(card["due"])
    return Program(
        source_connector=CONNECTOR,
        source_id=raw.source_id,
        source_url=f"{BASE}/fundingopp/page/{card['slug']}",
        external_number=None,
        name=card["name"],
        level="state",
        jurisdiction=JURISDICTION,
        administering_agency=AGENCY,
        agency_code=None,
        funding_type=funding_type_for(card["name"]),
        funding_source="direct",
        amount_min=None,
        amount_max=None,
        match_required=None,
        match_pct=None,
        status=status_for(available, due, today),
        opens_at=available,
        closes_at=due,
        closes_at_text=closes_text_for(card),
        rolling=None,
        summary=card["purpose"][0] if card["purpose"] else None,
        eligibility_text="\n".join(card["eligible"]) or None,
        eligibility_structured=structured_for(card),
        applicant_types=applicant_tags(card["eligible"]),
        categories=[],
        alns=[],
    )
