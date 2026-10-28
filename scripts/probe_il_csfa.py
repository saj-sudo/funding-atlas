"""One-off probe for the Illinois CSFA connector: read the live list once, keep the rows the tests need, save the list
(trimmed), the agency table, and the opportunity and program pages of the native rows as fixtures, and print what the
connector sees on each.
  uv run python scripts/probe_il_csfa.py
Writes tests/fixtures/il_csfa/: OpportunityList.html, AgencyList.html, opportunity_<n>.html, program_<n>.html."""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import il_csfa as il  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "il_csfa"

# Case name -> predicate on a parsed list row; the first row that satisfies each, in list order, is kept.
CASES = {
    "native, no end date": lambda r: r["kind"] == "nofo" and "No end date" in r["date_range"],
    "native, dated": lambda r: r["kind"] == "nofo" and "No end date" not in r["date_range"],
    "native, Not Applicable award": lambda r: r["kind"] == "nofo" and r["award_range"] == "Not Applicable",
    "native, municipal free text": lambda r: r["kind"] == "nofo" and "Community Development Block Grant Disaster" in r["title"],
    "native, federal source": lambda r: r["kind"] == "nofo" and "Emergency Management Performance" in r["title"],
    "native, Illinois Grocery Initiative (shared program)": lambda r: r["kind"] == "nofo" and "Grocery" in r["title"],
    "gms, no end date": lambda r: r["kind"] == "gms" and "No end date" in r["date_range"],
    "gms, dated": lambda r: r["kind"] == "gms" and "No end date" not in r["date_range"],
    "gms, DNR": lambda r: r["kind"] == "gms" and r["agency"].startswith("DNR"),
}


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with il._client() as client:
        list_html = il._get(client, il.LIST_URL)
        agency_html = il._get(client, il.AGENCY_URL)
        rows = il.parse_list(list_html)
        print(f"list: {len(rows)} rows")
        wanted: list[dict] = []
        for name, pred in CASES.items():
            hit = next((r for r in rows if pred(r) and r not in wanted), None)
            print(f"{name}: {hit['source_id'] if hit else None}")
            if hit:
                wanted.append(hit)
        # A second Grocery Initiative round, to prove two opportunities can share one program page.
        for r in rows:
            if r["kind"] == "nofo" and "Grocery" in r["title"] and r not in wanted:
                wanted.append(r)
                break
        keep = {r["source_id"] for r in wanted}

        soup = BeautifulSoup(list_html, "html.parser")
        for tr in soup.find("table", id="tblList").find("tbody").find_all("tr"):
            cells = tr.find_all("td")
            link = cells[0].find("a", href=True)
            m = il.NOFO_RE.search(link["href"])
            sid = f"nofo-{m.group(1)}" if m else f"gms-{(il.amplifund_target(link['href']) or '').rstrip('/').rsplit('/', 1)[-1]}"
            if sid not in keep:
                tr.decompose()
        (FIXTURES / "OpportunityList.html").write_text(str(soup), encoding="utf-8")
        (FIXTURES / "AgencyList.html").write_text(agency_html, encoding="utf-8")

        saved_programs: set[str] = set()
        for r in wanted:
            if r["kind"] != "nofo":
                continue
            n = r["source_id"].split("-", 1)[1]
            time.sleep(il.DELAY_S)
            opp_html = il._get(client, il.OPPORTUNITY_URL.format(n=n))
            (FIXTURES / f"opportunity_{n}.html").write_text(opp_html, encoding="utf-8")
            csfa = il.program_number(opp_html)
            if csfa and csfa not in saved_programs:
                time.sleep(il.DELAY_S)
                (FIXTURES / f"program_{csfa}.html").write_text(il._get(client, il.PROGRAM_URL.format(n=csfa)), encoding="utf-8")
                saved_programs.add(csfa)
    print(f"saved {len(wanted)} rows, {len(saved_programs)} program pages")

    agencies = il.parse_agencies(agency_html)
    for r in wanted:
        payload = {"list": r, "agency_name": agencies.get(il.split_agency(r["agency"])[1] or ""),
                   "opportunity": None, "program": None, "program_id": None}
        if r["kind"] == "nofo":
            n = r["source_id"].split("-", 1)[1]
            opp_html = (FIXTURES / f"opportunity_{n}.html").read_text(encoding="utf-8")
            payload["opportunity"] = il.parse_fields(opp_html)
            csfa = il.program_number(opp_html)
            payload["program"] = il.parse_fields((FIXTURES / f"program_{csfa}.html").read_text(encoding="utf-8"))
        p = il.normalize(RawRecord(source_connector=il.CONNECTOR, source_id=r["source_id"], payload=payload), date.today())
        print(f"{r['source_id'][:18]}: {p.name[:40]!r} | {p.status} {p.opens_at} -> {p.closes_at} | {p.closes_at_text!r} rolling {p.rolling}"
              f" | {p.agency_code} {p.funding_type} {p.funding_source} {p.amount_min}-{p.amount_max} match {p.match_required}"
              f" | {p.applicant_pairs()} | {p.category_pairs()}")


if __name__ == "__main__":
    main()
