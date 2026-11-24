"""One-off probe for South Carolina (Commerce, the Rural Infrastructure Authority): read every page in each module's
`PAGES` once, save them as fixtures, and print what the connectors see (one line per record; a page that holds several
programs prints each).
  uv run python scripts/probe_south_carolina.py [sc_commerce sc_ria]
Writes tests/fixtures/<connector>/<slug>.html (a slug read from two pages: `<slug>.html` and `<slug>.2.html`) with scripts,
styles, menus and the page chrome removed, and every line that carries a phone number or an e-mail address taken out."""

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
GONE = "script, style, svg, noscript, iframe, link, meta, header, footer, nav, form"
LEAVES = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "address", "span", "a", "div"]
BLOCKS = ["p", "li", "ul", "ol", "div", "table", "section", "h1", "h2", "h3", "h4", "h5", "h6"]
CONTACT_RE = re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|[\w.]+@[\w-]+\s*\.\w+|\[email\s*protected\]|\bPO Box\b", re.I)
ALL = ["sc_commerce", "sc_ria"]


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.select(GONE):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in soup.find_all(LEAVES):   # contact lines: the connector drops them, the fixture does not keep them
        if not tag.decomposed and not tag.find(BLOCKS) and CONTACT_RE.search(" ".join(tag.get_text(" ").split())):
            tag.decompose()
    for tag in soup.select("a[href^='mailto:'], a[href^='tel:']"):
        tag.decompose()
    return str(soup)


def fixture(slug: str, n: int) -> str:
    return f"{slug}.html" if n == 0 else f"{slug}.{n + 1}.html"


def main(names: list[str]) -> None:
    today = date.today()
    with hl.client() as client:
        for name in names:
            mod = importlib.import_module(f"connectors.{name}")
            out = ROOT / name
            out.mkdir(parents=True, exist_ok=True)
            print(f"== {name}")
            for slug, spec in mod.PAGES.items():
                pages = []
                for n, url in enumerate(mod.SITE.urls_for(slug, spec)):
                    time.sleep(max(3.0, getattr(mod.SITE, "DELAY_S", 0)))
                    html = scrub(hl.get(client, url))
                    (out / fixture(slug, n)).write_text(html, encoding="utf-8")
                    pages.append(mod.SITE.parse_page(html))
                for sid, payload in mod.SITE.records_for(slug, spec, pages, 0):
                    p = mod.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today)
                    print(f"  {sid:30} {p.status:10} open={p.opens_at} close={p.closes_at} rolling={p.rolling} {p.funding_source:12} "
                          f"{sorted({t.value for t in p.applicant_types})} | {(p.closes_at_text or '')[:90]}")


if __name__ == "__main__":
    main(sys.argv[1:] or ALL)
