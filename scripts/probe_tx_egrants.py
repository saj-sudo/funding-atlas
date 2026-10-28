"""One-off probe for the Texas eGrants connector: read the Active page and the first archive pages once, keep the
cards the tests need, save the trimmed pages as fixtures, and print what the connector sees on each.
  uv run python scripts/probe_tx_egrants.py
Writes tests/fixtures/tx_egrants/: active.html, archive_0.html, archive_1.html (archive page 25), archive_end.html
(a page past the end, no cards). Scripts and hidden form inputs (the CSRF token) are removed from every page."""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import tx_egrants as tx  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "tx_egrants"

# archive page -> [(why, predicate on a parsed card)]; the first card satisfying each predicate is kept.
WANTED = {
    0: (
        ("eligible text with no <p> (a bare block)", lambda c, raw: bare_eligible(raw)),
        ("a bare $ in Total Funds, and a negated sentence", lambda c, raw: c["total_funds"].strip() == "$"),
        ("N Million and units of local government", lambda c, raw: re.fullmatch(r"\$[\d.]+ Million", c["total_funds"]) and any("units of local government" in p for p in c["eligible"])),
        ("Invitation Only", lambda c, raw: bool(c["eligible"]) and c["eligible"][0].lower().startswith("invitation only")),
    ),
    1: (
        ("units of local government", lambda c, raw: any("units of local government" in p for p in c["eligible"])),
        ("N Million", lambda c, raw: re.fullmatch(r"\$[\d.]+ Million", c["total_funds"])),
    ),
}


def bare_eligible(raw: str) -> bool:
    """True when the card's Eligible Organizations block holds its text outside any <p>."""
    for block in BeautifulSoup(raw, "html.parser").select(".opp-list-details"):
        if block.select_one(".opp-label").get_text(strip=True).startswith("Eligible"):
            return not block.select(".opp-detail p") and bool(block.select_one(".opp-detail").get_text(strip=True))
    return False


def scrub(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["script"]):
        tag.decompose()
    for tag in soup.find_all("input", attrs={"type": "hidden"}):
        tag.decompose()


def trim(page_html: str, keep: set[str]) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for card in soup.select("div.opp-list-item"):
        if card.get("id") not in keep:
            card.decompose()
    scrub(soup)
    return str(soup)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    pages: dict[str, str] = {}
    with tx._client() as client:
        active = tx._get(client, tx.ACTIVE_URL)
        pages["active.html"] = trim(active, {c["slug"] for c in tx.parse_cards(active)})
        print(f"active: {len(tx.parse_cards(active))} cards")
        for page, wanted in WANTED.items():
            time.sleep(tx.DELAY_S)
            html = tx._get(client, tx.archive_url(page))
            soup = BeautifulSoup(html, "html.parser")
            raws = {c.get("id"): str(c) for c in soup.select("div.opp-list-item")}
            cards = tx.parse_cards(html)
            keep: set[str] = set()
            for why, pred in wanted:
                hit = next((c for c in cards if c["slug"] not in keep and pred(c, raws[c["slug"]])), None)
                print(f"archive {page}: {why}: {hit['slug'] if hit else None}")
                if hit:
                    keep.add(hit["slug"])
            pages[f"archive_{page}.html"] = trim(html, keep)
        time.sleep(tx.DELAY_S)
        end = tx._get(client, tx.archive_url(len(WANTED) + 4))
        assert not tx.parse_cards(end), "expected a page past the end"
        pages["archive_end.html"] = trim(end, set())
    for name, html in pages.items():
        (FIXTURES / name).write_text(html, encoding="utf-8")
    for name in ("active.html", "archive_0.html", "archive_1.html"):
        for c in tx.parse_cards(pages[name]):
            p = tx.normalize(RawRecord(source_connector=tx.CONNECTOR, source_id=c["slug"], payload={"listed": name, "card": c}), date.today())
            print(f"{name[:9]:9} {c['slug'][:40]:40} | {p.status} {p.opens_at} -> {p.closes_at} | {c['total_funds']!r:.22} | {p.eligibility_structured}"
                  f" | {sorted({t.value for t in p.applicant_types})}")


if __name__ == "__main__":
    main()
