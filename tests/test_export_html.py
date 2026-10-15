"""Static page export: the v_municipal_page view and the HTML renderer, on an in-memory database."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

import db
from pipeline.models import ALL_APPLICANT_TYPES, ApplicantTag, CategoryTag, Program
from pipeline.upsert import upsert
from scripts import export_html

LOCAL = [ApplicantTag(value="municipality", source_code="02"), ApplicantTag(value="county", source_code="01")]
EVERYONE = [ApplicantTag(value=t, source_code=f"{i:02d}") for i, t in enumerate(ALL_APPLICANT_TYPES)]
NOW = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def prog(source_id, name, **over) -> Program:
    base = dict(
        source_connector="grants_gov", source_id=source_id, source_url=f"https://x/{source_id}", name=name,
        level="federal", jurisdiction="US", administering_agency="Agency X", agency_code="X", funding_type="grant",
        funding_source="direct", status="open", applicant_types=LOCAL,
        categories=[CategoryTag(value="water", source_code="ENV")],
    )
    base.update(over)
    return Program(**base)


PROGRAMS = [
    prog("1", "Wildlife Crossings Pilot", closes_at=date(2099, 3, 1), amount_max=2_000_000, match_required=True,
         summary="Crossings for critters", eligibility_text="Units of local government <may> apply", alns=["20.205", "99.999"]),
    prog("2", "Rolling State Thing", source_connector="md_mht", level="state", jurisdiction="MD",
         administering_agency="Maryland Historical Trust", agency_code="MD-MHT", funding_type="loan",
         rolling=True, closes_at=None, closes_at_text="Loan applications are accepted year-round.",
         applicant_types=[ApplicantTag(value="municipality", source_code="99")], categories=[]),
    prog("3", "Early-Onset Cancers (R01 Clinical Trial Optional)", agency_code="HHS-NIH11", applicant_types=EVERYONE,
         categories=[CategoryTag(value="health", source_code="HL")]),
    prog("4", "Closed One", status="closed"),
    prog("5", "<script>alert(1)</script> Resilience", closes_at=date(2099, 1, 1),
         eligibility_text="local governments"),
    prog("20.205", "Highway Planning and Construction", source_connector="sam_assistance_listings", status="unknown",
         applicant_types=[], categories=[], alns=["20.205"]),
]


@pytest.fixture(scope="module")
def conn():
    c = db.connect(":memory:")
    db.apply_schema(c)
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('grants_gov', ?, ?, 'ok')", (NOW, NOW))
    c.execute("INSERT INTO run (connector, started_at, status) VALUES ('md_mht', ?, 'failed')", (NOW,))
    upsert(c, 1, PROGRAMS, NOW)
    yield c
    c.close()


def test_view_rows_and_order(conn):
    rows = export_html.load(conn)
    assert [r["name"] for r in rows] == [
        "<script>alert(1)</script> Resilience",   # likely, closes first
        "Wildlife Crossings Pilot",               # likely
        "Rolling State Thing",                    # possible, no close date
    ]
    wc = rows[1]
    assert wc["municipal_tier"] == "likely"
    assert wc["categories"] == "water" and wc["applicant_types"] == "county, municipality"
    assert wc["listings"] == "20.205 · Highway Planning and Construction"   # 99.999 has no listing, so no line
    assert wc["days_since_first_seen"] == 0 and wc["days_since_changed"] == 0
    assert rows[2]["listings"] is None and rows[2]["rolling"] == 1
    assert export_html.excluded_unlikely(conn) == 1


def test_freshness_reports_last_ok_run(conn):
    assert export_html.freshness(conn) == [("grants_gov", NOW), ("md_mht", None)]


def test_render(conn):
    page = export_html.render(
        export_html.load(conn), generated_at=NOW, freshness=export_html.freshness(conn),
        excluded_unlikely=export_html.excluded_unlikely(conn),
    )
    assert "Wildlife Crossings Pilot" in page and "Rolling State Thing" in page
    assert "Early-Onset Cancers" not in page and "Closed One" not in page
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "&lt;may&gt; apply" in page                              # eligibility text is escaped, not dropped
    assert "20.205 · Highway Planning and Construction" in page
    assert "$2,000,000" in page
    assert 'class="badge new"' in page
    assert 'Likely (2)' in page and 'Possible (1)' in page
    assert "1 further open records" in page
    assert "Maryland Historical Trust: no successful run yet" in page
    assert "last successful run " + NOW[:10] in page
    assert "http://" not in page.replace("https://x/", "") and "cdn" not in page   # self-contained


def test_write(conn, tmp_path):
    out, n = export_html.write(conn, tmp_path / "sub" / "page.html")
    assert n == 3 and out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")
