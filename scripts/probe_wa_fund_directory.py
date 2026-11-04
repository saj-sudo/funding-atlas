"""One-off probe for the Washington Fund Directory: read the landing page and its six topic pages once, save them as
fixtures, and print what the connector sees.
  uv run python scripts/probe_wa_fund_directory.py
Writes tests/fixtures/wa_fund_directory/index.html and <topic slug>.html with scripts, SVG and menus removed."""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import wa_fund_directory as wa  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "wa_fund_directory"
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
    rows = []
    with wa._client() as client:
        index_html = wa._get(client, wa.INDEX_URL)
        (FIXTURES / "index.html").write_text(scrub(index_html), encoding="utf-8")
        topics = wa.parse_topics(index_html)
        print(f"landing: {len(topics)} topics")
        for topic in topics:
            time.sleep(wa.DELAY_S)
            html = wa._get(client, topic["url"])
            (FIXTURES / f"{topic['url'].rstrip('/').rsplit('/', 1)[-1]}.html").write_text(scrub(html), encoding="utf-8")
            got = wa.parse_topic(html, topic["name"])
            rows += got
            print(f"  {topic['name']:50} {len(got)} rows")
    records = wa.merge(rows)
    print(f"{len(rows)} rows, {len(records)} programs")
    for r in records[:12]:
        p = wa.normalize(RawRecord(source_connector=wa.CONNECTOR, source_id=r["source_id"], payload=r), date.today())
        print(f"{p.source_id[:46]:46} {p.agency_code:8} {str(p.funding_type):6} {[c.value for c in p.categories]} {r['topics']}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
