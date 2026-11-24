"""Measure a shared-rule change on every agency-page fixture (CLAUDE.md: a rule change is measured on every stored record
and on every fixture of every agency-page connector; the stored database does not hold connectors no daily run has read).

For every connector in `pipeline.run.CONNECTORS` whose module has a `SITE` with `PAGES` and `parse_page` (the hand-list
and agency-page connectors), each slug's saved page `tests/fixtures/<connector>/<slug>.html` (and `<slug>.2.html`, ... for
a slug read from several pages) goes through `parse_page` -> `records_for` -> `normalize` on a fixed date. Per record: the
fields a reading rule can move, and the `record_hash`. Run before and after a rule change and diff:
  uv run python scripts/measure_fixtures.py snapshot fx_before.json
  uv run python scripts/measure_fixtures.py snapshot fx_after.json
  uv run python scripts/measure_fixtures.py diff fx_before.json fx_after.json
A slug with no fixture is counted, not read.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.models import RawRecord  # noqa: E402
from pipeline.run import CONNECTORS  # noqa: E402

DAY = date(2026, 11, 24)
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
FIELDS = ("name", "status", "opens_at", "closes_at", "closes_at_text", "rolling", "funding_type", "funding_source",
          "match_required", "summary", "eligibility_text")


def pages_for(folder: Path, slug: str) -> list[str]:
    """The slug's saved page and any further pages (`<slug>.2.html`, ...), in order; empty when none was saved."""
    first = folder / f"{slug}.html"
    if not first.exists():
        return []
    out, n = [first.read_text(encoding="utf-8")], 2
    while (folder / f"{slug}.{n}.html").exists():
        out.append((folder / f"{slug}.{n}.html").read_text(encoding="utf-8"))
        n += 1
    return out


def records(names: list[str] | None = None, day: date = DAY) -> tuple[dict[str, dict], int]:
    """`connector/source_id` -> the measured fields, and how many slugs had no fixture."""
    result: dict[str, dict] = {}
    missing = 0
    for name, mod in CONNECTORS.items():
        if names and name not in names:
            continue
        site = getattr(mod, "SITE", None)
        if site is None or not getattr(site, "PAGES", None) or not hasattr(site, "parse_page"):
            continue
        folder = FIXTURES / name
        count = 0
        for slug, spec in site.PAGES.items():
            htmls = pages_for(folder, slug)
            if not htmls:
                missing += 1
                continue
            try:
                parsed = [site.parse_page(h) for h in htmls]
                pairs = site.records_for(slug, spec, parsed, count)
            except Exception as e:  # a fixture the reader no longer understands is reported, not fatal
                result[f"{name}/{slug}"] = {"error": repr(e)[:200]}
                continue
            for sid, payload in pairs:
                count += 1
                key = f"{name}/{sid}"
                try:
                    p = mod.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), day)
                except Exception as e:
                    result[key] = {"error": repr(e)[:200]}
                    continue
                row = {f: (str(getattr(p, f)) if getattr(p, f) is not None else None) for f in FIELDS}
                row["tags"] = sorted({t.value for t in p.applicant_types})
                row["hash"] = p.record_hash
                result[key] = row
    return result, missing


def snapshot(out: str) -> None:
    result, missing = records()
    errors = sum(1 for v in result.values() if "error" in v)
    Path(out).write_text(json.dumps(result, indent=0, sort_keys=True), encoding="utf-8")
    print(f"{len(result)} fixture records, {errors} errors, {missing} slugs without a fixture -> {out}")


def diff(before: str, after: str) -> None:
    a = json.loads(Path(before).read_text(encoding="utf-8"))
    b = json.loads(Path(after).read_text(encoding="utf-8"))
    moved = 0
    for k in sorted(set(a) | set(b)):
        if k not in a or k not in b:
            print(f"{'NEW ' if k not in a else 'GONE'}  {k}")
            moved += 1
            continue
        if a[k].get("hash") == b[k].get("hash"):
            continue
        moved += 1
        changes = [f"{f}: {a[k].get(f)!r} -> {b[k].get(f)!r}" for f in (*FIELDS, "tags") if a[k].get(f) != b[k].get(f)]
        print(f"MOVE  {k}  {(a[k].get('name') or '')[:60]!r}")
        for c in changes or ["(hash only)"]:
            print(f"        {c[:300]}")
    print(f"{moved} moved, of {len(a)}")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "snapshot":
        snapshot(args[0])
    else:
        diff(*args)
