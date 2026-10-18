"""One-off probe for the grants.wv.gov connector: pull the AvailableGrants list once, keep the items the tests
need, save them as the fixture, and print what the connector sees on each.
  uv run python scripts/probe_wv_grants.py             # the default ids plus one pass-through and one future forecast
  uv run python scripts/probe_wv_grants.py 78 76 201   # named ids
Writes tests/fixtures/wv_grants/availablegrants_sample.json: the API envelope ({"properties": [...]}) trimmed to the
chosen items, exactly as the connector's fetch() reads it."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import wv_grants as wv  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "wv_grants"

DEFAULT_IDS = (
    "78",   # CWSRF: active on 2026-10-18, counties and municipalities named
    "76",   # Chesapeake Bay: posted 2027-01-01, "Ongoing" -> forecasted, rolling
    "201",  # SWMB FY2027: past due, municipal
    "131",  # Arts CAPS: past due, "Annual deadline of April 1st" -> closed with cycle text
    "141",  # "rolling deadline", past due -> closed, rolling
    "142",  # no dates, "No further solicitations..." -> unknown
    "95",   # no dates, "Spring 2023" -> unknown (stale forecast)
    "94",   # CDBG: past due, municipal
)


def main(ids: list[str]) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with wv._client() as client:
        items = wv.fetch_list(client)
    print(f"list: {len(items)} items")
    by_id = {str(i["Id"]): i for i in items}
    wanted = [i for i in ids if i in by_id]
    if not sys.argv[1:]:
        today = date.today()
        extra = [i for i in items if i.get("TypeOfGrant") == "Pass-through"][:1]
        extra += [i for i in items if (lambda d: d and d >= today)(wv.forecast_date(i.get("Forecasted") or ""))][:1]
        extra += [i for i in items if i.get("ImportantDateTitle1") and not i.get("Forecasted")][:1]
        wanted += [str(i["Id"]) for i in extra if str(i["Id"]) not in wanted]
    sample = {"properties": [by_id[i] for i in wanted] + [""]}
    (FIXTURES / "availablegrants_sample.json").write_text(json.dumps(sample, indent=1, ensure_ascii=False) + "\n")
    print(f"availablegrants_sample.json: {len(wanted)} items ({', '.join(wanted)})")
    for i in wanted:
        p = wv.normalize(RawRecord(source_connector=wv.CONNECTOR, source_id=i, payload=by_id[i]), date.today())
        print(f"{i}: {p.name[:50]!r} | {p.status} {p.opens_at} -> {p.closes_at} | text {p.closes_at_text!r:.45} | rolling {p.rolling}"
              f" | {p.funding_type} {p.funding_source} | {p.applicant_pairs()} | {p.category_pairs()}")


if __name__ == "__main__":
    main(sys.argv[1:] or list(DEFAULT_IDS))
