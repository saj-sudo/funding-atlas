"""Navigator site: the views of migrations 0005 and 0006, the JSON shaping, and the rendered pages, on an
in-memory database. No network, no browser."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta

import pytest

import db
from pipeline.models import ALL_APPLICANT_TYPES, ApplicantTag, CategoryTag, Program
from pipeline.upsert import upsert
from scripts import build_site

LOCAL = [ApplicantTag(value="municipality", source_code="02"), ApplicantTag(value="county", source_code="01")]
EVERYONE = [ApplicantTag(value=t, source_code=f"{i:02d}") for i, t in enumerate(ALL_APPLICANT_TYPES)]
NOW = datetime.now(UTC)
TODAY = NOW.strftime("%Y-%m-%d")
T1 = (NOW - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")   # first full read, three weeks ago
T2 = (NOW - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")    # a later run, two days ago
GEN = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


def prog(source_id, name, **over) -> Program:
    base = dict(
        source_connector="grants_gov", source_id=source_id, source_url=f"https://x/{source_id}", name=name,
        level="federal", jurisdiction="US", administering_agency="Agency X", agency_code="X", funding_type="grant",
        funding_source="direct", status="open", applicant_types=LOCAL,
        categories=[CategoryTag(value="water", source_code="ENV")],
    )
    base.update(over)
    return Program(**base)


SOON = (NOW + timedelta(days=12)).date()
FIRST_RUN = [
    prog("1", "Wildlife Crossings Pilot", closes_at=SOON, amount_max=2_000_000, match_required=True,
         summary="Crossings for critters", eligibility_text="Units of local government <may> apply",
         alns=["20.205", "99.999"], external_number="DOT-001"),
    prog("2", "Rolling State Thing", source_connector="md_mht", level="state", jurisdiction="MD",
         administering_agency="Maryland Historical Trust", agency_code="MD-MHT", funding_type="loan",
         rolling=True, closes_at=None, closes_at_text="Loan applications are accepted year-round.",
         applicant_types=[ApplicantTag(value="municipality", source_code="99")], categories=[]),
    prog("3", "Early-Onset Cancers (R01 Clinical Trial Optional)", agency_code="HHS-NIH11", applicant_types=EVERYONE,
         categories=[CategoryTag(value="health", source_code="HL")]),
    prog("4", "Will Close Later", source_connector="md_dhcd", level="state", jurisdiction="MD",
         administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments"),
    prog("5", "<script>alert(1)</script> Resilience", closes_at=date(2099, 1, 1), eligibility_text="local governments"),
    prog("6", "Virginia Towns Fund", source_connector="va_test", level="state", jurisdiction="VA:Richmond",
         administering_agency="Virginia DHCD", agency_code="VA-DHCD", eligibility_text="towns and cities"),
    prog("20.205", "Highway Planning and Construction", source_connector="sam_assistance_listings", status="unknown",
         applicant_types=[], categories=[], alns=["20.205"]),
    # between rounds: a state round that closed three months ago (listed), one that closed two years ago (too old),
    # and a closed federal notice (never listed: federal rows stay off the appendix)
    prog("8", "Spring Round", source_connector="md_dhcd", level="state", jurisdiction="MD",
         administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
         status="closed", closes_at=(NOW - timedelta(days=90)).date(), closes_at_text="application closed: three months ago"),
    prog("9", "Long Dead Credit", source_connector="md_dhcd", level="state", jurisdiction="MD",
         administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
         status="closed", closes_at=(NOW - timedelta(days=700)).date()),
    prog("10", "Old Notice", status="closed", closes_at=(NOW - timedelta(days=30)).date(), eligibility_text="local governments"),
]
SECOND_RUN = [
    prog("4", "Will Close Later", source_connector="md_dhcd", level="state", jurisdiction="MD",
         administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
         status="closed"),
    prog("7", "Brand New Notice", closes_at=date(2099, 6, 1), eligibility_text="local governments"),
]


@pytest.fixture(scope="module")
def conn():
    c = db.connect(":memory:")
    db.apply_schema(c)
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('grants_gov', ?, ?, 'ok')", (T1, T1))
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_mht', ?, ?, 'ok')", (T1, T1))
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_dhcd', ?, ?, 'ok')", (T1, T1))
    c.execute("INSERT INTO run (connector, started_at, status) VALUES ('va_test', ?, 'failed')", (T1,))
    upsert(c, 1, FIRST_RUN, T1)
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('grants_gov', ?, ?, 'ok')", (T2, T2))
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_dhcd', ?, ?, 'ok')", (T2, T2))
    upsert(c, 5, SECOND_RUN, T2)
    yield c
    c.close()


# ---------- views ----------

def test_navigator_program_covers_every_state_and_matches_the_maryland_page(conn):
    rows = [dict(r) for r in conn.execute("SELECT * FROM v_navigator_program")]
    assert {r["state"] for r in rows} == {None, "MD", "VA"}
    assert "Early-Onset Cancers (R01 Clinical Trial Optional)" not in {r["name"] for r in rows}   # unlikely
    assert "Will Close Later" not in {r["name"] for r in rows}                                   # closed now
    md = [r["id"] for r in conn.execute("SELECT id FROM v_navigator_program WHERE state IS NULL OR state = 'MD'")]
    page = [r["id"] for r in conn.execute("SELECT id FROM v_municipal_page")]
    assert md == page and len(md) == 4
    wc = next(r for r in rows if r["name"] == "Wildlife Crossings Pilot")
    assert wc["alns"] == "20.205, 99.999" and wc["listings"] == "20.205 · Highway Planning and Construction"
    assert wc["slug"].startswith("wildlife-crossings-pilot-grants-gov-")


def test_navigator_change_keeps_the_closed_flip(conn):
    rows = [dict(r) for r in conn.execute("SELECT * FROM v_navigator_change")]
    assert rows[0]["changed_at"] >= rows[-1]["changed_at"]
    flip = next(r for r in rows if r["name"] == "Will Close Later" and r["change_type"] == "changed")
    assert json.loads(flip["changed_fields"])["status"] == {"old": "open", "new": "closed"}
    assert all(r["name"] != "Early-Onset Cancers (R01 Clinical Trial Optional)" for r in rows)


def test_navigator_coverage(conn):
    cov = {r["state"]: dict(r) for r in conn.execute("SELECT * FROM v_navigator_coverage")}
    assert cov["MD"]["n_agencies"] == 2 and cov["MD"]["n_programs"] == 4 and cov["MD"]["n_open_municipal"] == 1
    assert cov["MD"]["n_between_rounds"] == 2 and cov["MD"]["last_ok"] == T2
    assert cov["VA"]["n_programs"] == 1 and cov["VA"]["n_between_rounds"] == 0 and cov["VA"]["last_ok"] is None
    assert "US" not in cov


def test_navigator_between_lists_recent_closed_state_rounds_only(conn):
    rows = [dict(r) for r in conn.execute("SELECT * FROM v_navigator_between")]
    assert [r["name"] for r in rows] == ["Spring Round", "Will Close Later"]       # dated first, then undated
    assert all(r["state"] == "MD" for r in rows)                                   # never a federal row
    assert "Long Dead Credit" not in {r["name"] for r in rows}                      # older than 15 months
    assert "Old Notice" not in {r["name"] for r in rows}                            # federal, closed, recent: still out
    spring = rows[0]
    assert spring["days_since_deadline"] == 90 and spring["last_reopened"] is None and spring["municipal_tier"] == "likely"
    assert rows[1]["closes_at"] is None and rows[1]["days_since_deadline"] is None
    on_page = {r["id"] for r in conn.execute("SELECT id FROM v_navigator_program")}
    assert not on_page & {r["id"] for r in rows}


# ---------- shaping ----------

def test_build_shapes_programs_and_rules(conn):
    site = build_site.build(conn, generated_at=GEN)
    md = site["states"]["MD"]
    names = {p["name"]: p for p in md["programs"]}
    assert set(names) == {"Wildlife Crossings Pilot", "Rolling State Thing", "<script>alert(1)</script> Resilience", "Brand New Notice"}
    wc = names["Wildlife Crossings Pilot"]
    assert wc["is_new"] is False                      # first seen on the connector's first run: not "new"
    assert names["Brand New Notice"]["is_new"] is True   # seen on a later run, within the window
    assert wc["days_to_close"] == 12 and wc["match_required"] is True and wc["rolling"] is None
    assert wc["applicant_types"] == ["county", "municipality"] and wc["categories"] == ["water"]
    assert wc["alns"] == ["20.205", "99.999"] and wc["listings"] == [{"aln": "20.205", "name": "Highway Planning and Construction"}]
    assert wc["number"] == "DOT-001" and wc["summary"] == "Crossings for critters"
    rs = names["Rolling State Thing"]
    assert rs["rolling"] is True and rs["closes_at"] is None and rs["closes_text"].startswith("Loan applications")
    assert rs["state"] == "MD" and rs["listings"] == [] and rs["amount_max"] is None
    assert md["coverage"]["state"]["agencies"] == 2 and md["coverage"]["state"]["open"] == 1
    assert md["coverage"]["state"]["between"] == 2 and md["rules"]["between_months"] == build_site.BETWEEN_MONTHS
    assert [p["name"] for p in md["between"]] == ["Spring Round", "Will Close Later"]
    spring = md["between"][0]
    assert spring["days_since_deadline"] == 90 and spring["days_to_close"] == -90 and spring["last_reopened"] is None
    assert spring["closes_text"] == "application closed: three months ago" and spring["status"] == "closed"
    assert md["coverage"]["federal"]["open"] == 3
    assert md["excluded_unlikely"] == 1
    assert [s["connector"] for s in md["coverage"]["state"]["sources"]] == ["md_dhcd", "md_mht"]

    va = site["states"]["VA"]
    assert {p["name"] for p in va["programs"]} == {"Wildlife Crossings Pilot", "<script>alert(1)</script> Resilience", "Brand New Notice", "Virginia Towns Fund"}
    assert va["coverage"]["state"]["last_ok"] is None and va["coverage"]["state"]["programs"] == 1
    assert va["between"] == [] and va["coverage"]["state"]["between"] == 0
    assert site["states"]["WY"]["coverage"]["state"] is None
    assert len(site["states"]["WY"]["programs"]) == 3 and site["states"]["WY"]["between"] == []


def test_build_shapes_changes(conn):
    site = build_site.build(conn, generated_at=GEN)
    md = site["states"]["MD"]
    flip = next(c for c in md["changes"] if c["name"] == "Will Close Later" and c["type"] == "changed")
    assert flip["status_flip"] is True and flip["listed"] is True        # closed, but on the page under "between rounds"
    assert flip["fields"] == [{"field": "status", "old": "open", "new": "closed"}]
    added = next(c for c in md["changes"] if c["name"] == "Brand New Notice")
    assert added["type"] == "added" and added["listed"] is True and added["fields"] == []
    assert all(c["state"] in (None, "MD") for c in md["changes"])
    assert sum(1 for c in md["changes"] if c["state"] == "MD") == 5    # four added + the flip, never starved by federal rows
    assert md["changes"][0]["at"] >= md["changes"][-1]["at"]
    assert len(site["index"]["changes"]) <= build_site.INDEX_FEED_N
    assert site["index"]["federal"]["new"] == 1 and site["index"]["federal"]["closing_soon"] == 1


def test_index_states_and_tile_grid(conn):
    site = build_site.build(conn, generated_at=GEN)
    states = site["index"]["states"]
    assert len(states) == 51 and len({s["code"] for s in states}) == 51
    assert len({(s["row"], s["col"]) for s in states}) == 51          # no two tiles on one cell
    md = next(s for s in states if s["code"] == "MD")
    assert md["programs"] == 4 and md["open"] == 1 and md["agencies"] == 2 and md["between"] == 2
    wy = next(s for s in states if s["code"] == "WY")
    assert wy["programs"] == 0 and wy["between"] == 0


# ---------- rendering ----------

def test_embed_json_is_script_safe():
    text = build_site.embed_json({"a": "</script><b> "})
    assert "</" not in text and "\\u2028" in text
    assert json.loads(text) == {"a": "</script><b> "}


def test_write_site(conn, tmp_path):
    out, counts = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    assert (out / ".nojekyll").exists() and (out / "index.html").exists()
    assert len(counts) == 51 and counts["MD"] == 4 and counts["VA"] == 4 and counts["WY"] == 3
    page = (out / "md" / "index.html").read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>")
    assert "<script>alert(1)</script>" not in page
    data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1))
    assert data["state"] == {"code": "MD", "name": "Maryland"} and len(data["programs"]) == 4 and len(data["between"]) == 2
    assert 'id="between-list"' in page and 'id="between-toggle"' in page
    assert "&lt;may&gt;" in json.dumps(data) or "<may>" in json.dumps(data)   # verbatim text survives round trip
    # self-contained: nothing loaded from anywhere
    body = page.replace("https://x/", "")
    assert "<script src" not in body and "<link rel=\"stylesheet\"" not in body and "@import" not in body
    assert "url(http" not in body and "cdn" not in body
    index = (out / "index.html").read_text(encoding="utf-8")
    assert 'data-page="index"' in index and "Funding Atlas" in index
    # rebuilding wipes stale files
    (out / "stale.txt").write_text("x")
    build_site.write(conn, out, generated_at=GEN)
    assert not (out / "stale.txt").exists()


def test_a_reopening_is_observed_from_the_change_log(conn):
    """Last in the file on purpose: it adds a third run to the shared fixture."""
    t3 = (NOW - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    run3 = conn.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_dhcd', ?, ?, 'ok')", (t3, t3)).lastrowid
    reopened = prog("8", "Spring Round", source_connector="md_dhcd", level="state", jurisdiction="MD",
                    administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
                    status="open", closes_at=(NOW + timedelta(days=60)).date(), closes_at_text="application closes in two months")
    upsert(conn, run3, [reopened], t3)
    assert "Spring Round" not in {r["name"] for r in conn.execute("SELECT name FROM v_navigator_between")}
    assert "Spring Round" in {r["name"] for r in conn.execute("SELECT name FROM v_navigator_program")}
    # close it again: the appendix now carries the observed reopening date, from the log, not from a calendar
    t4 = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    run4 = conn.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_dhcd', ?, ?, 'ok')", (t4, t4)).lastrowid
    closed = prog("8", "Spring Round", source_connector="md_dhcd", level="state", jurisdiction="MD",
                  administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
                  status="closed", closes_at=(NOW - timedelta(days=1)).date())
    upsert(conn, run4, [closed], t4)
    row = dict(conn.execute("SELECT * FROM v_navigator_between WHERE name = 'Spring Round'").fetchone())
    assert row["last_reopened"] == t3 and row["days_since_deadline"] == 1
    site = build_site.build(conn, generated_at=GEN)
    spring = next(p for p in site["states"]["MD"]["between"] if p["name"] == "Spring Round")
    assert spring["last_reopened"] == t3


def test_placeholder_dates_are_flagged_not_dropped():
    from datetime import date as _date

    from scripts.build_site import is_placeholder

    today = _date(2026, 10, 18)
    assert is_placeholder("2035-12-31", today) is True and is_placeholder("2999-07-01", today) is True
    assert is_placeholder("2031-10-18", today) is False and is_placeholder("2031-10-19", today) is True
    assert is_placeholder("2027-06-30", today) is False and is_placeholder(None, today) is False
    assert is_placeholder("not a date", today) is False

