"""One-off probe for the Delaware State Housing Authority connector: read the six hand-listed pages once, save them
as fixtures (scripts, comments, contact cards, phone numbers and e-mails removed) and print what the connector sees.
  uv run python scripts/probe_de_dsha.py"""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import de_dsha as de  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "de_dsha"


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.select("script, .hd-contact-card"):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for row in soup.select(".hd-hdr-meta > div"):
        k = row.select_one(".hd-hdr-meta-k")
        if k and k.get_text(strip=True).lower().startswith("questions"):
            row.decompose()
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", "contact@example.delaware.gov", str(soup))
    return re.sub(r"\(\d{3}\) \d{3}-\d{4}", "(000) 000-0000", text)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with de._client() as client:
        html_by_slug = {}
        for slug in de.PAGES:
            time.sleep(de.DELAY_S)
            html_by_slug[slug] = de._get(client, f"{de.BASE}/{slug}/")
            (FIXTURES / f"{slug}.html").write_text(scrub(html_by_slug[slug]), encoding="utf-8")
    import httpx
    de_get = lambda client, url: html_by_slug[url.rstrip("/").rsplit("/", 1)[-1]]  # noqa: E731
    saved = de._get
    de._get = de_get
    try:
        for r in de.fetch():
            p = de.normalize(r, date.today())
            print(f"{r.source_id:36} {p.name[:40]!r} | {p.status} {p.opens_at}->{p.closes_at} rolling={p.rolling} {p.funding_type} {p.funding_source}"
                  f" | {sorted({t.value for t in p.applicant_types})}")
            print(f"    status: {p.closes_at_text!r}")
            print(f"    elig:   {(p.eligibility_text or '')[:160]!r}")
    finally:
        de._get = saved
    _ = httpx
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
