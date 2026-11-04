"""One-off probe for Vermont's four agencies: read every page in each module's `PAGES` once, save them as fixtures, and
print what the connectors see.
  uv run python scripts/probe_vermont.py [vt_accd vt_vtrans vt_fpr vt_vem]
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
GONE = "script, style, svg, noscript, iframe, link, meta, header, footer, nav, form, .layout-sidebar-first, .layout-sidebar-second"
ALL = ["vt_accd", "vt_vtrans", "vt_fpr", "vt_vem"]


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
                time.sleep(hl.DELAY_S * 2)
                html = hl.get(client, mod.BASE + path)
                (out / f"{slug}.html").write_text(scrub(html), encoding="utf-8")
                raw = RawRecord(source_connector=name, source_id=slug, payload={"path": path, "page": mod.SITE.parse_page(html)})
                p = mod.normalize(raw, today)
                print(f"  {slug:30} {p.status:10} open={p.opens_at} close={p.closes_at} {p.funding_source:12} "
                      f"{[t.value for t in p.applicant_types]} | {(p.closes_at_text or '')[:90]}")


if __name__ == "__main__":
    main(sys.argv[1:] or ALL)
