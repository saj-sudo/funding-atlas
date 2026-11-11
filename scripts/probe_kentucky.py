"""One-off probe for Kentucky's four agencies: read every page in each module's `PAGES` once, save what the connectors
read as fixtures, and print what they see.
  uv run python scripts/probe_kentucky.py [ky_dlgfed ky_tc ky_eec ky_kia]
Writes tests/fixtures/<connector>/<slug>.html holding only the page's `h1` and its rich-text fields (the whole SharePoint
page is 50 to 280 KB of chrome); the connectors read exactly those."""

from __future__ import annotations

import importlib
import re
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import hand_list as hl  # noqa: E402
from connectors import kentucky_sharepoint as ky  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
ALL = ["ky_dlgfed", "ky_tc", "ky_eec", "ky_kia"]
# The repository is public: no staff name, e-mail address or phone number goes into a fixture.
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}-\d{4}\b")
MAILTO_RE = re.compile(r'(<a href="mailto:[^"]*">)[^<]*(</a>)')      # a staff member's name is the link text


def scrub(page_html: str) -> str:
    """The title, the h1 and the outermost rich-text fields: what `kentucky_sharepoint.parse_page` reads."""
    doc = hl.soup(page_html)
    keep = BeautifulSoup("<html><head><title></title></head><body></body></html>", "html.parser")
    keep.title.string = doc.title.get_text(strip=True) if doc.title else ""
    if doc.h1:
        keep.body.append(BeautifulSoup(f"<h1>{doc.h1.get_text(' ', strip=True)}</h1>", "html.parser"))
    for field in doc.select(ky.BODY_SELECTOR):
        if not field.find_parent("div", class_="ms-rtestate-field"):
            if re.match(r"^\W*Staff\b", field.get_text(" ", strip=True)):      # ARC's staff list: names and addresses
                continue
            for tag in field.select("script, style, svg, noscript, iframe"):
                tag.decompose()
            keep.body.append(field)
    return PHONE_RE.sub("502-000-0000", EMAIL_RE.sub("contact@ky.gov", MAILTO_RE.sub(r"\1the office\2", str(keep))))


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
                    print(f"  {sid:30} {p.status:10} open={p.opens_at} close={p.closes_at} {p.funding_type:6} {p.funding_source:12} "
                          f"{[t.value for t in p.applicant_types]} | {(p.closes_at_text or '')[:80]}")


if __name__ == "__main__":
    main(sys.argv[1:] or ALL)
