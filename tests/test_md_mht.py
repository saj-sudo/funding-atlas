"""Maryland Historical Trust connector tests. Mapping tests run against saved page fixtures (never the
network); the open-list parser, amount, match and timeline rules are pure functions tested directly."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import md_mht as mh
from pipeline.models import RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "md_mht"
TODAY = date(2026, 10, 15)

INDEX = "funding/how-apply-grant"
CAPITAL = "funding/historic-preservation-capital-grant-program"
AAHPP = "funding/african-american-heritage-preservation-program-grants/aahpp-non-capital-grants"
MHAA = "planning-protection/maryland-heritage-areas-program/maryland-heritage-areas-program-project-grants"
LOANS = "funding/loans-historic-preservation"
MARITIME = "funding/maritime-heritage-grant-program"
SMALL_COMMERCIAL = "funding/tax-credits/small-commercial-tax-credit"
EASEMENT = "planning-protection/preservation-easements/donate-or-convey-easement"


def payload(source_id: str) -> dict:
    return json.loads((FIXTURES / f"{source_id.rsplit('/', 1)[-1]}.json").read_text())


def normalize(source_id: str, listed_open: bool | None = None):
    p = payload(source_id)
    if listed_open is not None:
        p = {**p, "listed_open": listed_open}
    return mh.normalize(RawRecord(source_connector=mh.CONNECTOR, source_id=source_id, payload=p), today=TODAY)


# ---------- enumeration and the open list ----------

def test_sitemap_filter_keeps_funding_and_planning_pages():
    entries = mh.iter_sitemap((FIXTURES / "sitemap_excerpt.xml").read_text())
    urls = [u for u, _ in entries]
    assert len(entries) == 8
    assert all("/funding" in u or "/planning-protection/" in u for u in urls)
    assert not [u for u in urls if "/education-outreach/" in u or "/about" in u or "/media/" in u]
    assert dict(entries)[f"{mh.BASE}/{CAPITAL}"] == payload(CAPITAL)["lastmod"]


def test_open_paths_reads_only_the_list_under_the_heading():
    # The paragraph after the list links a newsletter and an events page; neither is a program.
    assert mh.open_paths(payload(INDEX)["main_html"]) == {AAHPP}
    assert mh.open_paths("<main><div class='usa-prose maryland-toc-target'><h2>Step 1</h2><ul><li><a href='/x'>x</a></li></ul></div></main>") == set()


def test_annotate_stamps_listed_open_by_path():
    ctx = {"open_paths": [AAHPP]}
    assert mh.SITE.annotate(payload(AAHPP), ctx)["listed_open"] is True
    assert mh.SITE.annotate(payload(CAPITAL), ctx)["listed_open"] is False
    assert "listed_open" in payload(AAHPP)          # the probe stamps fixtures the same way


def test_record_scope_needs_timeline_and_eligibility():
    assert mh.SITE.is_record(payload(CAPITAL)) and mh.SITE.is_record(payload(SMALL_COMMERCIAL))
    assert not mh.SITE.is_record(payload(EASEMENT))        # Timeline, no eligibility section
    assert not mh.SITE.is_record(payload(INDEX))
    assert mh.classify_page(payload(EASEMENT)) == {"status": "unknown"}
    assert mh.classify_page(payload(AAHPP), TODAY) == {"status": "open", "closes_at": date(2026, 11, 20)}


# ---------- pure rules ----------

@pytest.mark.parametrize("text, expected", [
    ("Applicants may request up to $100,000 in funding. A 1:1 cash match is required.", (None, 100000)),
    ("Applicants may request up to $20,000 in funding, with grants typically between $10,000 - $15,000.", (None, 20000)),
    ("Grant awards range from $10,000 to $100,000. Total project costs must range from $20,000 to $200,000.", (10000, 100000)),
    ("A 1:1 match is required Non-capital grants range from $5,000-$50,000 Capital grants range from $5,000-$100,000", (None, None)),
    ("In FY26, the program received $285,000 for grants statewide.", (None, None)),
    (None, (None, None)),
])
def test_amount_rules(text, expected):
    assert mh.amounts_for(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("A match is not required.", False),
    ("A 1:1 cash match is required for all applicants other than nonprofits.", True),
    ("Local governments must provide a 1:1 match (cash or in-kind).", True),
    ("Funds are awarded through a competitive process.", None),
    (None, None),
])
def test_match_rules(text, expected):
    assert mh.match_required_for(text) == expected


def test_box_close_date_and_text():
    box = "Applications now open for FY27 grant round! Access your grant portal account. Applications close on November 20, 2026 at 11:59 PM."
    assert mh.closes_at_for(box) == date(2026, 11, 20)
    assert mh.closes_at_for("Applications now open!") is None
    html = '<main><div class="usa-prose maryland-toc-target"><h2>Timeline</h2><ul><li>Application opens: early October</li><li>Application deadline: mid-November</li></ul></div></main>'
    assert mh.timeline_text_for(html, box) == (
        "Application opens: early October; Application deadline: mid-November; "
        "Applications close on November 20, 2026 at 11:59 PM.")
    assert mh.timeline_text_for(html, "") == "Application opens: early October; Application deadline: mid-November"


def test_prose_timeline_picks_the_timing_sentence():
    html = ('<main><div class="usa-prose maryland-toc-target"><h2>Timeline</h2>'
            '<p>There are two different types of applications: loan and transfer. Loan applications are accepted year-round, as funds become available.</p>'
            '<h2>Next</h2><p>Ignored.</p></div></main>')
    assert mh.timeline_text_for(html, "") == "Loan applications are accepted year-round, as funds become available."


# ---------- normalize ----------

def test_normalize_closed_annual_round_with_amount_and_match():
    p = normalize(CAPITAL)
    assert p.name == "Historic Preservation Capital Grant Program" and p.agency_code == "MD-MHT"
    assert p.level == "state" and p.jurisdiction == "MD" and p.funding_type == "grant" and p.funding_source == "direct"
    assert p.status == "closed" and p.opens_at is None and p.closes_at is None and p.rolling is None
    assert p.closes_at_text == "Application opens: February; Application deadline: March; Awards announced: June"
    assert (p.amount_min, p.amount_max) == (None, 100000) and p.match_required is True
    assert p.summary.startswith("Learn about eligible projects")
    assert p.eligibility_text.startswith("Nonprofit organizations Local governments")
    assert ("municipality", "local governments") in p.applicant_pairs() and ("county", "local governments") in p.applicant_pairs()
    assert ("nonprofit", "nonprofit") in p.applicant_pairs() and ("individual", "individuals") in p.applicant_pairs()
    assert p.category_pairs() == [("other", "historic-preservation")]


def test_normalize_open_via_list_and_banner():
    p = normalize(AAHPP)
    assert p.status == "open" and p.closes_at == date(2026, 11, 20) and p.opens_at is None
    assert p.closes_at_text.endswith("Applications close on November 20, 2026 at 11:59 PM.")
    assert p.name.endswith("Non-Capital Grants") and p.funding_type == "grant"
    assert (p.amount_min, p.amount_max) == (None, 50000) and p.match_required is False
    # the banner alone keeps it open even if the list drops it; the list alone keeps it open without the banner
    assert normalize(AAHPP, listed_open=False).status == "open"
    assert normalize(CAPITAL, listed_open=True).status == "open"


def test_normalize_two_ranges_give_no_amount():
    p = normalize(MHAA)
    assert p.status == "closed" and (p.amount_min, p.amount_max) == (None, None) and p.match_required is True
    assert p.closes_at_text.startswith("Grant round opens: December;")


def test_normalize_year_round_loan_is_open_and_rolling():
    p = normalize(LOANS)
    assert p.status == "open" and p.rolling is True and p.funding_type == "loan"
    assert p.closes_at_text == "Loan applications are accepted year-round , as funds become available."
    assert (p.amount_min, p.amount_max) == (None, None) and p.match_required is None


def test_normalize_federal_pass_through_with_range_amount():
    p = normalize(MARITIME)
    assert p.funding_source == "pass_through" and p.alns == ["15.925"]
    assert p.status == "closed" and p.closes_at is None           # "Full application due: November 13" has no year
    assert (p.amount_min, p.amount_max) == (10000, 100000) and p.match_required is True
    pairs = p.applicant_pairs()
    assert ("tribe", "tribal") in pairs and ("state", "state government agencies") in pairs and ("higher_ed", "colleges") in pairs


def test_normalize_rolling_tax_credit():
    p = normalize(SMALL_COMMERCIAL)
    assert p.status == "open" and p.rolling is True and p.funding_type == "tax_credit"
    assert p.closes_at_text.startswith("Applications are accepted year-round")
    assert p.applicant_pairs() == []        # "Owners of income-producing historic buildings" matches no keyword
    assert p.amount_max is None                                    # no "Available funding" section on tax credit pages


def test_normalize_invents_nothing_from_a_bare_timeline():
    raw = RawRecord(source_connector=mh.CONNECTOR, source_id="funding/bare", payload={
        "url": f"{mh.BASE}/funding/bare", "lastmod": None, "updated_time": None, "description": None, "listed_open": False,
        "main_html": '<main><h1>Bare Grant</h1><div class="usa-prose maryland-toc-target">'
                     '<h2>Timeline</h2><ul><li>Application opens: May</li></ul><h2>Eligible applicants</h2><ul><li>Anyone.</li></ul></div></main>',
    })
    p = mh.normalize(raw, today=TODAY)
    assert p.status == "closed" and p.closes_at_text == "Application opens: May"
    assert p.opens_at is None and p.closes_at is None and p.rolling is None
    assert p.amount_max is None and p.match_required is None and p.applicant_types == [] and p.summary is None
    assert p.record_hash


def test_hash_changes_when_the_open_list_changes():
    assert normalize(CAPITAL, listed_open=False).record_hash != normalize(CAPITAL, listed_open=True).record_hash
    assert normalize(CAPITAL).record_hash == normalize(CAPITAL).record_hash
