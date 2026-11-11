"""Measure a shared-rule change on every stored record (roadmap 10.x sessions).

Re-normalizes every raw record in `atlas.db` through its connector on a fixed date and writes, per record, the sorted
applicant tags, the status and the `record_hash`. Run it before and after a rule change and diff the two files:
  uv run python scripts/measure_tagger.py snapshot before.json
  uv run python scripts/measure_tagger.py snapshot after.json
  uv run python scripts/measure_tagger.py diff before.json after.json
`atlas.db` is the database restored from `gh-pages` (`git show origin/gh-pages:atlas.db.gz | gunzip > atlas.db`).
"""

from __future__ import annotations

import inspect
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.models import RawRecord  # noqa: E402
from pipeline.run import CONNECTORS  # noqa: E402

DAY = date(2026, 11, 11)


def snapshot(db: str, out: str) -> None:
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT source_connector, source_id, payload FROM raw_record ORDER BY 1, 2").fetchall()
    result: dict[str, dict] = {}
    errors = 0
    for connector, source_id, payload in rows:
        mod = CONNECTORS.get(connector)
        if mod is None:
            continue
        try:
            raw = RawRecord(source_connector=connector, source_id=source_id, payload=json.loads(payload))
            # Connectors that decide status from dates take the run date; the rest take the record only.
            p = mod.normalize(raw, DAY) if len(inspect.signature(mod.normalize).parameters) > 1 else mod.normalize(raw)
        except Exception as e:  # a record a connector no longer reads is reported, not fatal
            errors += 1
            result[f"{connector}/{source_id}"] = {"error": repr(e)[:200]}
            continue
        result[f"{connector}/{source_id}"] = {
            "name": p.name,
            "tags": sorted({t.value for t in p.applicant_types}),
            "status": p.status,
            "hash": p.record_hash,
        }
    Path(out).write_text(json.dumps(result, indent=0, sort_keys=True), encoding="utf-8")
    print(f"{len(result)} records, {errors} errors -> {out}")


def diff(before: str, after: str) -> None:
    a = json.loads(Path(before).read_text(encoding="utf-8"))
    b = json.loads(Path(after).read_text(encoding="utf-8"))
    tag_moves = [k for k in a if k in b and a[k].get("tags") != b[k].get("tags")]
    other = [k for k in a if k in b and k not in tag_moves and a[k].get("hash") != b[k].get("hash")]
    for k in tag_moves:
        print(f"TAGS  {k}  {a[k]['name'][:60]!r}  {a[k]['tags']} -> {b[k]['tags']}")
    for k in other:
        print(f"HASH  {k}  {a[k].get('name', '')[:60]!r}  status {a[k].get('status')} -> {b[k].get('status')}")
    print(f"{len(tag_moves)} tag moves, {len(other)} other hash moves, of {len(a)}")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "snapshot":
        snapshot("atlas.db", args[0])
    else:
        diff(*args)
