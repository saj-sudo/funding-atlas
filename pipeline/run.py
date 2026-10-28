"""Run one connector end to end: fetch -> store raw -> normalize -> upsert -> resolve missing."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from types import ModuleType

from connectors import (
    ca_grants,
    grants_gov,
    md_commerce,
    md_dhcd,
    md_dnr,
    md_mea,
    md_mht,
    pa_grants,
    sam_assistance_listings,
    wv_grants,
)
from pipeline.upsert import mark_missing, upsert

CONNECTORS: dict[str, ModuleType] = {
    "grants_gov": grants_gov,
    "sam_assistance_listings": sam_assistance_listings,
    "md_dhcd": md_dhcd,
    "md_commerce": md_commerce,
    "md_mht": md_mht,
    "md_mea": md_mea,
    "md_dnr": md_dnr,
    "pa_grants": pa_grants,
    "wv_grants": wv_grants,
    "ca_grants": ca_grants,
}


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_prior(conn: sqlite3.Connection, name: str) -> dict[str, dict]:
    """Last stored raw payload per source record, so a connector can skip refetching what has not moved."""
    return {
        r["source_id"]: json.loads(r["payload"])
        for r in conn.execute("SELECT source_id, payload FROM raw_record WHERE source_connector = ?", (name,))
    }


def run_connector(name: str, conn: sqlite3.Connection, limit: int | None = None) -> int:
    """Returns the run id. With `limit`, the missing-record check is skipped: a partial fetch
    says nothing about what disappeared."""
    connector = CONNECTORS[name]
    now = utcnow()
    cur = conn.execute(
        "INSERT INTO run (connector, started_at, status) VALUES (?, ?, 'running')", (name, now)
    )
    run_id = cur.lastrowid
    conn.commit()
    try:
        raws = connector.fetch(limit=limit, prior=load_prior(conn, name))
        conn.executemany(
            "INSERT INTO raw_record (source_connector, source_id, fetched_at, payload) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(source_connector, source_id) DO UPDATE SET fetched_at = excluded.fetched_at,"
            " payload = excluded.payload",
            [(r.source_connector, r.source_id, now, json.dumps(r.payload, ensure_ascii=False)) for r in raws],
        )
        programs = [connector.normalize(r) for r in raws]
        counts = upsert(conn, run_id, programs, now)
        missing = 0
        if limit is None:
            seen = {p.source_id for p in programs}
            missing = mark_missing(conn, run_id, name, seen, connector.resolve_missing, now)
        conn.execute(
            "UPDATE run SET finished_at = ?, status = 'ok', fetched_count = ?, added_count = ?,"
            " changed_count = ?, missing_count = ? WHERE id = ?",
            (utcnow(), len(raws), counts["added"], counts["changed"], missing, run_id),
        )
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - record the failure, then re-raise
        conn.execute(
            "UPDATE run SET finished_at = ?, status = 'failed', error = ? WHERE id = ?",
            (utcnow(), f"{type(exc).__name__}: {exc}", run_id),
        )
        conn.commit()
        raise
    return run_id
