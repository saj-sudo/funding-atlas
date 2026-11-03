"""One-off probe for the Maryland MDOT connector: read the three live pages with the connector's own functions, save
them as fixtures (scripts, comments, contact details and the named program managers removed) and print what the
connector sees.
  uv run python scripts/probe_md_mdot.py"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import md_mdot as md  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "md_mdot"
NAMED_CONTACT_RE = re.compile(r"(reach out to|please contact|contact) [A-Z][a-z]+ [A-Z][a-z]+", re.I)


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.find_all(["script", "noscript", "iframe"]):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for a in soup.find_all("a", href=True):
        if "email-protection" in a["href"] or a["href"].startswith("mailto:"):
            a.decompose()
    text = str(soup)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", "contact@example.maryland.gov", text)
    text = re.sub(r"\b\d{3}[.-]\d{3}[.-]\d{4}\b", "000-000-0000", text)
    return NAMED_CONTACT_RE.sub(r"\1 the program manager", text)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with md._client() as client:
        for slug, (page_id, section) in md.PAGES.items():
            html = md._get(client, md.URL.format(n=page_id))
            (FIXTURES / f"{slug}.html").write_text(scrub(html), encoding="utf-8")
            page = md.parse_page(html)
            p = md.normalize(RawRecord(source_connector=md.CONNECTOR, source_id=slug,
                                       payload={"page_id": page_id, "section": section, "page": page}), date.today())
            print(f"{slug:10} {p.name!r} | {p.status} {p.closes_at} rolling={p.rolling} {p.funding_type} match={p.match_required} | {sorted({t.value for t in p.applicant_types})}")
            print(f"    round: {p.closes_at_text!r}")
            print(f"    elig:  {(p.eligibility_text or '')[:300]!r}")
            print(f"    summary: {(p.summary or '')[:120]!r}")
            print(f"    blocks: {len(page['blocks'])}; labels: {[t for k, t in page['blocks'] if k == 'label'][:12]}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
