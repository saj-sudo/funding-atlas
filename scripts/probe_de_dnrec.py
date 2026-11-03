"""One-off probe for the Delaware dnrec connector: read the live pages once with the connector's own functions, save
them as fixtures (scripts, comments and contact details removed) and print what the connector sees.
  uv run python scripts/probe_de_dnrec.py"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import de_dnrec as de  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "de_dnrec"


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.find_all("script"):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", "contact@example.delaware.gov", str(soup))
    return re.sub(r"\b\d{3}[.-]\d{3}[.-]\d{4}\b", "000-000-0000", text)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with de._client() as client:
        for slug in de.PAGES:
            html = de._get(client, f"{de.BASE}{slug}/")
            (FIXTURES / f"{slug}.html").write_text(scrub(html), encoding="utf-8")
            p = de.normalize(RawRecord(source_connector=de.CONNECTOR, source_id=slug, payload={"page": de.parse_page(html)}), date.today())
            print(f"{slug:36} {p.status:8} {p.funding_type} rolling={p.rolling} match={p.match_required} | {sorted({t.value for t in p.applicant_types})} | {[c.value for c in p.categories]}")
            print(f"    cycle: {p.closes_at_text!r}")
            print(f"    elig:  {(p.eligibility_text or '')[:150]!r}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
