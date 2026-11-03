"""MDE (MWIFA) connector tests: the index table and banner, the banner-first status rules, the Purpose-cell applicants,
and the seven saved payloads (never the network)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import maryland_sharepoint as sp
from connectors import md_mde as md
from pipeline.models import RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "md_mde"
TODAY = date(2026, 11, 3)

WQRLF = "programs/water/wqfa/pages/water_quality_fund.aspx"
DWRLF = "programs/water/wqfa/pages/drinking_water_fund.aspx"
WATER_SUPPLY = "programs/water/wqfa/pages/wqfa_ws.aspx"
BRF_WASTEWATER = "programs/water/wqfa/pages/wqfa_enr.aspx"
SUPPLEMENTAL = "programs/water/wqfa/pages/index.aspx"
SEPTIC = "programs/water/bayrestorationfund/onsitedisposalsystems/pages/index.aspx"
CFMGP = "programs/water/stormwatermanagementprogram/pages/floodmgmt.aspx"
BANNER = "MWIFA's funding solicitation is currently closed. Applications will reopen in December 2026."


def payload(source_id: str) -> dict:
    return json.loads((FIXTURES / f"{sp.fixture_name(source_id)}.json").read_text())


def normalize(source_id: str, today: date = TODAY, **overrides):
    p = {**payload(source_id), **overrides}
    return md.normalize(RawRecord(source_connector=md.CONNECTOR, source_id=source_id, payload=p), today=today)


def index() -> dict:
    return json.loads((FIXTURES / "index__programs__water__wqfa__pages__index.json").read_text())


def section(body: str, h1: str = "Some Program") -> str:
    return (f'<section class="mdgov-section"><div id="ctl00_PlaceHolderMain_editmodepanel2"><h1>{h1}</h1></div>'
            f'<div id="ctl00_PlaceHolderMain_RichHtmlField1__ControlWrapper_RichHtmlField" class="ms-rtestate-field">'
            f'{body}</div></section>')


# ---------- enumeration ----------

def test_index_rows_seven_with_one_unlinked_and_the_banner():
    data = md.index_rows(index()["url"], index()["main_html"])
    assert data["banner"] == BANNER
    rows = data["rows"]
    assert [r["title"] for r in rows] == [
        "Water Quality Revolving Loan Program (WQRLF)", "Drinking Water Revolving Loan Program (DWRLF)",
        "Water Supply Assistance Grant Program", "Bay Restoration Fund - Wastewater Grant Program",
        "Supplemental Assistance Grant Program", "Bay Restoration Fund - Septic System Upgrade Program",
        "Comprehensive Flood Management Grant Program",
    ]
    assert rows[4]["href"] is None and rows[0]["href"] == "https://mde.maryland.gov/programs/water/WQFA/Pages/water_quality_fund.aspx"
    assert rows[0]["purpose"].startswith("Provides low-interest loans to local governments")


def test_entries_key_the_unlinked_row_to_the_index_page():
    entries = md.entries_for(index()["url"], index()["main_html"])
    assert len(entries) == 7 and SUPPLEMENTAL in entries and WQRLF in entries
    assert entries[SUPPLEMENTAL]["url"] == index()["url"] and entries[SUPPLEMENTAL]["row"]["linked"] is False
    assert entries[WQRLF]["row"] == {"title": "Water Quality Revolving Loan Program (WQRLF)", "purpose": entries[WQRLF]["row"]["purpose"],
                                      "banner": BANNER, "linked": True}


@pytest.mark.parametrize("body", ["<p>no table</p>", "<table><tr><th>Other</th><th>Columns</th></tr><tr><td>x</td><td>y</td></tr></table>",
                                  "<table><tr><th>Financial Program</th><th>Purpose</th></tr></table>"])
def test_missing_or_empty_table_aborts(body):
    with pytest.raises(ValueError):
        md.index_rows("https://mde.maryland.gov/programs/water/WQFA/Pages/index.aspx", section(body))


# ---------- status rules ----------

def fields(banner: str | None, body: str = "<p>Funding Applications Accepted December thru January Annually</p>", today: date = TODAY) -> dict:
    return md.status_fields_for({"title": "X", "purpose": None, "banner": banner, "linked": True}, section(body), today)


def test_banner_closed_with_a_month_ahead_is_forecasted():
    f = fields(BANNER)
    assert f == {"status": "forecasted", "opens_at": None, "closes_at": None, "closes_at_text": BANNER, "rolling": None}
    assert fields(BANNER, today=date(2026, 12, 5))["status"] == "closed"                       # the month has come
    assert fields("MWIFA's funding solicitation is currently closed.")["status"] == "closed"
    assert fields("Applications are not being accepted. Applications will reopen on January 5, 2027.")["opens_at"] == date(2027, 1, 5)


def test_banner_open_with_and_without_a_date():
    f = fields("MWIFA's funding solicitation is now open. Applications are due January 31, 2027.")
    assert f["status"] == "open" and f["closes_at"] == date(2027, 1, 31)
    assert fields("MWIFA's funding solicitation is now open.")["status"] == "open"
    assert fields("MWIFA's funding solicitation is now open. Applications are due January 31, 2026.")["status"] == "unknown"


def test_no_banner_keeps_the_cycle_line_and_is_unknown():
    f = fields(None)
    assert f["status"] == "unknown" and f["closes_at_text"] == "Funding Applications Accepted December thru January Annually"
    assert fields(None, "<p>A page with no cycle line.</p>")["closes_at_text"] is None


# ---------- normalize ----------

def test_wqrlf_pass_through_loan_local_governments():
    p = normalize(WQRLF)
    assert p.name == "Water Quality Revolving Loan Program (WQRLF)" and p.agency_code == "MD-MDE"
    assert p.status == "forecasted" and p.closes_at_text == BANNER and p.opens_at is None
    assert p.funding_type == "loan" and p.funding_source == "pass_through" and p.alns == []
    assert {t.value for t in p.applicant_types} == {"municipality", "county"}
    assert p.summary.startswith("Provides low-interest loans to local governments")
    assert p.eligibility_text.startswith(p.summary)
    assert p.category_pairs() == [("water", "mwifa")]


def test_water_supply_grant_with_a_local_match():
    p = normalize(WATER_SUPPLY)
    assert p.funding_type == "grant" and p.funding_source == "direct" and p.match_required is True
    assert {t.value for t in p.applicant_types} == {"municipality", "county"}


def test_unlinked_supplemental_row_reads_the_index_cell_only():
    p = normalize(SUPPLEMENTAL)
    assert p.name == "Supplemental Assistance Grant Program" and p.source_url.lower() == index()["url"].lower()
    assert p.status == "forecasted" and p.funding_type == "grant" and p.match_required is True
    assert p.applicant_types == []                                                               # "communities" is not a type
    assert p.eligibility_text == p.summary                                                       # not the index's other sentences


def test_septic_grant_by_override_and_no_applicant():
    p = normalize(SEPTIC)
    assert p.name == "Bay Restoration Fund - Septic System Upgrade Program" and p.funding_type == "grant"
    assert p.applicant_types == [] and p.status == "forecasted"


def test_cfmgp_local_jurisdictions():
    p = normalize(CFMGP)
    assert {t.value for t in p.applicant_types} == {"municipality", "county"}
    assert p.funding_type == "grant" and p.funding_source == "direct"


def test_banner_change_moves_the_hash():
    p = normalize(WQRLF)
    reopened = normalize(WQRLF, row={**payload(WQRLF)["row"], "banner": "MWIFA's funding solicitation is now open."})
    assert reopened.status == "open" and reopened.record_hash != p.record_hash


def test_bare_page_invents_nothing():
    p = md.normalize(RawRecord(source_connector=md.CONNECTOR, source_id="programs/x.aspx",
                               payload={"url": f"{md.BASE}/programs/x.aspx", "main_html": section("<p>Hello.</p>", "X"), "row": None}), TODAY)
    assert p.name == "X" and p.status == "unknown" and p.applicant_types == [] and p.summary is None


def test_fixtures_carry_no_phone_numbers():
    for path in FIXTURES.iterdir():
        assert "537-3908" not in path.read_text(encoding="utf-8")
    assert "537-3908" not in (normalize(WQRLF).eligibility_text or "")
