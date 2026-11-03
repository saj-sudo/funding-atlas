"""One-off probe for the Virginia DHCD connector: crawl the site once with the connector's own functions, save the
pages the tests need as fixtures, and print what the connector sees on every program page.
  uv run python scripts/probe_va_dhcd.py
Writes tests/fixtures/va_dhcd/: communities.html (a section), downtown-revitalization.html (a landing),
cdbg-downtown-revitalization.html (a CDBG family page with "Learn More"), and program pages irf, vaarc,
cdbg-community-improvement-grants, cdbg-planning-grants, vez, vida, plus vhsp (templated, not a program). Scripts are
removed and the contact block's people replaced by placeholders on every page."""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import va_dhcd as va  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "va_dhcd"
KEEP = ("/communities", "/downtown-revitalization", "/cdbg-downtown-revitalization", "/irf", "/vaarc",
        "/cdbg-community-improvement-grants", "/cdbg-planning-grants", "/vez", "/vida", "/vhsp")


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.find_all("script"):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for user in soup.select("div.programcontact div.user"):
        for cls, text in (("name", "Contact Name"), ("phone", "000-000-0000")):
            for el in user.select(f"div.{cls}"):
                el.string = text
        for a in user.select("div.email a"):
            a["href"] = "mailto:contact@example.virginia.gov"
            a.string = "contact@example.virginia.gov"
    return str(soup)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with va._client() as client:
        for path in KEEP:
            time.sleep(va.DELAY_S)
            page = va._get(client, va.BASE + path)
            (FIXTURES / f"{path.strip('/')}.html").write_text(scrub(page), encoding="utf-8")
            program = va.parse_program(page)
            kind = "program" if va.is_program(program) else ("landing" if va.parse_teasers(page) else "page")
            print(f"{path:38} {kind:8} teasers={len(va.parse_teasers(page))} boxes={[b['label'] for b in program['boxes']]}")
            if va.is_program(program):
                p = va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id=path.strip("/"),
                                           payload={"path": path, "depth": 2, "program": program}), date.today())
                print(f"    {p.name[:50]!r} | {p.status} {p.opens_at} -> {p.closes_at} | {[t.value for t in p.applicant_types]} | {(p.closes_at_text or '')[:90]!r}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
