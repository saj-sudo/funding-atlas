"""Pipeline tests on an in-memory SQLite database. No network, no connector."""

from __future__ import annotations

import json
from datetime import date

import pytest

import db
from pipeline.diff import render
from pipeline.models import ApplicantTag, CategoryTag, Program
from pipeline.upsert import load_existing, mark_missing, upsert


def make_program(**overrides) -> Program:
    base = dict(
        source_connector="test",
        source_id="1",
        source_url="https://example.org/1",
        name="Test Program",
        level="federal",
        jurisdiction="US",
        funding_type="grant",
        funding_source="direct",
        status="open",
        closes_at=date(2026, 12, 1),
        applicant_types=[ApplicantTag(value="municipality", source_code="02"),
                         ApplicantTag(value="county", source_code="01")],
        categories=[CategoryTag(value="water", source_code="ENV")],
        alns=["93.243"],
    )
    base.update(overrides)
    return Program(**base)


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.apply_schema(c)
    yield c
    c.close()


def new_run(conn, n: int) -> int:
    cur = conn.execute("INSERT INTO run (connector, started_at, status) VALUES ('test', ?, 'ok')", (f"2026-10-{n:02d}T00:00:00Z",))
    return cur.lastrowid


def test_hash_is_order_independent():
    a = make_program()
    b = make_program(applicant_types=list(reversed(a.applicant_types)))
    assert a.record_hash == b.record_hash
    assert make_program(closes_at=date(2027, 1, 1)).record_hash != a.record_hash


def test_add_then_unchanged_then_changed(conn):
    r1 = new_run(conn, 1)
    counts = upsert(conn, r1, [make_program(), make_program(source_id="2", name="Other")], "2026-10-01T00:00:00Z")
    assert counts == {"added": 2, "changed": 0, "unchanged": 0}
    assert conn.execute("SELECT COUNT(*) FROM program_applicant_type").fetchone()[0] == 4

    r2 = new_run(conn, 2)
    counts = upsert(conn, r2, [make_program(), make_program(source_id="2", name="Other")], "2026-10-02T00:00:00Z")
    assert counts == {"added": 0, "changed": 0, "unchanged": 2}
    row = load_existing(conn, "test", "1")
    assert row["first_seen"] == "2026-10-01T00:00:00Z"
    assert row["last_seen"] == "2026-10-02T00:00:00Z"
    assert row["last_changed"] == "2026-10-01T00:00:00Z"
    assert conn.execute("SELECT COUNT(*) FROM program_change WHERE run_id = ?", (r2,)).fetchone()[0] == 0

    r3 = new_run(conn, 3)
    changed = make_program(closes_at=date(2027, 1, 15), alns=["93.243", "93.244"])
    counts = upsert(conn, r3, [changed], "2026-10-03T00:00:00Z")
    assert counts["changed"] == 1
    change = conn.execute("SELECT * FROM program_change WHERE run_id = ?", (r3,)).fetchone()
    fields = json.loads(change["changed_fields"])
    assert set(fields) == {"closes_at", "alns"}
    assert fields["closes_at"] == {"old": "2026-12-01", "new": "2027-01-15"}
    assert load_existing(conn, "test", "1")["last_changed"] == "2026-10-03T00:00:00Z"
    assert "closes_at 2026-12-01 → 2027-01-15" in render(conn, r3)


def test_missing_record_is_resolved(conn):
    r1 = new_run(conn, 1)
    upsert(conn, r1, [make_program(), make_program(source_id="2", name="Stays")], "2026-10-01T00:00:00Z")

    r2 = new_run(conn, 2)
    upsert(conn, r2, [make_program(source_id="2", name="Stays")], "2026-10-02T00:00:00Z")
    calls = []

    def resolve(source_id):
        calls.append(source_id)
        return {"status": "closed", "closes_at": date(2026, 9, 30)}

    n = mark_missing(conn, r2, "test", {"2"}, resolve, "2026-10-02T00:00:00Z")
    assert n == 1 and calls == ["1"]
    row = load_existing(conn, "test", "1")
    assert row["status"] == "closed" and row["closes_at"] == "2026-09-30"
    report = render(conn, r2)
    assert "Status transitions (1)" in report and "status open → closed" in report

    # Already closed: not re-resolved. Reappearing later with status open is detected as a change.
    r3 = new_run(conn, 3)
    assert mark_missing(conn, r3, "test", {"2"}, lambda s: pytest.fail("should not resolve"), "x") == 0
    counts = upsert(conn, r3, [make_program()], "2026-10-03T00:00:00Z")
    assert counts["changed"] == 1
    assert load_existing(conn, "test", "1")["status"] == "open"


def test_unresolvable_missing_becomes_unknown(conn):
    r1 = new_run(conn, 1)
    upsert(conn, r1, [make_program()], "2026-10-01T00:00:00Z")
    r2 = new_run(conn, 2)
    assert mark_missing(conn, r2, "test", set(), lambda s: None, "2026-10-02T00:00:00Z") == 1
    assert load_existing(conn, "test", "1")["status"] == "unknown"


def test_view_answers_the_municipal_question(conn):
    r1 = new_run(conn, 1)
    upsert(conn, r1, [
        make_program(),
        make_program(source_id="3", name="Closed", status="closed"),
        make_program(source_id="4", name="Nonprofit only",
                     applicant_types=[ApplicantTag(value="nonprofit", source_code="12")]),
    ], "2026-10-01T00:00:00Z")
    names = [r[0] for r in conn.execute("SELECT name FROM v_open_for_municipalities")]
    assert names == ["Test Program"]


def test_from_row_round_trips(conn):
    r1 = new_run(conn, 1)
    p = make_program(match_required=True, eligibility_structured={"a": 1})
    upsert(conn, r1, [p], "2026-10-01T00:00:00Z")
    rebuilt = Program.from_row(load_existing(conn, "test", "1"))
    assert rebuilt.record_hash == p.record_hash
