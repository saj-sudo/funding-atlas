"""One-off probe: hit the SAM.gov assistance-listing search and detail endpoints, save real responses as
test fixtures, and print the shape of what came back.
  uv run python scripts/probe_sam_assistance_listings.py            # default numbers
  uv run python scripts/probe_sam_assistance_listings.py 14.218 97.044
Writes tests/fixtures/sam_assistance_listings/search_page0.json (size 5) and programs_<number>.json,
each the exact RawRecord payload {"hit": ..., "detail": ...}."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.sam_assistance_listings import DETAIL_URL, SEARCH_URL, _client, _get, lookup, search_params  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sam_assistance_listings"
DEFAULT_NUMBERS = ("97.106", "14.218", "66.458")


def shape(obj, depth=0, max_depth=3):
    pad = "  " * depth
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and depth < max_depth:
                print(f"{pad}{k}: {type(v).__name__}[{len(v)}]")
                shape(v[0] if isinstance(v, list) and v else v, depth + 1, max_depth)
            else:
                print(f"{pad}{k}: {json.dumps(v, ensure_ascii=False)[:90]}")
    elif isinstance(obj, list) and obj:
        shape(obj[0], depth, max_depth)


def main(numbers: list[str]) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with _client() as client:
        print("== search page 0 (size 5) ==")
        page = _get(client, SEARCH_URL, search_params(0, 5))
        (FIXTURES / "search_page0.json").write_text(json.dumps(page, indent=1, ensure_ascii=False))
        print("page:", page.get("page"))
        shape((page.get("_embedded") or {}).get("results") or [{}], max_depth=2)

        for pn in numbers:
            print(f"\n== {pn} ==")
            hit = lookup(client, pn)
            if not hit:
                print("not found")
                continue
            detail = _get(client, DETAIL_URL.format(id=hit["_id"]))
            (FIXTURES / f"programs_{pn}.json").write_text(
                json.dumps({"hit": hit, "detail": detail}, indent=1, ensure_ascii=False))
            d = detail["data"]
            print("title:", d.get("title"), "| active:", hit.get("isActive"), "| types:", hit.get("assistanceTypeLabels"))
            print("applicant types:", (d.get("eligibility") or {}).get("applicant", {}).get("types"))
            print("deadlines:", json.dumps((d.get("assistance") or {}).get("deadlines"))[:300])
            print("range:", json.dumps((d.get("financial") or {}).get("rangeAndAverageAssistance"))[:300])
            print("matching:", ((d.get("compliance") or {}).get("formulaAndMatching") or {}).get("types"))
    print("\nfixtures written to", FIXTURES)


if __name__ == "__main__":
    main(sys.argv[1:] or list(DEFAULT_NUMBERS))
