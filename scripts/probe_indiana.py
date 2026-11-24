"""One-off probe for Indiana's OCRA and INDOT: read every page in each module's `PAGES` once, save them as fixtures, and
print what the connectors see (one line per record, a page that holds several programs prints each).
  uv run python scripts/probe_indiana.py [in_ocra] [in_indot]
Writes tests/fixtures/<connector>/<slug>.html with scripts, styles, menus and the page chrome removed, and with every
contact removed: an accordion body that names a contact is emptied, a line with an address or a phone number is cut."""

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
GONE = "script, style, svg, noscript, iframe, link, meta, header, footer, nav"
ALL = ["in_ocra", "in_indot"]
CONTACT_RE = re.compile(r"[\w.-]+@[\w-]+\.[\w.-]+|\(?\b\d{3}\)?[ -]?\d{3}-\d{4}\b")


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.select(GONE):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for body in soup.select(".accordion-body"):
        if body.select_one("a[href^=mailto]") or CONTACT_RE.search(body.get_text(" ")):
            body.clear()
    for line in soup.find_all(["p", "li"]):
        if not line.find(["p", "li"]) and CONTACT_RE.search(line.get_text(" ")):
            line.decompose()
    for a in soup.select("a[href^=mailto]"):
        a.decompose()
    for a in soup.select('a[href*="/dA/"], a[href*="/files/"]'):   # document links; some file names carry a person's name
        a["href"] = "#"
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
                time.sleep(max(1.5, getattr(mod.SITE, "DELAY_S", 0)))
                html = hl.get(client, mod.BASE + path)
                (out / f"{slug}.html").write_text(scrub(html), encoding="utf-8")
                page = mod.SITE.parse_page(html)
                for sid, payload in mod.SITE.records_for(slug, path, [page], 0):
                    p = mod.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today)
                    print(f"  {sid:42} {p.status:10} open={p.opens_at} close={p.closes_at} {p.funding_source:12} "
                          f"{[t.value for t in p.applicant_types]} | {(p.closes_at_text or '')[:80]}")


if __name__ == "__main__":
    main(sys.argv[1:] or ALL)
