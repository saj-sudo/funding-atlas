"""One-off probe for the Virginia DCR connector: read the six hand-listed pages once, save them as fixtures, and
print what the connector sees on each.
  uv run python scripts/probe_va_dcr.py
Writes tests/fixtures/va_dcr/<slug>.html with scripts, "Questions?" blocks and e-mail addresses removed."""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import va_dcr as va  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "va_dcr"


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.find_all("script"):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for h in soup.find_all(["h2", "h3"]):
        if va.QUESTIONS_RE.match(h.get_text(" ", strip=True)):
            for sib in list(h.find_next_siblings()):
                sib.decompose()
            h.decompose()
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", "contact@example.virginia.gov", str(soup))


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with va._client() as client:
        for slug, path in va.PAGES.items():
            time.sleep(va.DELAY_S)
            html = va._get(client, va.BASE + path)
            (FIXTURES / f"{slug}.html").write_text(scrub(html), encoding="utf-8")
            page = va.parse_page(html)
            p = va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id=slug, payload={"path": path, "page": page}), date.today())
            print(f"{slug:22} {p.name[:45]!r} | {p.status} {p.closes_at} | {p.funding_source} match={p.match_required} | {[t.value for t in p.applicant_types]}")
            print(f"    round: {p.closes_at_text!r}")
            print(f"    elig:  {(p.eligibility_text or '')[:160]!r}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
