"""Municipal relevance view: rule-by-rule checks on synthetic programs."""

from __future__ import annotations

import pytest

import db
from pipeline.models import ALL_APPLICANT_TYPES, ApplicantTag, CategoryTag, Program
from pipeline.upsert import upsert

EVERYONE = [ApplicantTag(value=t, source_code=c) for t, c in zip(ALL_APPLICANT_TYPES, [f"{i:02d}" for i in range(13)], strict=True)]
LOCAL = [ApplicantTag(value="municipality", source_code="02"), ApplicantTag(value="county", source_code="01"),
         ApplicantTag(value="state", source_code="00"), ApplicantTag(value="tribe", source_code="07")]


def prog(source_id, name, agency="X", applicant_types=LOCAL, categories=(), eligibility_text=None, summary=None):
    return Program(
        source_connector="test", source_id=source_id, source_url=f"https://x/{source_id}", name=name,
        level="federal", jurisdiction="US", agency_code=agency, funding_source="direct", status="open",
        applicant_types=applicant_types, categories=[CategoryTag(value=c, source_code=c) for c in categories],
        eligibility_text=eligibility_text, summary=summary,
    )


CASES = [
    ("nih", prog("1", "Early-Onset Cancers (R01 Clinical Trial Optional)", "HHS-NIH11", EVERYONE, ["health"],
                 eligibility_text="Refer to Section III"), "unlikely"),
    ("bja", prog("2", "BJA FY 2026 Rural Violent Crime Reduction", "USDOJ-OJP-BJA", EVERYONE, ["public_safety"],
                 eligibility_text="Units of local government and federally recognized tribes"), "likely"),
    ("dot", prog("3", "Wildlife Crossings Pilot Program", "DOT-FHWA", LOCAL, ["transportation"]), "likely"),
    ("cdc", prog("4", "Chronic Disease Education and Awareness", "HHS-CDC-NCCDPHP", EVERYONE, ["health"],
                 summary="Awareness campaigns for populations at risk"), "unlikely"),
    ("doe", prog("5", "Notice of Intent: Domestic Infrastructure", "DOE-GFO", [ApplicantTag(value="municipality", source_code="99")], ["other"]), "possible"),
    ("rfi", prog("6", "Request for Information - Investor Interest", "DOE-NETL", LOCAL, ["energy"]), "unlikely"),
    ("nsf", prog("7", "Engineering (ENG): Civil Innovation", "NSF", [ApplicantTag(value="municipality", source_code="99")]), "unlikely"),
    ("fy", prog("8", "Resilience Grants (FY26 Round 2)", "DHS-FEMA", EVERYONE, ["infrastructure"]), "possible"),
    ("capacity", prog("9", "Capacity Building for Electricity Markets", "DOE-GFO", EVERYONE, ["energy"]), "possible"),
    ("dos", prog("10", "Promoting Human Rights for Vulnerable Children in Haut-Katanga", "DOS-COD", EVERYONE, ["other"],
                 eligibility_text="Local governments and NGOs"), "unlikely"),
    ("baa", prog("11", "NRL Long Range Broad Agency Announcement (BAA)", "DOD-ONR-NRL", [ApplicantTag(value="municipality", source_code="99")]), "unlikely"),
    ("stale", prog("12", "Stale But Still Posted", "HUD", LOCAL, ["housing"], eligibility_text="units of general local government"), "likely"),
]
CASES[-1][1].closes_at = __import__("datetime").date(2021, 8, 4)


@pytest.fixture(scope="module")
def conn():
    c = db.connect(":memory:")
    db.apply_schema(c)
    c.execute("INSERT INTO run (connector, started_at, status) VALUES ('test', 'x', 'ok')")
    upsert(c, 1, [p for _, p, _ in CASES], "2026-10-01T00:00:00Z")
    yield c
    c.close()


@pytest.mark.parametrize("label, program, tier", CASES, ids=[c[0] for c in CASES])
def test_tier(conn, label, program, tier):
    row = conn.execute(
        "SELECT r.* FROM v_municipal_relevance r JOIN program p ON p.id = r.program_id WHERE p.source_id = ?",
        (program.source_id,),
    ).fetchone()
    assert row["municipal_tier"] == tier, dict(row)


def test_word_boundaries_do_not_match_capacity_or_electricity(conn):
    row = conn.execute("SELECT local_gov_wording FROM v_municipal_relevance r JOIN program p ON p.id = r.program_id WHERE p.source_id = '9'").fetchone()
    assert row[0] == 0


def test_fy_in_title_is_not_a_research_code(conn):
    row = conn.execute("SELECT research_notice FROM v_municipal_relevance r JOIN program p ON p.id = r.program_id WHERE p.source_id = '8'").fetchone()
    assert row[0] == 0


def test_stale_posted_record_is_excluded_from_open_view(conn):
    assert conn.execute("SELECT municipal_tier FROM v_municipal_relevance r JOIN program p ON p.id = r.program_id WHERE p.source_id = '12'").fetchone()[0] == "likely"
    assert conn.execute("SELECT COUNT(*) FROM v_open_for_municipalities WHERE name = 'Stale But Still Posted'").fetchone()[0] == 0


def test_open_view_orders_by_tier(conn):
    tiers = [r[0] for r in conn.execute("SELECT municipal_tier FROM v_open_for_municipalities")]
    assert tiers == sorted(tiers, key={"likely": 0, "possible": 1, "unlikely": 2}.get)
    assert tiers[0] == "likely"


def test_migration_is_recorded_and_rerun_safe(conn):
    assert db.schema_version(conn) == db.migrations()[-1][0]
    db.apply_schema(conn)  # second call must not fail or duplicate
    assert conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 1 + len(db.migrations())
