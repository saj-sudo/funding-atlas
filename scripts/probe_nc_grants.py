"""One-off probe for the North Carolina seed list: read nc.gov's grant table once, save it as the fixture, and print
what the connector sees.
  uv run python scripts/probe_nc_grants.py
Writes tests/fixtures/nc_grants/index.html with scripts, SVG and menus removed."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import nc_grants as nc  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "nc_grants"
GONE = "script, style, svg, noscript, iframe, link, meta, header, footer, nav, form"


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.select(GONE):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return str(soup)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with nc._client() as client:
        html = nc._get(client, nc.INDEX_URL)
    (FIXTURES / "index.html").write_text(scrub(html), encoding="utf-8")
    rows = nc.parse_index(html)
    print(f"{len(rows)} programs")
    for r in rows:
        p = nc.normalize(nc.RawRecord(source_connector=nc.CONNECTOR, source_id=r["source_id"], payload=r), date.today())
        print(f"{p.source_id[:50]:50} {p.agency_code:14} {str(p.funding_type):6} {[c.value for c in p.categories]} {r['categories']}")


if __name__ == "__main__":
    main()
