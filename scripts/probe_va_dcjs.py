"""One-off probe for the Virginia DCJS connector: read the view and the program pages the tests need, save them as
fixtures, and print what the connector sees on each.
  uv run python scripts/probe_va_dcjs.py
Writes tests/fixtures/va_dcjs/: grants.html (the view, trimmed to the kept rows, with the first row repeated once)
and program_<slug>.html for each kept row. Scripts and the Grant Contact Information block (named people) are removed
from every page."""

from __future__ import annotations

import copy
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import va_dcjs as va  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "va_dcjs"

# why -> predicate on (row, parsed program); the first row satisfying each is kept.
WANTED = (
    ("599: localities, a bold-run label", lambda r, p: "599" in r["title"] and "2027" in r["title"]),
    ("local units of government under a heading", lambda r, p: "School Safety Officer" in r["title"]),
    ("a negated sentence beside the applicant statement", lambda r, p: any("not open to" in e for e in p["eligibility"])),
    ("no eligibility passage", lambda r, p: not p["eligibility"] and "Opioid" in r["title"]),
    ("nonprofits only", lambda r, p: any("exclusively to non-profit" in e for e in p["eligibility"])),
)
CONTACT_BLOCK = "block-uswds-base-subtheme-grantcontactinformation"


def scrub(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.find_all("script"):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):      # Drupal's THEME DEBUG template comments
        c.extract()
    for block in soup.find_all(id=lambda i: i and i.startswith(CONTACT_BLOCK)):
        block.decompose()
    for el in soup.find_all(string=lambda s: "Grant Coordinator" in s or "Grant Monitor" in s):
        el.find_parent().decompose()
    return str(soup)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with va._client() as client:
        list_html = va._get(client, va.LIST_URL)
        rows = va.parse_rows(list_html)
        print(f"view: {len(rows)} rows")
        programs: dict[str, dict] = {}
        for row in rows:
            time.sleep(va.DELAY_S)
            programs[row["slug"]] = (va.parse_program(va._get(client, row["url"])), None)
        keep: list[dict] = []
        for why, pred in WANTED:
            hit = next((r for r in rows if r not in keep and pred(r, programs[r["slug"]][0])), None)
            print(f"  {why}: {hit['slug'] if hit else None}")
            if hit:
                keep.append(hit)
        soup = BeautifulSoup(list_html, "html.parser")
        body = soup.select_one("table.usa-table tbody")
        kept_trs = []
        for tr in body.find_all("tr"):
            link = tr.select_one("td.views-field-title a[href]")
            slug = link["href"].rstrip("/").rsplit("/", 1)[-1] if link else ""
            if slug in {r["slug"] for r in keep}:
                kept_trs.append(tr)
            tr.extract()
        for tr in kept_trs:
            body.append(tr)
        body.append(copy.copy(kept_trs[0]))          # the repeat the connector must drop
        (FIXTURES / "grants.html").write_text(scrub(str(soup)), encoding="utf-8")
        for row in keep:
            time.sleep(va.DELAY_S)
            (FIXTURES / f"program_{row['slug']}.html").write_text(scrub(va._get(client, row["url"])), encoding="utf-8")
            p = va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id=row["slug"],
                                       payload={"row": row, "program": programs[row["slug"]][0]}), date.today())
            print(f"  {row['slug'][:40]}: {p.status} {p.opens_at} -> {p.closes_at} | {[t.value for t in p.applicant_types]} | {(p.eligibility_text or '')[:80]!r}")
    print("fixtures:", sorted(f.name for f in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
