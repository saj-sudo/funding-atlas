"""MDEM connector tests: the roster parser, the roster-first status rules, the clause-level negation, and the four
saved pages (never the network)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import maryland_sharepoint as sp
from connectors import md_mdem as md
from pipeline.models import RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "md_mdem"
TODAY = date(2026, 11, 3)

NSGP = "pages/nonprofit-security-grant-program.aspx"
FMA = "community/pages/mitigation.aspx"
RLF = "pages/rlf-fund.aspx"
PA = "community/pages/public-assistance-program.aspx"


def payload(source_id: str) -> dict:
    return json.loads((FIXTURES / f"{sp.fixture_name(source_id)}.json").read_text())


def normalize(source_id: str, today: date = TODAY, **overrides):
    p = {**payload(source_id), **overrides}
    return md.normalize(RawRecord(source_connector=md.CONNECTOR, source_id=source_id, payload=p), today=today)


def roster() -> dict:
    data = json.loads((FIXTURES / "index__pages__grants.json").read_text())
    return md.roster_rows(data["url"], data["main_html"])


def section(body: str, h1: str = "Some Program") -> str:
    return (f'<section class="mdgov-section"><div id="ctl00_PlaceHolderMain_editmodepanel2"><h1>{h1}</h1></div>'
            f'<div id="ctl00_PlaceHolderMain_ctl00__ControlWrapper_RichHtmlField" class="ms-rtestate-field">'
            f'{body}</div></section>')


# ---------- enumeration ----------

def test_roster_rows_two_items_with_facts():
    rows = roster()
    assert list(rows) == [NSGP, FMA]
    nsgp = rows[NSGP]["roster"]
    assert nsgp["title"] == "Nonprofit Security Grant Program (NSGP)"
    assert nsgp["applications_open"] is True and nsgp["deadline"] == "2023-04-26"
    assert nsgp["deadline_text"] == "4/26/2023 11:59 PM"
    assert nsgp["eligible_lines"] == ["1. Nonprofit entities within designated urban areas",
                                      "2. Nonprofit entities not within designated urban areas"]
    assert nsgp["description"].startswith("Funds physical and cybersecurity enhancements") and "Learn More" not in nsgp["description"]
    assert rows[NSGP]["url"] == "https://mdem.maryland.gov/Pages/Nonprofit-Security-Grant-Program.aspx"
    fma = rows[FMA]["roster"]
    assert fma["applications_open"] is False and fma["deadline"] is None and fma["deadline_text"] is None
    assert fma["eligible_lines"][0] == "Local Governments and State Agencies"
    assert fma["apply_url"] == "https://www.fema.gov/grants/mitigation/floods"
    assert rows[FMA]["url"] == "https://mdem.maryland.gov/community/Pages/Mitigation.aspx"     # as written; the 302 is followed on fetch


def test_hand_added_are_unlisted_and_carry_no_roster():
    assert payload(RLF)["listed"] is False and payload(RLF)["roster"] is None
    assert payload(NSGP)["listed"] is True and payload(NSGP)["roster"]["title"]


@pytest.mark.parametrize("html", ["<html><body><p>no table</p></body></html>",
                                  '<table class="ms-listviewtable"><tr><th>Title</th></tr></table>'])
def test_empty_or_missing_roster_aborts(html):
    with pytest.raises(ValueError):
        md.roster_rows("https://mdem.maryland.gov/Pages/grants.aspx", html)


# ---------- status rules ----------

def fields(roster: dict | None, body: str = "", today: date = TODAY) -> dict:
    return md.status_fields_for(roster, section(body), today)


def test_roster_no_is_closed_and_yes_with_a_future_deadline_is_open():
    assert fields({"applications_open": False, "deadline": None})["status"] == "closed"
    f = fields({"applications_open": True, "deadline": "2026-12-01", "deadline_text": "12/1/2026 5:00 PM"})
    assert f["status"] == "open" and f["closes_at"] == date(2026, 12, 1)
    assert f["closes_at_text"] == "Applications Open?: Yes; Application Deadline: 12/1/2026 5:00 PM"


def test_stale_yes_reads_the_page_window():
    window = "<p>Applications will be accepted from June 30, 2026 until 4:00pm on July 15, 2026.</p>"
    stale = {"applications_open": True, "deadline": "2023-04-26", "deadline_text": "4/26/2023 11:59 PM"}
    f = fields(stale, window)
    assert f["status"] == "unknown" and f["closes_at"] == date(2026, 7, 15) and f["opens_at"] == date(2026, 6, 30)
    assert f["closes_at_text"].endswith("until 4:00pm on July 15, 2026.")
    assert fields(stale, window, today=date(2026, 7, 1))["status"] == "open"
    assert fields(stale, "<p>Nothing about dates.</p>")["status"] == "unknown"


def test_hand_pages_without_a_window_are_unknown_unless_year_round():
    assert fields(None, "<p>Loans help local governments.</p>")["status"] == "unknown"
    f = fields(None, "<p>Applications are accepted year-round.</p>")
    assert f["status"] == "open" and f["rolling"] is True
    assert fields(None, "<p>Applications are not accepted year-round.</p>")["status"] == "unknown"


# ---------- applicants ----------

def test_parenthetical_negation_drops_the_clause_not_the_line():
    lines = ["Local Governments and State Agencies (Individuals, businesses, and organizations are not eligible, but a "
             "government/agency may sponsor the project on their behalf)"]
    assert md.roster_clauses(lines) == ["Local Governments and State Agencies"]
    assert md.roster_clauses(["1. Nonprofit entities within designated urban areas",
                              "2. Nonprofit entities not within designated urban areas"]) == [
        "Nonprofit entities within designated urban areas", "Nonprofit entities not within designated urban areas"]   # 10.6: a place limit, not a negation


# ---------- normalize ----------

def test_nsgp_stale_roster_window_passed():
    p = normalize(NSGP)
    assert p.name == "Nonprofit Security Grant Program (NSGP)" and p.agency_code == "MD-MDEM"
    assert p.status == "unknown" and p.closes_at == date(2026, 7, 15) and p.opens_at == date(2026, 6, 30)
    assert p.applicant_pairs() == [("nonprofit", "nonprofit")]
    assert p.funding_type == "grant" and p.funding_source == "pass_through" and p.alns == ["97.008"]
    assert p.summary.startswith("Funds physical and cybersecurity enhancements")
    assert p.category_pairs() == [("public_safety", "mdem")]
    assert normalize(NSGP, today=date(2026, 7, 1)).status == "open"


def test_fma_closed_from_the_roster_named_from_the_roster():
    p = normalize(FMA)
    assert p.name == "Flood Mitigation Assistance (FMA)"                    # not the hazard page's H1
    assert p.status == "closed" and p.closes_at is None and p.closes_at_text == "Applications Open?: No"
    assert {t.value for t in p.applicant_types} == {"municipality", "county", "state"}
    assert "not eligible" not in (p.eligibility_text or "")
    assert p.funding_type == "grant" and p.alns == ["97.029"]
    assert p.source_url == "https://mdem.maryland.gov/community/Pages/Mitigation.aspx"


def test_rlf_loan_direct_local_governments_not_beneficiaries():
    p = normalize(RLF)
    assert p.name == "Resilient MD Revolving Loans" and p.funding_type == "loan" and p.funding_source == "direct"
    assert p.status == "unknown" and p.closes_at is None
    assert {t.value for t in p.applicant_types} == {"municipality", "county"}     # not the homeowners it is lent on behalf of
    assert p.summary is None                                                        # boilerplate meta, no roster


def test_public_assistance_pass_through_unknown():
    p = normalize(PA)
    assert p.status == "unknown" and p.funding_source == "pass_through" and p.alns == ["97.036"]
    assert p.funding_type == "grant"                                                # "Federal grant assistance"
    assert {t.value for t in p.applicant_types} == {"municipality", "county", "nonprofit", "state"}   # "to State, local governments" (10.6)


def test_roster_flip_changes_the_hash():
    p = normalize(FMA)
    flipped = normalize(FMA, roster={**payload(FMA)["roster"], "applications_open": True, "deadline": "2027-01-15", "deadline_text": "1/15/2027"})
    assert flipped.status == "open" and flipped.record_hash != p.record_hash


def test_classify_page_without_roster_facts_reads_the_page_only():
    assert md.classify_page(payload(NSGP) | {"roster": None}, TODAY) == {"status": "unknown", "closes_at": date(2026, 7, 15)}
    assert md.classify_page(payload(FMA) | {"roster": None}, TODAY) == {"status": "unknown", "closes_at": None}


def test_bare_page_invents_nothing():
    p = md.normalize(RawRecord(source_connector=md.CONNECTOR, source_id="pages/x.aspx",
                               payload={"url": f"{md.BASE}/Pages/x.aspx", "main_html": section("<p>Hello.</p>", "X"), "roster": None}), TODAY)
    assert p.status == "unknown" and p.applicant_types == [] and p.closes_at is None and p.funding_type is None


def test_fixtures_carry_no_contacts():
    for path in FIXTURES.iterdir():
        text = path.read_text(encoding="utf-8").lower()
        assert "mailto:" not in text and "cfemail" not in text and "@maryland.gov" not in text and "lagola" not in text
    assert "Nora" not in (normalize(PA).eligibility_text or "")
