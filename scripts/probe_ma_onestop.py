"""One-off probe for the Massachusetts One Stop connector: read the index, the nine mass.gov program pages and the
MassDevelopment grant-programs page once, save them as fixtures, and print what the connector sees on each.
  uv run python scripts/probe_ma_onestop.py
Writes tests/fixtures/ma_onestop/index.html, <source_id>.html per mass.gov program and massdev.html, with scripts,
SVG, contact cards, press teasers and the feedback form removed and e-mail addresses replaced."""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urldefrag

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import ma_onestop as ma  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ma_onestop"
GONE = "script, style, svg, noscript, iframe, header, footer, nav, .ma__contact-us, .ma__contact-list, .ma__contact-group, " \
       ".ma__mass-feedback-form, .ma__press-teaser, .ma__sticky-toc, .ma__link-list, .post-content"


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.select(GONE):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", "contact@example.mass.gov", str(soup))


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with ma._client() as client:
        index_html = ma._get(client, ma.INDEX_URL)
        (FIXTURES / "index.html").write_text(scrub(index_html), encoding="utf-8")
        index = ma.parse_index(index_html)
        print(f"index: {len(index['programs'])} programs; round {index['round']['heading']!r}; dates {ma.round_dates(index['round']['lines'])}")
        shared: dict[str, str] = {}
        for program in index["programs"]:
            plain, fragment = urldefrag(program["url"])
            if plain not in shared:
                time.sleep(ma.DELAY_S)
                shared[plain] = ma._get(client, plain)
                name = "massdev" if fragment else program["source_id"]
                (FIXTURES / f"{name}.html").write_text(scrub(shared[plain]), encoding="utf-8")
            page = ma.parse_page(shared[plain], fragment or None)
            raw = RawRecord(source_connector=ma.CONNECTOR, source_id=program["source_id"], payload={"program": program, "round": index["round"], "page": page})
            p = ma.normalize(raw, date.today())
            print(f"{p.source_id:48} {p.agency_code} | {p.status} | {[t.value for t in p.applicant_types]} | blocks={len(page['blocks'])}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
