"""One-off probe for the Business Oregon connector: read the Programs index and a sample of program pages once, save
them as fixtures, and print what the connector sees on each.
  uv run python scripts/probe_or_biz.py           # the sample below
  uv run python scripts/probe_or_biz.py --all     # every program (about a hundred GETs), fixtures for the sample only
Writes tests/fixtures/or_biz/index.html and <source_id with / as __>.html with scripts, SVG, menus and the sidebar
field removed and e-mail addresses replaced."""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import or_biz as ob  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "or_biz"
SAMPLE = [
    "programs/cdbg", "programs/levee", "programs/county_fairgrounds_grants", "programs/bep", "programs/brownfields",
    "programs/srf", "programs/cgf", "programs/aggiebond", "programs/hisf", "programs/bdp", "programs/sbma", "programs/rsia",
    "aboutus/artscommission/grants/for-organizations/arts-build-communities",
]
GONE = "script, style, svg, noscript, iframe, link, meta, input, select, textarea, header, footer, nav, #s4-ribbonrow, #ms-designer-ribbon, #suiteBar, .ms-core-navigation, " \
       "#DeltaTopNavigation, #sideNavBox, .oregon-footer, #disqus_thread"


def scrub(page_html: str, keep_sidebar: bool = False) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.select(GONE):
        tag.decompose()
    if not keep_sidebar:
        for field in soup.select(".ms-rtestate-field"):
            if (field.get("id") or "").endswith("RichHtmlField12__ControlWrapper_OregonRichHtmlField"):
                field.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", "contact@example.oregon.gov", str(soup))


def main(everything: bool) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with ob._client() as client:
        index_html = ob._get(client, ob.INDEX_URL)
        (FIXTURES / "index.html").write_text(scrub(index_html, keep_sidebar=True), encoding="utf-8")
        programs = ob.parse_index(index_html)
        by_id = {p["source_id"]: p for p in programs}
        print(f"index: {len(programs)} programs, {sum(1 for p in programs if p['topic'])} with a topic")
        for sid in (list(by_id) if everything else SAMPLE):
            program = by_id[sid]
            time.sleep(ob.DELAY_S)
            html = ob._get(client, program["url"])
            if sid in SAMPLE:
                (FIXTURES / f"{sid.replace('/', '__')}.html").write_text(scrub(html), encoding="utf-8")
            page = ob.parse_page(html)
            p = ob.normalize(RawRecord(source_connector=ob.CONNECTOR, source_id=sid, payload={"program": program, "page": page}), date.today())
            print(f"{sid[:50]:50} {p.status:8} rolling={p.rolling} | {[t.value for t in p.applicant_types]} | {p.closes_at_text!r:.80}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main("--all" in sys.argv[1:])
