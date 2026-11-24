"""One-off probe for Florida: read the Department of State's grant table and every page in `fl_dep.PAGES` once, save them
as fixtures, and print what the connectors see (one line per record, a page that holds several programs prints each).
  uv run python scripts/probe_florida.py [fl_dos] [fl_dep]
Writes tests/fixtures/<connector>/<slug>.html with scripts, styles, menus and the page chrome removed."""

from __future__ import annotations

import importlib
import re
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import hand_list as hl  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
GONE = "script, style, svg, noscript, iframe, link, meta, header, footer, nav, form, input"
ALL = ["fl_dos", "fl_dep"]
CONTACTS_RE = re.compile(r"^(?:program )?contacts?(?: us)?$", re.I)
PERSONAL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\(?\b\d{3}\)?[-. ]\d{3}[-.]\d{4}\b")


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.select(GONE):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    # a "Contacts" heading and everything after it in its block (staff names, phones), every mail link, every image
    for h in soup.find_all(["h2", "h3", "h4", "h5"]):
        if h.parent is not None and CONTACTS_RE.match(h.get_text(" ", strip=True)):
            for sib in list(h.find_next_siblings()):
                sib.decompose()
            h.decompose()
    for a in soup.select('a[href^="mailto:"], img'):
        a.decompose()
    return PERSONAL_RE.sub("", str(soup))


def line(p) -> str:
    return (f"  {p.source_id:42} {p.status:10} open={p.opens_at} close={p.closes_at} {p.funding_source:12} "
            f"{[t.value for t in p.applicant_types]} | {(p.closes_at_text or '')[:80]}")


def main(names: list[str]) -> None:
    today = date.today()
    with hl.client() as client:
        for name in names:
            mod = importlib.import_module(f"connectors.{name}")
            out = ROOT / name
            out.mkdir(parents=True, exist_ok=True)
            print(f"== {name}")
            if hasattr(mod, "LIST_URL"):   # a table: one page, one record per kept row
                html = hl.get(client, mod.LIST_URL)
                (out / "program.html").write_text(scrub(html), encoding="utf-8")
                for row in mod.parse_rows(html):
                    if mod.kept(row):
                        print(line(mod.normalize(RawRecord(source_connector=name, source_id=mod.slug(row["name"]), payload=row), today)))
                continue
            for slug, path in mod.PAGES.items():
                time.sleep(max(1.5, getattr(mod.SITE, "DELAY_S", 0)))
                html = hl.get(client, mod.BASE + path)
                (out / f"{slug}.html").write_text(scrub(html), encoding="utf-8")
                page = mod.SITE.parse_page(html)
                for sid, payload in mod.SITE.records_for(slug, path, [page], 0):
                    print(line(mod.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today)))


if __name__ == "__main__":
    main(sys.argv[1:] or ALL)
