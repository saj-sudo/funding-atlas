"""One-off probe for Kentucky's DLG Portal: read both opportunity lists and every opportunity page once, save them as
fixtures, and print what the connector sees.
  uv run python scripts/probe_ky_dlg.py
Writes tests/fixtures/ky_dlg/list_<status>.json and <shortname>.html with scripts, styles and menus removed."""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import ky_dlg as ky  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ky_dlg"
GONE = "script, noscript, iframe, link, meta, header, footer, nav, form"


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.select(GONE):
        tag.decompose()
    for style in soup.select("head style"):
        style.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return str(soup)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with ky._client() as client:
        rows = []
        for label in ky.LISTS:
            text = ky._get(client, f"{ky.LIST_URL}?page=1&applicationStatus={label}")
            (FIXTURES / f"list_{label.lower()}.json").write_text(text.strip() + "\n", encoding="utf-8")
            got = ky.parse_list(text)
            print(f"{label}: {len(got['rows'])} rows, more={got['more']}")
            rows += [(label, r) for r in got["rows"]]
        for label, row in rows:
            time.sleep(ky.DELAY_S)
            html = ky._get(client, ky.page_url(row))
            (FIXTURES / f"{row['shortname']}.html").write_text(scrub(html), encoding="utf-8")
            page = ky.parse_page(html)
            p = ky.normalize(RawRecord(source_connector=ky.CONNECTOR, source_id=row["shortname"],
                                       payload={"row": row, "list": label, "page": page}), date.today())
            print(f"  {p.source_id:10} {p.status:6} {sorted(page['sections'])} {[t.value for t in p.applicant_types]} {p.name}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
