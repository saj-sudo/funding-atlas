"""Which commits on main changed how each connector reads its source (migration 0010, roadmap 13.15).

A connector's reading code is its module plus every module of this repository it imports, followed through the
imports, plus the pipeline's own upsert and model code (they decide what counts as a change). `refresh` asks git
for the first-parent commits on the given ref that touched any of those files and stores them in code_release.
Facts from git only: no file, no row.
"""

from __future__ import annotations

import ast
import sqlite3
import subprocess
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
ALWAYS = ("pipeline/upsert.py", "pipeline/models.py")   # run.py only lists the connectors: not reading code
PACKAGES = ("connectors", "pipeline")


def _local_imports(path: Path) -> set[Path]:
    """Repository modules a file imports (connectors.*, pipeline.*), as paths."""
    out: set[Path] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
            names += [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        for name in names:
            if name.split(".")[0] not in PACKAGES:
                continue
            candidate = ROOT / (name.replace(".", "/") + ".py")
            if candidate.exists():
                out.add(candidate)
    return out


def reading_files(module: ModuleType) -> list[str]:
    """The files that decide how this connector reads, relative to the repository root, sorted."""
    start = Path(module.__file__).resolve()
    seen: set[Path] = set()
    todo = [start]
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        todo += [q for q in _local_imports(p) if q not in seen]
    files = {str(p.relative_to(ROOT)) for p in seen} | set(ALWAYS)
    return sorted(f for f in files if (ROOT / f).exists())


def commits_touching(files: list[str], ref: str = "HEAD") -> list[tuple[str, str]]:
    """(sha, committer time in UTC ISO) for every first-parent commit on `ref` touching any of `files`."""
    out = subprocess.run(
        ["git", "log", "--first-parent", "--format=%H%x09%cI", ref, "--", *files],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        sha, when = line.split("\t")
        rows.append((sha, _utc(when)))
    return rows


def _utc(iso: str) -> str:
    from datetime import UTC, datetime
    return datetime.fromisoformat(iso).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def refresh(conn: sqlite3.Connection, connectors: dict[str, ModuleType], ref: str = "HEAD") -> int:
    """Replace code_release with what git says now. Returns the number of rows written."""
    rows = []
    for name, module in connectors.items():
        for sha, when in commits_touching(reading_files(module), ref):
            rows.append((name, sha, when))
    conn.execute("DELETE FROM code_release")
    conn.executemany("INSERT OR IGNORE INTO code_release (connector, sha, released_at) VALUES (?, ?, ?)", rows)
    conn.commit()
    return len(rows)
