"""One-off probe for the Virginia VDOT connector: read the Local Assistance index and its program pages once, save
them as fixtures, and print what the connector sees on each.
  uv run python scripts/probe_va_vdot.py
Writes tests/fixtures/va_vdot/index.html and <slug>.html with scripts and Contact blocks removed."""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import va_vdot as va  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "va_vdot"


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.find_all("script"):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for h in soup.find_all(["h2", "h3"]):
        if va.CONTACT_RE.match(h.get_text(" ", strip=True)):
            for sib in list(h.find_next_siblings()):
                sib.decompose()
            h.decompose()
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", "contact@example.virginia.gov", str(soup))


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with va._client() as client:
        index = va._get(client, va.INDEX_URL)
        (FIXTURES / "index.html").write_text(scrub(index), encoding="utf-8")
        cards = va.parse_cards(index)
        print(f"index: {len(cards)} program cards")
        for card in cards:
            time.sleep(va.DELAY_S)
            html = va._get(client, card["url"])
            (FIXTURES / f"{card['slug']}.html").write_text(scrub(html), encoding="utf-8")
            page = va.parse_page(html)
            p = va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id=card["slug"], payload={"card": card, "page": page}), date.today())
            print(f"{card['slug']:30} {p.name[:40]!r} | {p.status} | {[t.value for t in p.applicant_types]} | cycle={p.closes_at_text!r}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
