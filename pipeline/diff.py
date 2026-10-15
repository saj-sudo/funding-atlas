"""Render one run's program_change rows as a markdown report."""

from __future__ import annotations

import json
import sqlite3


def _trim(s: str | None, n: int = 70) -> str:
    s = (s or "").replace("|", "/").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _describe(fields: dict | None) -> str:
    if not fields:
        return ""
    parts = []
    for k, v in fields.items():
        if k == "status":
            parts.append(f"status {v['old']} → {v['new']}")
        elif k == "closes_at":
            parts.append(f"closes_at {v['old']} → {v['new']}")
        else:
            parts.append(k)
    return ", ".join(parts)


MAX_ROWS_PER_TABLE = 100   # a first catalog run adds ~2,900 rows; the report is for reading, the DB has the rest


def latest_run_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT MAX(id) FROM run").fetchone()
    return row[0] if row else None


def render(conn: sqlite3.Connection, run_id: int) -> str:
    run = conn.execute("SELECT * FROM run WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        return f"No run with id {run_id}."
    run = dict(run)
    rows = [
        dict(r) for r in conn.execute(
            "SELECT c.change_type, c.changed_fields, p.name, p.status, p.closes_at, p.source_url"
            " FROM program_change c JOIN program p ON p.id = c.program_id"
            " WHERE c.run_id = ? ORDER BY c.change_type, p.closes_at IS NULL, p.closes_at, p.name",
            (run_id,),
        )
    ]
    for r in rows:
        r["fields"] = json.loads(r["changed_fields"]) if r["changed_fields"] else None

    out = [
        f"## Run {run['id']} · {run['connector']} · {run['started_at']} · {run['status']}",
        "",
        f"fetched {run['fetched_count'] or 0} · added {run['added_count'] or 0} · "
        f"changed {run['changed_count'] or 0} · missing {run['missing_count'] or 0}",
    ]
    if run.get("error"):
        out += ["", f"error: {run['error']}"]

    def table(title: str, subset: list[dict]) -> None:
        if not subset:
            return
        out.extend(["", f"### {title} ({len(subset)})", "",
                    "| name | status | closes | change | source |", "|---|---|---|---|---|"])
        for r in subset[:MAX_ROWS_PER_TABLE]:
            out.append(
                f"| {_trim(r['name'])} | {r['status']} | {r['closes_at'] or ''} | "
                f"{_trim(_describe(r['fields']), 90)} | {r['source_url']} |"
            )
        if len(subset) > MAX_ROWS_PER_TABLE:
            out.append(f"| … and {len(subset) - MAX_ROWS_PER_TABLE} more | | | | |")

    transitions = [r for r in rows if r["fields"] and "status" in r["fields"]]
    table("Status transitions", transitions)
    table("Added", [r for r in rows if r["change_type"] == "added"])
    table("Changed", [r for r in rows if r["change_type"] == "changed" and r not in transitions])
    table("Missing from source", [r for r in rows if r["change_type"] == "missing" and r not in transitions])
    if not rows:
        out += ["", "No changes."]
    return "\n".join(out) + "\n"
