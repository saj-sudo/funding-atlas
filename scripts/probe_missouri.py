"""One-off probe for Missouri's agencies: read every page in each module's `PAGES` once, save them as fixtures, and
print what the connectors see (one line per record, a page that holds several programs prints each).
  uv run python scripts/probe_missouri.py [mo_ded mo_dnr mo_modot mo_sema]
Writes tests/fixtures/<connector>/<slug>.html with scripts, styles, menus and the page chrome removed."""

from __future__ import annotations

import importlib
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import hand_list as hl  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
GONE = "script, style, svg, noscript, iframe, link, meta, header, footer, nav"
ALL = ["mo_ded", "mo_dnr", "mo_modot", "mo_sema"]


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.select(GONE):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return str(soup)


def main(names: list[str]) -> None:
    today = date.today()
    with hl.client() as client:
        for name in names:
            mod = importlib.import_module(f"connectors.{name}")
            out = ROOT / name
            out.mkdir(parents=True, exist_ok=True)
            print(f"== {name}")
            for slug, path in mod.PAGES.items():
                time.sleep(1.5)
                html = hl.get(client, mod.BASE + path)
                (out / f"{slug}.html").write_text(scrub(html), encoding="utf-8")
                page = mod.SITE.parse_page(html)
                for sid, payload in mod.SITE.records_for(slug, path, [page], 0):
                    p = mod.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today)
                    print(f"  {sid:42} {p.status:10} open={p.opens_at} close={p.closes_at} {p.funding_source:12} "
                          f"{[t.value for t in p.applicant_types]} | {(p.closes_at_text or '')[:80]}")


if __name__ == "__main__":
    main(sys.argv[1:] or ALL)
