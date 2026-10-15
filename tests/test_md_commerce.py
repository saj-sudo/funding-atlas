"""Maryland Commerce connector tests. Mapping tests run against saved page fixtures (never the network);
the status, date and sentence rules are pure functions tested directly."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import md_commerce as mc
from pipeline.models import RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "md_commerce"
TODAY = date(2026, 10, 15)

EXPORTMD = "financial-incentives/grants/exportmd-program"
M40 = "financial-incentives/grants/maryland-manufacturing-40-m40"
ESCC = "financial-incentives/tax-incentives/employer-security-clearance-costs-tax-credit-escc"
RD = "financial-incentives/tax-incentives/research-and-development-tax-credit-rd"
CHILD_CARE = "financial-incentives/loans-financing/child-care-capital-support-revolving-loan-fund"
ADVANTAGE = "financial-incentives/loans-financing/advantage-maryland-medaaf"
CBAF = "financial-incentives/loans-financing/cannabis-business-assistance-fund-cbaf"
INDEX = "financial-incentives/grants"


def payload(source_id: str) -> dict:
    return json.loads((FIXTURES / f"{source_id.rsplit('/', 1)[-1]}.json").read_text())


def normalize(source_id: str):
    return mc.normalize(RawRecord(source_connector=mc.CONNECTOR, source_id=source_id, payload=payload(source_id)), today=TODAY)


# ---------- enumeration ----------

def test_sitemap_filter_keeps_financial_incentives_only():
    entries = mc.iter_sitemap((FIXTURES / "sitemap_excerpt.xml").read_text())
    urls = [u for u, _ in entries]
    assert len(entries) == 8
    assert all("/financial-incentives/" in u for u in urls)
    assert f"{mc.BASE}/{EXPORTMD}" in urls and f"{mc.BASE}/{INDEX}" in urls
    assert dict(entries)[f"{mc.BASE}/{EXPORTMD}"] == payload(EXPORTMD)["lastmod"]


def test_only_pages_with_a_program_status_section_are_records():
    assert mc.SITE.is_record(payload(EXPORTMD))
    assert not mc.SITE.is_record(payload(INDEX))
    assert mc.classify_page(payload(INDEX)) == {"status": "unknown"}
    assert mc.classify_page(payload(RD), TODAY) == {"status": "open", "closes_at": date(2026, 11, 15)}


# ---------- status rules ----------

@pytest.mark.parametrize("text, expected", [
    ("The program is currently active. Applications are accepted on a rolling basis.", "open"),
    ("MIDFA is currently active.", "open"),
    ("The program is ongoing. Applications are accepted on a rolling basis.", "open"),
    ("The application period for Tax Year 2025 is open.", "open"),
    ("The program is active but between funding rounds. The most recent application period closed January 30, 2026.", "closed"),
    ("The program is currently closed. The Tax Year 2025 application period opened May 1, 2026 and closed September 15, 2026.", "closed"),
    ("The application period is currently closed. The program sunsetted on September 30, 2026.", "closed"),
    ("Closed to new positions. Commerce may still accept applications for wages paid in tax years 2017–2020.", "closed"),
    ("Closed to new enrollment as of June 1, 2024. The application period is open only to enrolled businesses.", "closed"),
    ("The most recent round accepted applications from July 1, 2026 through August 14, 2026. That window has closed.", "closed"),
    ("The program is active. The most recent posted deadline was June 1, 2026. That deadline has passed and no later round has been posted.", "closed"),
    ("The program is active and awards grants once per year. Both dates have passed.", "closed"),
    ("Applications are not being accepted at this time. Check this page for the next application window (August 2, 2027).", "forecasted"),
    ("Applications are not being accepted at this time. Check this page for the next application window (August 2, 2026).", "closed"),
    ("CBAF is a financing resource operated by Commerce. The application portal opened June 3, 2025.", "unknown"),
    ("", "unknown"),
])
def test_status_rules(text, expected):
    assert mc.fields_for(text or None, TODAY)["status"] == expected


def test_closed_wording_beats_active_wording():
    assert mc.status_for("The program is active but between funding rounds.", TODAY) == "closed"


@pytest.mark.parametrize("raw, expected", [
    ("Aug. 3, 2026", date(2026, 8, 3)), ("August 3, 2026", date(2026, 8, 3)), ("Sept. 15, 2026", None),
])
def test_parse_text_date(raw, expected):
    assert mc.parse_text_date(raw) == expected


def test_dates_come_from_timing_sentences_not_sunset_sentences():
    f = mc.fields_for(
        "The program is currently active. Applications are accepted on a rolling basis. "
        "Sunset date: The credit remains in effect until January 1, 2032, subject to further extension.", TODAY)
    assert f["status"] == "open" and f["rolling"] is True
    assert f["opens_at"] is None and f["closes_at"] is None
    assert "2032" not in f["closes_at_text"]


def test_timing_sentences_need_a_timing_word():
    text = ("Advantage Maryland is currently active. Awards are made on a competitive basis. "
            "Awards depend on available funding, and limits were amended by the DECADE Act effective July 1, 2026.")
    assert mc.timing_sentences(text) == []
    assert mc.fields_for(text, TODAY) == {"status": "open", "closes_at_text": None, "opens_at": None, "closes_at": None}


def test_rolling_only_when_open():
    assert mc.fields_for("The program is currently closed. Applications were accepted on a rolling basis.", TODAY).get("rolling") is None


# ---------- normalize ----------

def test_normalize_open_monthly_pass_through():
    p = normalize(EXPORTMD)
    assert p.name == "ExportMD Program" and p.agency_code == "MD-COMMERCE" and p.level == "state"
    assert p.source_url == f"{mc.BASE}/{EXPORTMD}" and p.jurisdiction == "MD"
    assert p.funding_type == "grant" and p.funding_source == "pass_through" and p.alns == ["59.061"]
    assert p.status == "open" and p.rolling is True and p.opens_at is None and p.closes_at is None
    assert p.closes_at_text == "Commerce accepts applications every month. Applications are due on the 1st of each month."
    assert p.summary.startswith("The ExportMD Program")
    assert p.eligibility_text.startswith("This program is for Maryland small businesses")
    assert p.applicant_pairs() == [("business", "businesses")]
    assert p.category_pairs() == [("other", "grants")]
    assert p.amount_min is None and p.amount_max is None and p.match_required is None


def test_normalize_forecasted_round_uses_the_next_window_date():
    p = normalize(M40)
    assert p.status == "forecasted"
    assert p.opens_at == date(2027, 8, 2) and p.closes_at is None      # not the window that just closed
    assert "opened Aug. 3, 2026 and closed Aug. 31, 2026" in p.closes_at_text
    assert p.rolling is None and p.funding_type == "grant"


def test_normalize_closed_tax_credit_with_window_dates():
    p = normalize(ESCC)
    assert p.status == "closed" and p.funding_type == "tax_credit"
    assert (p.opens_at, p.closes_at) == (date(2026, 5, 1), date(2026, 9, 15))
    assert p.closes_at_text.startswith("The program is currently closed.")
    assert "Sunset" not in p.closes_at_text and "2033" not in p.closes_at_text
    assert p.category_pairs() == [("other", "tax-incentives")]


def test_normalize_open_window_from_until():
    p = normalize(RD)
    assert p.status == "open" and (p.opens_at, p.closes_at) == (date(2026, 6, 1), date(2026, 11, 15))
    assert p.rolling is None
    assert ("business", "for-profit") in p.applicant_pairs()


def test_normalize_between_rounds_is_closed():
    p = normalize(CHILD_CARE)
    assert p.status == "closed" and p.opens_at is None and p.closes_at == date(2026, 1, 30)
    assert p.funding_type == "loan" and p.applicant_pairs() == []           # "child care providers" is no keyword


def test_normalize_municipal_wording_is_tagged():
    p = normalize(ADVANTAGE)
    assert p.status == "open" and p.closes_at_text is None
    assert ("municipality", "municipalities") in p.applicant_pairs() and ("county", "counties") in p.applicant_pairs()
    assert p.funding_type == "loan"                                          # section default: no keyword in the name


def test_normalize_unknown_when_status_text_says_neither():
    p = normalize(CBAF)
    assert p.status == "unknown" and p.opens_at == date(2025, 6, 3) and p.closes_at is None
    assert p.funding_type == "loan"


def test_funding_type_rules():
    ft = mc.SITE.funding_type_for
    assert ft("Film Production Sales and Use Tax Exemption", "financial-incentives/tax-incentives/x") == "other"
    assert ft("Strategic Closing Fund", "financial-incentives/loans-financing/x") == "loan"
    assert ft("Job Creation Tax Credit (JCTC)", "financial-incentives/tax-incentives/x") == "tax_credit"
    assert ft("Maryland MADE", "financial-incentives/grants/x") == "grant"


def test_normalize_invents_nothing_from_a_bare_status():
    raw = RawRecord(source_connector=mc.CONNECTOR, source_id="financial-incentives/grants/bare", payload={
        "url": f"{mc.BASE}/financial-incentives/grants/bare", "lastmod": None, "updated_time": None, "description": None,
        "main_html": '<main><h1>Bare Fund</h1><div class="usa-prose maryland-toc-target">'
                     '<h2>Program Status</h2><p>The program is currently active.</p><h2>Contact</h2><p>Email us.</p></div></main>',
    })
    p = mc.normalize(raw, today=TODAY)
    assert p.status == "open" and p.funding_type == "grant"
    assert p.summary is None and p.eligibility_text is None and p.applicant_types == []
    assert p.opens_at is None and p.closes_at is None and p.closes_at_text is None and p.rolling is None
    assert p.record_hash


def test_hash_is_stable():
    assert normalize(EXPORTMD).record_hash == normalize(EXPORTMD).record_hash
    assert normalize(EXPORTMD).record_hash != normalize(RD).record_hash
