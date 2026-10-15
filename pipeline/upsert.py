"""Hash-compare upsert of normalized Programs, plus resolution of records that vanished from a source."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable
from typing import Any

from pipeline.models import LIST_FIELDS, PROGRAM_FIELDS, Program

_COLS = ", ".join(PROGRAM_FIELDS)
_PLACEHOLDERS = ", ".join("?" for _ in PROGRAM_FIELDS)
_SET = ", ".join(f"{c} = ?" for c in PROGRAM_FIELDS)


def load_existing(conn: sqlite3.Connection, connector: str, source_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM program WHERE source_connector = ? AND source_id = ?", (connector, source_id)
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    pid = d["id"]
    d["applicant_types"] = sorted(
        (r[0], r[1]) for r in conn.execute(
            "SELECT applicant_type, source_code FROM program_applicant_type WHERE program_id = ?", (pid,))
    )
    d["categories"] = sorted(
        (r[0], r[1]) for r in conn.execute(
            "SELECT category, source_code FROM program_category WHERE program_id = ?", (pid,))
    )
    d["alns"] = sorted(r[0] for r in conn.execute("SELECT aln FROM program_aln WHERE program_id = ?", (pid,)))
    return d


def changed_fields(old: dict[str, Any], new: Program) -> dict[str, dict[str, Any]]:
    """Column-by-column diff between a stored row (from load_existing) and a fresh Program."""
    out: dict[str, dict[str, Any]] = {}
    new_row = new.row()
    for f in PROGRAM_FIELDS:
        if old.get(f) != new_row[f]:
            out[f] = {"old": old.get(f), "new": new_row[f]}
    new_lists = {
        "applicant_types": new.applicant_pairs(),
        "categories": new.category_pairs(),
        "alns": new.aln_list(),
    }
    for f in LIST_FIELDS:
        old_list = [tuple(x) if isinstance(x, (list, tuple)) else x for x in old.get(f, [])]
        if old_list != new_lists[f]:
            out[f] = {"old": old_list, "new": new_lists[f]}
    return out


def _write_junctions(conn: sqlite3.Connection, pid: int, p: Program) -> None:
    conn.execute("DELETE FROM program_applicant_type WHERE program_id = ?", (pid,))
    conn.execute("DELETE FROM program_category WHERE program_id = ?", (pid,))
    conn.execute("DELETE FROM program_aln WHERE program_id = ?", (pid,))
    conn.executemany(
        "INSERT INTO program_applicant_type (program_id, applicant_type, source_code) VALUES (?, ?, ?)",
        [(pid, v, c) for v, c in p.applicant_pairs()],
    )
    conn.executemany(
        "INSERT INTO program_category (program_id, category, source_code) VALUES (?, ?, ?)",
        [(pid, v, c) for v, c in p.category_pairs()],
    )
    conn.executemany(
        "INSERT INTO program_aln (program_id, aln) VALUES (?, ?)",
        [(pid, a) for a in p.aln_list()],
    )


def _log_change(conn, run_id, pid, change_type, old_hash, new_hash, fields, now) -> None:
    conn.execute(
        "INSERT INTO program_change (run_id, program_id, change_type, old_hash, new_hash, changed_fields, changed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, pid, change_type, old_hash, new_hash,
         json.dumps(fields, sort_keys=True, default=str) if fields else None, now),
    )


def upsert(conn: sqlite3.Connection, run_id: int, programs: Iterable[Program], now: str) -> dict[str, int]:
    """Insert new programs, update changed ones, touch last_seen on the rest. Logs every add/change.
    The source is the truth: anything that differs from it, including manual DB edits, is a change."""
    counts = {"added": 0, "changed": 0, "unchanged": 0}
    for p in programs:
        new_hash = p.record_hash
        vals = tuple(p.row()[f] for f in PROGRAM_FIELDS)
        existing = load_existing(conn, p.source_connector, p.source_id)
        if existing is None:
            cur = conn.execute(
                f"INSERT INTO program ({_COLS}, slug, record_hash, first_seen, last_seen, last_changed)"
                f" VALUES ({_PLACEHOLDERS}, ?, ?, ?, ?, ?)",
                vals + (p.slug, new_hash, now, now, now),
            )
            pid = cur.lastrowid
            _write_junctions(conn, pid, p)
            _log_change(conn, run_id, pid, "added", None, new_hash, None, now)
            counts["added"] += 1
            continue

        pid = existing["id"]
        # Compare columns, not just the stored hash: a row edited by hand in SQLite keeps its old
        # hash, and the next run must reconcile it back to what the source says.
        fields = changed_fields(existing, p)
        if not fields:
            conn.execute("UPDATE program SET last_seen = ?, record_hash = ? WHERE id = ?", (now, new_hash, pid))
            counts["unchanged"] += 1
            continue

        conn.execute(
            f"UPDATE program SET {_SET}, slug = ?, record_hash = ?, last_seen = ?, last_changed = ? WHERE id = ?",
            vals + (p.slug, new_hash, now, now, pid),
        )
        _write_junctions(conn, pid, p)
        _log_change(conn, run_id, pid, "changed", existing["record_hash"], new_hash, fields, now)
        counts["changed"] += 1
    conn.commit()
    return counts


Resolver = Callable[[str], dict[str, Any] | None]


def mark_missing(
    conn: sqlite3.Connection,
    run_id: int,
    connector: str,
    seen_source_ids: set[str],
    resolve: Resolver,
    now: str,
) -> int:
    """For every non-closed program of this connector that the source did not return this run,
    ask the connector what it knows (resolve -> {'status': ..., 'closes_at': ...} or None).
    None means the source could not be read: status becomes 'unknown'. Logs a 'missing' change
    only when something actually changed."""
    rows = conn.execute(
        "SELECT source_id FROM program WHERE source_connector = ? AND status != 'closed'", (connector,)
    ).fetchall()
    n = 0
    for (source_id,) in rows:
        if source_id in seen_source_ids:
            continue
        existing = load_existing(conn, connector, source_id)
        assert existing is not None
        update = resolve(source_id) or {"status": "unknown"}
        current = Program.from_row(existing)
        proposed = current.model_copy(update={k: v for k, v in update.items() if k in ("status", "closes_at")})
        fields = changed_fields(existing, proposed)
        if not fields:
            continue
        new_hash = proposed.record_hash
        conn.execute(
            "UPDATE program SET status = ?, closes_at = ?, record_hash = ?, last_changed = ? WHERE id = ?",
            (proposed.status, proposed.row()["closes_at"], new_hash, now, existing["id"]),
        )
        _log_change(conn, run_id, existing["id"], "missing", existing["record_hash"], new_hash, fields, now)
        n += 1
    conn.commit()
    return n
