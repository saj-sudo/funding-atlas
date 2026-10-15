"""Maryland DHCD connector tests. Mapping tests run against saved page fixtures (never the network);
the box parser, date and status rules, and the refetch gate are pure functions tested directly."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import md_dhcd as md
from pipeline.models import RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "md_dhcd"
TODAY = date(2026, 10, 15)   # the crawl date; status rules compare against it

TAG = "neighborhood-revitalization/community-development-funding/technical-assistance-grant"
NOURISH = "business-development/nourishmd-grant-program"
CDBG = "neighborhood-revitalization/community-development-funding/community-development-block-grant-program"
NET_ZERO = "energy-home-repair/energy-grants-and-loans-residents/net-zero-loan-program"
MIP = "neighborhood-revitalization/main-street-maryland/main-street-improvement-grant-mip"
MEAP = "energy-home-repair/energy-grants-and-loans-residents/maryland-energy-assistance-program"
LEGACY = "neighborhood-revitalization/community-development-funding/state-revitalization-programs/community-legacy-program"


def payload(source_id: str) -> dict:
    return json.loads((FIXTURES / f"{source_id.rsplit('/', 1)[-1]}.json").read_text())


def load(source_id: str) -> RawRecord:
    return RawRecord(source_connector=md.CONNECTOR, source_id=source_id, payload=payload(source_id))


def normalize(source_id: str):
    return md.normalize(load(source_id), today=TODAY)


# ---------- sitemap ----------

def test_sitemap_filter_keeps_program_pages_only():
    entries = md.iter_sitemap((FIXTURES / "sitemap_excerpt.xml").read_text())
    urls = [u for u, _ in entries]
    assert len(entries) == 7
    assert f"{md.BASE}/{TAG}" in urls and f"{md.BASE}/{LEGACY}" in urls
    assert not [u for u in urls if "/media/" in u or "/news-stories/" in u or "/contacts/" in u or "/about-us" in u]
    assert f"{md.BASE}/" not in urls
    assert dict(entries)[f"{md.BASE}/{TAG}"] == payload(TAG)["lastmod"]


def test_source_id_is_the_path():
    assert md.source_id_for("https://dhcd.maryland.gov/housing/foo/bar") == "housing/foo/bar"


def test_needs_fetch_gate():
    good = {"lastmod": "2026-10-09T13:02Z", "main_html": "<main>x</main>"}
    assert md.needs_fetch("2026-10-09T13:02Z", None)
    assert not md.needs_fetch("2026-10-09T13:02Z", good)
    assert md.needs_fetch("2026-10-10T00:00Z", good)                           # moved
    assert md.needs_fetch(None, good)                                          # no stamp: refetch
    assert md.needs_fetch("2026-10-09T13:02Z", {"lastmod": "2026-10-09T13:02Z", "main_html": ""})


def test_page_payload_shape():
    p = payload(TAG)
    assert set(p) == {"url", "lastmod", "updated_time", "description", "main_html"}
    assert p["main_html"].startswith("<main") and p["updated_time"].startswith("2026-")
    assert md.page_payload("u", None, "<html><body>no main</body></html>") is None


# ---------- box parsing ----------

def test_parse_box_normalizes_labels():
    assert md.parse_box(payload(TAG)["main_html"]) == [
        ("application status", "Closed"),
        ("application opened", "Friday, February 20, 2026 at 8:00 AM(EDT)"),
        ("application closed", "Friday, March 20, 2026 at 5:00 PM (EDT)"),
    ]
    # &nbsp; inside the <strong> and a trailing &nbsp; on the value
    assert md.parse_box(payload(NOURISH)["main_html"]) == [
        ("application status", "Open"),
        ("application opens", "September 22, 2026"),
        ("application closes", "November 2, 2026"),
    ]
    assert md.parse_box(payload(LEGACY)["main_html"]) == []


def test_box_without_status_label_is_not_a_record():
    assert not md.has_status_label([])
    assert not md.has_status_label([("how to apply", "Email us"), ("", "Rolling")])
    assert md.has_status_label([("application status", "Open")])
    assert md.has_status_label([("applications status", "Closed")])
    assert md.has_status_label([("registration status", "Closed")])
    assert md.has_status_label([("funding status", "Fully spent")])
    assert md.has_status_label([("waitlist status", "Closed")])


@pytest.mark.parametrize("label, kind", [
    ("application status", "status"), ("application opens", "opens"), ("application opened", "opens"),
    ("application period opened", "opens"), ("registration period opens (expected)", "opens"),
    ("application closes", "closes"), ("application closed", "closes"), ("application period closed", "closes"),
    ("application deadline", "closes"), ("registration period closes (expected)", "closes"),
    ("next funding cycle", "cycle"), ("how to apply", None), ("application schedule", None),
])
def test_label_kinds(label, kind):
    assert md.label_kind(label) == kind


@pytest.mark.parametrize("raw, expected", [
    ("Friday, February 20, 2026 at 8:00 AM(EDT)", date(2026, 2, 20)),
    ("Friday, March 20, 2026 at 5:00 PM (EDT)", date(2026, 3, 20)),
    ("August 17, 2026 at 9:00 AM", date(2026, 8, 17)),
    ("Sunday, November 1, 2026, at 11:59 PM", date(2026, 11, 1)),
    ("April 1, 2026, at 9:00 AM", date(2026, 4, 1)),
    ("July 6, 2026", date(2026, 7, 6)),
    ("February 26 by 5:00 PM", None),                                    # no year: not a date
    ("February 2027", None),                                             # month only: text, not a date
    ("First business day of January at 8:00 AM", None),
    ("We are accepting applications until available funds are committed.", None),
])
def test_parse_box_date(raw, expected):
    assert md.parse_box_date(raw) == expected


# ---------- status rules ----------

@pytest.mark.parametrize("lines, expected", [
    ([("application status", "Open")], "open"),
    ([("application status", "Closed")], "closed"),
    ([("application status", "Closed"), ("application opened", "May 8, 2026")], "closed"),        # past
    ([("application status", "Closed"), ("application opens", "February 8, 2027")], "forecasted"),
    ([("application status", "Closed"), ("application opens", "February 2027")], "forecasted"),   # month-year
    ([("application status", "Closed"), ("application opens", "First business day of January")], "closed"),
    ([("application status", "Varies by jurisdiction")], "unknown"),
    ([("funding status", "Funding is fully spent for 2025–2026 (Waitlist only)")], "exhausted"),
    ([("funding status", "Available")], "unknown"),
    ([("waitlist status", "Closed")], "unknown"),
    ([("how to apply", "Email")], "unknown"),
])
def test_status_rules(lines, expected):
    assert md.status_for(lines, TODAY) == expected


def test_forecasted_flips_to_closed_once_the_date_passes():
    lines = [("application status", "Closed"), ("application opens", "February 2027")]
    assert md.status_for(lines, date(2027, 1, 31)) == "forecasted"
    assert md.status_for(lines, date(2027, 2, 1)) == "closed"


def test_classify_page_for_resolve_missing():
    assert md.classify_page(None) == {"status": "unknown"}
    assert md.classify_page(payload(LEGACY)) == {"status": "unknown"}
    assert md.classify_page(payload(NOURISH), TODAY) == {"status": "open", "closes_at": date(2026, 11, 2)}
    assert md.classify_page(payload(TAG), TODAY) == {"status": "closed", "closes_at": date(2026, 3, 20)}


# ---------- normalize ----------

def test_normalize_closed_round_with_weekday_dates():
    p = normalize(TAG)
    assert p.name == "Technical Assistance Grant"
    assert p.source_id == TAG and p.source_url == f"{md.BASE}/{TAG}"
    assert p.level == "state" and p.jurisdiction == "MD" and p.agency_code == "MD-DHCD"
    assert p.administering_agency == md.AGENCY
    assert p.funding_type == "grant" and p.funding_source == "direct" and p.alns == []
    assert p.status == "closed"
    assert (p.opens_at, p.closes_at) == (date(2026, 2, 20), date(2026, 3, 20))
    assert p.closes_at_text == ("application opened: Friday, February 20, 2026 at 8:00 AM(EDT); "
                                "application closed: Friday, March 20, 2026 at 5:00 PM (EDT)")
    assert p.rolling is None and p.match_required is False
    assert p.summary.startswith("DHCD is committed to assisting Maryland's local governments")
    assert p.eligibility_text.startswith("The following organizations may apply")
    assert "Priority Funding Area" in p.eligibility_text          # "Eligible project locations" is kept verbatim
    assert p.applicant_pairs() == [("county", "local governments"), ("municipality", "local governments"),
                                   ("nonprofit", "nonprofit")]    # but tags come from "Eligible applicants" only
    assert p.category_pairs() == [("housing", "neighborhood-revitalization")]
    assert p.amount_min is None and p.amount_max is None and p.external_number is None
    assert p.eligibility_structured is None and p.match_pct is None


def test_normalize_open_round():
    p = normalize(NOURISH)
    assert p.status == "open" and (p.opens_at, p.closes_at) == (date(2026, 9, 22), date(2026, 11, 2))
    assert p.rolling is None and p.match_required is None
    assert ("business", "retailers") in p.applicant_pairs() and ("nonprofit", "nonprofit") in p.applicant_pairs()
    assert p.category_pairs() == [("other", "business-development")]


def test_normalize_pass_through_with_deadline_only_label():
    p = normalize(CDBG)
    assert p.funding_source == "pass_through" and p.alns == ["14.228"]
    assert p.status == "closed" and p.opens_at is None and p.closes_at == date(2026, 7, 6)
    assert p.closes_at_text == "application deadline: July 6, 2026"
    assert ("municipality", "units of general local government") in p.applicant_pairs()
    assert ("county", "units of general local government") in p.applicant_pairs()
    assert ("municipality", "towns") in p.applicant_pairs()
    assert "Who is not eligible" not in p.eligibility_text        # heading text is not part of the section text
    assert p.eligibility_text.count("\n\n") >= 1                   # both "Who is eligible" and "Who is not eligible" sections


def test_normalize_rolling_loan():
    p = normalize(NET_ZERO)
    assert p.funding_type == "loan" and p.status == "open"
    assert p.opens_at == date(2025, 4, 16) and p.closes_at is None and p.rolling is True
    assert p.closes_at_text.endswith("until available funds are committed.")
    assert ("household", "homeowners") in p.applicant_pairs()
    assert p.category_pairs() == [("energy", "energy-home-repair"), ("housing", "energy-home-repair")]


def test_normalize_month_only_opening_is_forecasted_not_invented():
    p = normalize(MIP)
    assert p.status == "forecasted"
    assert p.opens_at is None and p.closes_at is None             # "February 2027" is never turned into a date
    assert p.closes_at_text == "application opens: February 2027"
    assert p.match_required is False
    assert p.applicant_pairs() == []                               # "Main Street Maryland communities" matches no keyword


def test_normalize_funding_status_box():
    p = normalize(MEAP)
    assert p.status == "exhausted" and p.funding_type is None
    assert p.funding_source == "pass_through" and p.alns == ["93.568"]
    assert p.closes_at_text.startswith("next funding cycle: November 1, 2026")
    assert p.opens_at is None and p.closes_at is None
    assert p.applicant_pairs() == []            # "To be eligible ... you must:" names no applicant type


def test_normalize_invents_nothing_from_a_bare_box():
    raw = RawRecord(source_connector=md.CONNECTOR, source_id="housing/bare", payload={
        "url": f"{md.BASE}/housing/bare", "lastmod": None, "updated_time": None, "description": None,
        "main_html": '<main><h1><span>Bare &amp; Minimal</span></h1>'
                     '<div class="maryland-summary-box"><ul><li><p><strong>Application status:</strong> Open</p></li></ul></div>'
                     '<div class="usa-prose maryland-toc-target"><h2>Contact information</h2><p>Email us.</p></div></main>',
    })
    p = md.normalize(raw, today=TODAY)
    assert p.name == "Bare & Minimal" and p.status == "open"
    assert p.funding_type is None and p.summary is None and p.eligibility_text is None
    assert p.opens_at is None and p.closes_at is None and p.closes_at_text is None and p.rolling is None
    assert p.match_required is None and p.applicant_types == [] and p.alns == []
    assert p.category_pairs() == [("housing", "housing")]
    assert p.record_hash


def test_applicant_tags_come_from_who_sections_only():
    html = ('<main><div class="usa-prose maryland-toc-target">'
            '<h2>Eligible participants</h2><p>Small municipalities with populations of 5,000 or less are eligible.</p>'
            '<h2>Eligible circuit sponsors</h2><p>Municipal governments, county governments or private organizations may sponsor.</p>'
            '<h2>Eligible project locations</h2><p>Projects must serve residents of a Priority Funding Area.</p>'
            '<h2>Eligible use of funds</h2><p>Salaries for homeowners\' counselors.</p>'
            '<h2>Eligible applicants</h2><p>IRS designated 501(c)(3) organizations.</p>'
            '<h2>Who is not eligible to apply?</h2><p>Businesses and individuals.</p>'
            '</div></main>')
    lines = md.applicant_text(html)
    text = " ".join(lines)
    assert "residents" not in text and "homeowners" not in text and "Businesses" not in text
    pairs = {(t.value, t.source_code) for t in md.applicant_types_for(lines)}
    assert pairs == {("municipality", "municipalities"), ("county", "county"), ("nonprofit", "501(c)(3)")}
    sections = md.body_sections(html)
    assert md.eligibility_text_for(sections).count("\n\n") == 5      # every eligibility section is kept verbatim


def test_applicant_lines_stop_at_conditions_and_skip_negations():
    html = ('<main><div class="usa-prose maryland-toc-target"><h2>Eligible applicants</h2>'
            '<p>To be eligible to receive a grant, an applicant must be either:</p>'
            '<ul><li>A nonprofit organization</li><li>A State or local government unit</li></ul>'
            '<p>For-profit businesses are not eligible to apply.</p>'
            '<p>This credit is for developers that:</p>'
            '<ul><li>are located within a Tier 1 County</li></ul>'
            '<p>Level 2. Requires local government approval (municipality or county resolution).</p>'
            '</div></main>')
    pairs = {(t.value, t.source_code) for t in md.applicant_types_for(md.applicant_text(html))}
    assert pairs == {("nonprofit", "nonprofit"), ("municipality", "local government"), ("county", "local government"),
                     ("business", "developers")}


def test_place_words_after_a_spatial_preposition_are_not_applicants():
    tags = md.applicant_types_for(["Units of general local government in non-entitlement counties and non-entitlement cities and towns"])
    pairs = {(t.value, t.source_code) for t in tags}
    assert ("county", "units of general local government") in pairs and ("municipality", "towns") in pairs
    assert ("county", "counties") not in pairs
    assert md.applicant_types_for(["then 4+ weeks of performances in 4+ cities outside Maryland"]) == []
    assert md.applicant_types_for(["must be located in a designated rural county"]) == []


def test_hash_is_stable_across_normalize_calls():
    assert normalize(TAG).record_hash == normalize(TAG).record_hash
    assert normalize(TAG).record_hash != normalize(NOURISH).record_hash
