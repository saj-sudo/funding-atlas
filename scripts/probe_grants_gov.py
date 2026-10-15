"""One-off probe: hit search2 and fetchOpportunity, save real responses as test fixtures,
and print the shape of what came back so the field mapping in connectors/grants_gov.py can be
checked against reality.  uv run python scripts/probe_grants_gov.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.grants_gov import FETCH_URL, SEARCH_URL, _client, _post, search_body  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "grants_gov"


def shape(obj, depth=0, max_depth=3):
    pad = "  " * depth
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and depth < max_depth:
                print(f"{pad}{k}: {type(v).__name__}[{len(v)}]")
                shape(v[0] if isinstance(v, list) and v else v, depth + 1, max_depth)
            else:
                s = json.dumps(v, ensure_ascii=False)
                print(f"{pad}{k}: {s[:90]}")
    elif isinstance(obj, list) and obj:
        shape(obj[0], depth, max_depth)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with _client() as client:
        print("== search2 page 1 ==")
        page1 = _post(client, SEARCH_URL, search_body(0, 100))
        (FIXTURES / "search2_page1.json").write_text(json.dumps(page1, indent=1, ensure_ascii=False))
        data = page1["data"]
        print("hitCount:", data.get("hitCount"), " returned:", len(data.get("oppHits") or []))
        print("facets - eligibilities:", json.dumps(data.get("eligibilities"))[:1500])
        print("facets - fundingInstruments:", json.dumps(data.get("fundingInstruments"))[:600])
        print("facets - fundingCategories:", json.dumps(data.get("fundingCategories"))[:1500])
        print("-- first hit --")
        shape((data.get("oppHits") or [{}])[0])

        print("\n== search2 page 2 (pagination check) ==")
        page2 = _post(client, SEARCH_URL, search_body(100, 100))["data"]
        ids1 = {h["id"] for h in data.get("oppHits") or []}
        ids2 = {h["id"] for h in page2.get("oppHits") or []}
        print("page2 returned:", len(ids2), " overlap with page1:", len(ids1 & ids2))

        hits = data.get("oppHits") or []
        posted = next((h for h in hits if h.get("oppStatus") == "posted"), None)
        forecast = next((h for h in hits if h.get("oppStatus") == "forecasted"), None)
        for label, hit in (("posted", posted), ("forecasted", forecast)):
            if not hit:
                print(f"\n(no {label} hit on page 1)")
                continue
            print(f"\n== fetchOpportunity {hit['id']} ({label}) ==")
            detail = _post(client, FETCH_URL, {"opportunityId": int(hit["id"])})
            (FIXTURES / f"fetch_{hit['id']}.json").write_text(json.dumps(detail, indent=1, ensure_ascii=False))
            shape(detail["data"], max_depth=2)
    print("\nfixtures written to", FIXTURES)


if __name__ == "__main__":
    main()
