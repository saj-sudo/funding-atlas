"""One-off probe for the California Grants Portal connector: download the CSV once, keep the rows the tests need,
save them as the fixture, and print what the connector sees on each.
  uv run python scripts/probe_ca_grants.py                 # one row per case below
  uv run python scripts/probe_ca_grants.py 194175 192864   # named PortalIDs
Writes tests/fixtures/ca_grants/grants_sample.csv: the header (byte-order mark included) and the chosen rows, exactly
as the connector's fetch() reads the file."""

from __future__ import annotations

import csv
import io
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import ca_grants as ca  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ca_grants"

# Case name -> predicate on a row; the first row that satisfies each, in file order, is kept.
CASES = {
    "active, Public Agency only, notes name cities": lambda r: r["Status"] == "active"
        and r["ApplicantType"] == "Public Agency" and "cities" in r["ApplicantTypeNotes"].lower(),
    "active, Public Agency only, no notes": lambda r: r["Status"] == "active"
        and r["ApplicantType"] == "Public Agency" and not r["ApplicantTypeNotes"].strip(),
    "active, Ongoing deadline": lambda r: r["Status"] == "active" and r["ApplicationDeadline"] == "Ongoing",
    "active, range and match percentage": lambda r: r["Status"] == "active"
        and r["EstAmounts"].startswith("Between") and r["MatchingFunds"].endswith("%"),
    "single amount": lambda r: r["EstAmounts"].startswith("$"),
    "forecasted, text open date": lambda r: r["Status"] == "forecasted",
    "closed, federal, municipal notes": lambda r: r["Status"] == "closed" and r["FundingSource"] == "Federal"
        and "cities" in r["ApplicantTypeNotes"].lower(),
    "closed, loan": lambda r: r["Status"] == "closed" and r["Type"] == "Loan",
    "Grant; Loan, Federal and State": lambda r: r["Type"] == "Grant; Loan" and r["FundingSource"] == "Federal and State",
    "GrantID present": lambda r: bool(r["GrantID"].strip()),
}


def main(ids: list[str]) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with ca._client() as client:
        r = client.get(ca.CSV_URL)
        r.raise_for_status()
    text = r.content.decode("utf-8-sig")
    rows = ca.parse_csv(text)
    print(f"file: {len(rows)} rows")
    by_id = {row["PortalID"]: row for row in rows}
    if ids:
        wanted = [i for i in ids if i in by_id]
    else:
        wanted = []
        for name, pred in CASES.items():
            hit = next((row["PortalID"] for row in rows if pred(row) and row["PortalID"] not in wanted), None)
            print(f"{name}: {hit}")
            if hit:
                wanted.append(hit)
    header = next(csv.reader(io.StringIO(text)))
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=header, lineterminator="\r\n")
    writer.writeheader()
    for i in wanted:
        writer.writerow(by_id[i])
    (FIXTURES / "grants_sample.csv").write_bytes(("﻿" + out.getvalue()).encode("utf-8"))
    print(f"grants_sample.csv: {len(wanted)} rows ({', '.join(wanted)})")
    for i in wanted:
        p = ca.normalize(RawRecord(source_connector=ca.CONNECTOR, source_id=i, payload=by_id[i]), date.today())
        print(f"{i}: {p.name[:45]!r} | {p.status} {p.opens_at} -> {p.closes_at} | text {p.closes_at_text!r:.30} | rolling {p.rolling}"
              f" | {p.funding_type} {p.funding_source} {p.amount_min}-{p.amount_max} match {p.match_required} {p.match_pct}"
              f" | {p.applicant_pairs()} | {p.category_pairs()}")


if __name__ == "__main__":
    main(sys.argv[1:])
