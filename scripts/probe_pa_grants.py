"""One-off probe for the pa.gov grants connector: read the search key, pull one Coveo page and a handful of
grant-details records, save them as test fixtures, and print what the connector sees on each.
  uv run python scripts/probe_pa_grants.py                 # the default records
  uv run python scripts/probe_pa_grants.py dced/2 dmva/1   # named records
Writes tests/fixtures/pa_grants/search_page1.json (the first Coveo page, trimmed to six results, totalCount kept)
and <agency>_<n>.json per record: the exact RawRecord payload, {"hit": ..., "detail": ...}."""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import pa_grants as pa  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "pa_grants"

DEFAULT_RECORDS = (
    "pema/10",     # closed federal pass-through, two percentages, eligibility is a URL
    "penndot/25",  # open, award range, 30% match, Municipality + Public Agency
    "dced/51",     # closed, CFA money, the Multimodal duplicate
    "dced/2",      # Act 47: Reoccurring, 2035 placeholder close -> rolling
    "dmva/1",      # Closed with a future open date -> forecasted
    "pema/14",     # Closed, open date after close date -> stays closed
    "dced/57",     # tax credit
    "dep/31",      # federal loan, Revolving Loan Fund, 2999 placeholder
    "pccd/63",     # open, no close date
)


def hit_for(client, key: str, source_id: str) -> dict:
    """The Coveo result for one record, by its URL."""
    url = f"https://www.pa.gov/en/grants/search/grant-details/{source_id}"
    body = pa.search_body(0, 1) | {"cq": f'@copapwpurl=="{url}"'}
    r = client.post(pa.COVEO_URL, json=body, headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    results = r.json().get("results") or []
    return pa.hit_fields(results[0]) if results else {"copapwpurl": url}


def main(ids: list[str]) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with pa._client() as client:
        key = pa.fetch_search_key(client)
        print(f"search key read ({len(key)} chars)")
        r = client.post(pa.COVEO_URL, json=pa.search_body(0, pa.ROWS), headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        page = r.json()
        trimmed = {k: page[k] for k in ("totalCount", "totalCountFiltered", "searchUid", "pipeline") if k in page}
        trimmed["results"] = [
            {"title": res.get("title"), "uri": res.get("uri"), "clickUri": res.get("clickUri"), "raw": pa.hit_fields(res)}
            for res in page["results"][:6]
        ]
        (FIXTURES / "search_page1.json").write_text(json.dumps(trimmed, indent=1, ensure_ascii=False) + "\n")
        print(f"search_page1.json: totalCount {page.get('totalCount')}, {len(trimmed['results'])} results kept")
        for sid in ids:
            hit = hit_for(client, key, sid)
            detail = pa.fetch_detail(client, sid) or {}
            payload = {"hit": hit, "detail": detail}
            name = sid.replace("/", "_") + ".json"
            (FIXTURES / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
            p = pa.normalize(RawRecord(source_connector=pa.CONNECTOR, source_id=sid, payload=payload), date.today())
            print(f"{name}: {p.name!r} | {p.status} {p.opens_at} -> {p.closes_at} | {p.funding_type} {p.funding_source}"
                  f" | match {p.match_required} {p.match_pct} | rolling {p.rolling} | {p.applicant_pairs()} | {p.category_pairs()}")
            time.sleep(pa.DETAIL_DELAY_S)


if __name__ == "__main__":
    main(sys.argv[1:] or list(DEFAULT_RECORDS))
