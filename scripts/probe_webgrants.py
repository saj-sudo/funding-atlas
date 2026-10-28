"""One-off probe for the WebGrants connector: read each storefront list once, keep the rows the tests need, save the
trimmed lists and those rows' detail pages as fixtures, and print what the connector sees on each.
  uv run python scripts/probe_webgrants.py
Writes tests/fixtures/webgrants/: <host>_list.html and detail_<host>-<ID>.html."""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import webgrants as wg  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "webgrants"

# host key -> (title fragment, why it is kept). Rows are matched by title so the probe survives a changed ID.
WANTED = {
    "ia": (
        ("Iowa Energy Center Grant Program", "Eligible Applicants and Eligibility Requirements sections, a pre-application date"),
        ("CDBG 2024 Disaster Recovery - General Infrastructure", "municipal: units of general local government and tribes"),
        ("Historic Preservation Tax Credit - Small Projects", "Final deadline Not Applicable; cities and counties are NOT eligible"),
        ("FY 27 Computer Science Incentive Fund - ENDORSEMEN", "no description at all"),
    ),
    "mtagr": (
        ("Emergency Weed Grant", "Montana, no eligibility heading"),
        ("Potato Research and Market Development", "all-caps APPLICANT ELIGIBILITY heading, applicants as plain paragraphs"),
    ),
    "mtfwp": (),
}


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    kept: list[tuple[str, dict[str, str], str]] = []
    with wg._client() as client:
        for key, (base, _state) in wg.HOSTS.items():
            list_html = wg._get(client, base + wg.LIST_PATH)
            rows = wg.parse_list(list_html)
            print(f"{key}: {len(rows)} rows")
            chosen = []
            for fragment, why in WANTED[key]:
                hit = next((r for r in rows if fragment.lower() in r["title"].lower()), None)
                print(f"  {fragment}: {hit['id'] if hit else None}  ({why})")
                if hit:
                    chosen.append(hit)
            keep_oids = {r["oid"] for r in chosen}
            soup = BeautifulSoup(list_html, "html.parser")
            table = soup.find("table", id="storefrontFO")
            for tr in table.find("tbody").find_all("tr") if table and table.find("tbody") else []:
                link = tr.find("a", href=True)
                if link is None or link["href"].split("OIDString=", 1)[-1] not in keep_oids:
                    tr.decompose()
            (FIXTURES / f"{key}_list.html").write_text(str(soup), encoding="utf-8")
            for row in chosen:
                time.sleep(wg.DELAY_S)
                page = wg._get(client, base + wg.DETAIL_PATH.format(oid=row["oid"]))
                (FIXTURES / f"detail_{key}-{row['id']}.html").write_text(page, encoding="utf-8")
                kept.append((key, row, page))
    for key, row, page in kept:
        payload = {"host": key, "list": row, "detail": wg.parse_detail(page)}
        p = wg.normalize(RawRecord(source_connector=wg.CONNECTOR, source_id=f"{key}-{row['id']}", payload=payload), date.today())
        print(f"{p.source_id}: {p.name[:42]!r} | {p.status} {p.opens_at} -> {p.closes_at} | {p.closes_at_text!r} rolling {p.rolling}"
              f" | {p.funding_type} {p.amount_min}-{p.amount_max} | {p.applicant_pairs()} | {p.category_pairs()}")


if __name__ == "__main__":
    main()
