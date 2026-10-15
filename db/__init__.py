"""SQLite access for funding-atlas. The schema lives in schema.sql; migrations are numbered SQL
files in migrations/ applied in order on top of it. Keep SQL visible."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
SCHEMA_PATH = HERE / "schema.sql"
MIGRATIONS_DIR = HERE / "migrations"
DEFAULT_DB = "atlas.db"


def _regexp(pattern: str, value: object) -> bool:
    """SQL `value REGEXP pattern` (Python re syntax; use (?i) for case-insensitive)."""
    if value is None:
        return False
    return re.search(pattern, str(value)) is not None


def connect(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open a connection with foreign keys on, dict-style rows, and REGEXP available in SQL."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("REGEXP", 2, _regexp, deterministic=True)
    return conn


def migrations() -> list[tuple[int, Path]]:
    out = []
    for p in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = re.match(r"(\d+)_", p.name)
        if m:
            out.append((int(m.group(1)), p))
    return out


def apply_schema(conn: sqlite3.Connection) -> None:
    """Create the base schema, then apply every migration not yet recorded in schema_version.
    schema.sql is idempotent (IF NOT EXISTS); migrations must be too, or must be guarded here."""
    conn.executescript(SCHEMA_PATH.read_text())
    applied = {r[0] for r in conn.execute("SELECT version FROM schema_version")}
    for version, path in migrations():
        if version in applied:
            continue
        conn.executescript(path.read_text())
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()


def schema_version(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return row["v"] if row else None
