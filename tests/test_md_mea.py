"""Maryland Energy Administration connector tests. Mapping tests run against saved page fixtures (never the
network); the index parser, labeled-line parser, status, date and funding-type rules are pure functions tested
directly."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import md_mea as me
from pipeline.models import RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "md_mea"
TODAY = date(2026, 10, 16)

SOLARAPP = "govt/pages/solarapp.aspx"
CCB = "pages/commercial%26communitybuildingsgrantprogram.aspx"
EVSE = "pages/communityevse.aspx"
LGEM = "govt/pages/smartenergycommunities.aspx"
RESILIENT = "business/pages/resilientmaryland.aspx"
STORAGE = "pages/energy-storage-grant-program.aspx"
MSAP = "residential/pages/incentives/maryland-solar-access-program.aspx"
SOLAR_TA = "govt/pages/solartechnicalassistanceprogram.aspx"
LAWTON = "govt/pages/janeelawton.aspx"
MEGAWATTS = "pages/megawattsformaryland.aspx"
COMMERCIAL_SOLAR = "business/pages/commercial-solar.aspx"


def payload(source_id: str) -> dict:
    return json.loads((FIXTURES / f"{me.fixture_name(source_id)}.json").read_text())


def index_html(path: str) -> tuple[str, str]:
    data = json.loads((FIXTURES / f"index__{me.fixture_name(path)}.json").read_text())
    return data["url"], data["main_html"]


def normalize(source_id: str, **overrides):
    p = {**payload(source_id), **overrides}
    return me.normalize(RawRecord(source_connector=me.CONNECTOR, source_id=source_id, payload=p), today=TODAY)


def section(body: str, h1: str = "Some Program") -> str:
    """A minimal mdgov section around a body fragment."""
    return (f'<section class="mdgov-section"><div id="ctl00_PlaceHolderMain_editmodepanel2"><h1>{h1}</h1></div>'
            f'<div id="ctl00_PlaceHolderMain_RichHtmlField1__ControlWrapper_RichHtmlField" class="ms-rtestate-field">'
            f'{body}</div></section>')


# ---------- enumeration ----------

def test_index_links_read_program_links_under_their_headings():
    url, html = index_html("transportation/pages/incentives.aspx")
    links = me.index_links(url, html)
    assert links["pages/communityevse.aspx"]["heading"] == "Grants & Loans"
    assert links["transportation/pages/incentives_evserebate.aspx"]["heading"] == ""     # before the first heading
    assert links["transportation/pages/afip.aspx"]["heading"] == "Archived Programs"
    assert "pages/news.aspx" not in links                                               # SKIP_PATH
    assert not [sid for sid in links if "mva.maryland.gov" in sid]                       # off-site
    assert all(sid == sid.lower() for sid in links)


def test_index_union_across_the_five_indexes():
    entries: dict[str, dict] = {}
    for path in me.INDEX_PATHS:
        url, html = index_html(path)
        for sid, link in me.index_links(url, html).items():
            entries.setdefault(sid, {"index": {}})["index"][path] = link["heading"]
    assert len(entries) == 34
    assert entries[SOLARAPP]["index"] == {"pages/renewables.aspx": "Grants", "pages/communities.aspx": ""}
    assert entries[CCB]["index"] == {"pages/renewables.aspx": "Grants"}                    # %26 kept, lowercased
    assert "pages/facts/empower.aspx" not in entries and "pages/all-incentives.aspx" not in entries
    assert not any(path in entries for path in me.INDEX_PATHS)


def test_source_id_and_fixture_name_rules():
    assert me.source_id_for("https://energy.maryland.gov/govt/Pages/SolarAPP.aspx#top") == SOLARAPP
    assert me.canonical_url("/Pages/X.aspx#a", "http://energy.maryland.gov/Pages/Renewables.aspx") == "https://energy.maryland.gov/Pages/X.aspx"
    assert me.fixture_name(CCB) == "pages__commercial-26communitybuildingsgrantprogram"
    assert me.fixture_name(MSAP) == "residential__pages__incentives__maryland-solar-access-program"


# ---------- page parsing ----------

def test_page_payload_needs_the_mdgov_body():
    assert me.page_payload("https://energy.maryland.gov/x", "<html><main><p>nothing</p></main></html>") is None
    p = me.page_payload("https://energy.maryland.gov/x", f"<html><head><title>T</title></head><body>{section('<p>Status: Open</p>')}</body></html>")
    assert p is not None and p["title"] == "T" and p["content_hash"] == me.text_hash(p["main_html"])


def test_text_hash_ignores_cloudflare_email_markup():
    a = section('<p>Contact <a class="__cf_email__" data-cfemail="b6d1d7">[email protected]</a></p>')
    b = section('<p>Contact <a class="__cf_email__" data-cfemail="0f3a2c">[email protected]</a></p>')
    assert a != b and me.text_hash(a) == me.text_hash(b)
    assert me.text_hash(a) != me.text_hash(section("<p>Contact nobody</p>"))


def test_labeled_lines_take_an_empty_value_from_the_next_block_and_own_text_from_nested_divs():
    html = section(
        '<div><strong>Type of Program:</strong></div><div>Rebate Program</div>'
        '<div><strong>Target Audience: </strong><span>county and municipal governments</span>'
        '<div><strong>Program Launch Date:</strong> September 9, 2026</div></div>'
        '<p><strong>Application Deadline:</strong></p><p><strong>Online Application Portal Status:</strong> Open</p>'
    )
    assert me.labeled_lines(html) == [
        ("program_type", "Type of Program", "Rebate Program"),
        ("audience", "Target Audience", "county and municipal governments"),
        ("launch", "Program Launch Date", "September 9, 2026"),
        ("deadline", "Application Deadline", ""),                 # the next line is itself a known label
        ("status", "Online Application Portal Status", "Open"),
    ]


@pytest.mark.parametrize("label, kind", [
    ("Online Application Portal Status", "status"), ("FY26 Program Status", "status"), ("Application Status", "status"),
    ("Application Deadline", "deadline"), ("Program Application Deadline", "deadline"),
    ("Anticipated Application Deadline", "deadline"), ("FY27 Application Deadline", "deadline"),
    ("Program Launch Date", "launch"), ("Funding Opportunity Announcement Issue Date", "launch"),
    ("Target Audience", "audience"), ("Eligible Applicants", "audience"), ("Eligible entity types are", "audience"),
    ("Program Type", "program_type"), ("Type of Program", "program_type"), ("Type of Grant Program", "program_type"),
    ("Anticipated Program Budget", None), ("Program Contact", None), ("June 8, 2026 UPDATE", None),
])
def test_label_kinds(label, kind):
    assert me.label_kind(label) == kind


@pytest.mark.parametrize("value, expected", [
    ("3:00 PM ET, November 18, 2026 through the JotForm application portal. The portal may close early.", date(2026, 11, 18)),
    ("December 9, 2026 - 3:00 PM Eastern Time", date(2026, 12, 9)),
    ("3:00 P.M. ET, Monday, February 11, 2026.", date(2026, 2, 11)),
    ("Stage 1: 3:00 PM Eastern Time December 02, 2026", date(2026, 12, 2)),
    ("December 31, 2025 – 5:00pm EST", date(2025, 12, 31)),
    ("November 21, 2025, at 3:00 PM ET.", date(2025, 11, 21)),
    ("Deadline Extended: Wednesday, November 19th at 5PM.", None),                       # no year
    ("None. The program remains open until funding is expended.", None),
    ("The FY26 program’s final program budget is $8,800,000. MEA received 57 applications by Jan 5, 2026.", None),  # not in the first sentence
    ("", None), (None, None),
])
def test_deadline_dates(value, expected):
    assert me.parse_text_date(value) == expected


def fields(body: str, index: dict | None = None, today: date = TODAY) -> dict:
    return me.status_fields_for(section(body), index or {}, today)


def test_status_line_decides_first_and_the_first_status_line_wins():
    assert fields("<p>Online Application Portal Status: Open to new applications</p><p>The program is CLOSED.</p>")["status"] == "open"
    assert fields("<p>FY26 Program Status: The application portal is currently CLOSED to new applications.</p><p>Now Open!</p>")["status"] == "closed"
    assert fields("<p>FY27 Online Application Portal Status: Open to new applications</p><p>Application Status: Closed</p>")["status"] == "open"


def test_prose_closed_beats_open_and_funding_depletion_is_exhausted():
    assert fields("<p>Now Open! FY27 Program</p>")["status"] == "open"
    assert fields("<p>The L-GEM Program is CLOSED</p><p>Applications are accepted on a rolling basis.</p>")["status"] == "closed"
    assert fields("<p>The FY26 program is closed.</p>")["status"] == "closed"
    assert fields("<p>DUE TO THE FY26 FUNDING DEPLETION, THE APPLICATION PORTAL IS NOW CLOSED.</p>")["status"] == "exhausted"
    assert fields("<p>THIS PROGRAM IS INACTIVE AND IS NO LONGER ACCEPTING APPLICATIONS, PER STATE LAW.</p>"
                  "<p>Funding Depleted: MEA is no longer accepting applications.</p>")["status"] == "closed"
    assert fields("<p>FY26 PROGRAM NOW ACCEPTING APPLICATIONS</p>")["status"] == "open"
    assert fields("<p>The online application portal may close to new applications prior to the deadline.</p>")["status"] == "unknown"


def test_future_launch_date_turns_closed_or_undecided_into_forecasted():
    f = fields("<p>Online Application Portal Status: Closed to New Applications</p>"
               "<p>Funding Opportunity Announcement Issue Date: October 26, 2026</p><p>Application Deadline: Stage 1: November 30, 2026</p>")
    assert f["status"] == "forecasted" and f["opens_at"] == date(2026, 10, 26) and f["closes_at"] == date(2026, 11, 30)
    assert fields("<p>Status: Closed</p><p>Program Launch Date: July 1, 2026</p>")["status"] == "closed"      # past launch
    assert fields("<p>Attention: The FY27 program opens on November 2, 2026.</p>")["status"] == "forecasted"  # prose date
    assert fields("<p>Status: Open</p><p>Program Launch Date: November 2, 2026</p>")["status"] == "open"        # open stays open


def test_deadline_only_pages_and_archived_programs():
    assert fields("<p>Application Deadline: December 9, 2026</p>")["status"] == "open"
    assert fields("<p>Application Deadline: January 21, 2025</p>")["status"] == "unknown"                        # stale, not closed
    assert fields("<p>Application Deadline: January 21, 2025</p>")["closes_at"] == date(2025, 1, 21)
    assert fields("<p>Nothing here.</p>")["status"] == "unknown"
    assert fields("<p>Status: Open</p>", {"transportation/pages/incentives.aspx": "Archived Programs"})["status"] == "closed"
    assert fields("<p>Status: Open</p>", {"transportation/pages/incentives.aspx": "Archived Programs", "pages/renewables.aspx": "Grants"})["status"] == "open"


def test_rolling_and_timing_text():
    f = fields("<p>FY26 PROGRAM NOW ACCEPTING APPLICATIONS</p>"
               "<p>Program Application Deadline: None. The program remains open until funding is expended.</p>")
    assert f["status"] == "open" and f["rolling"] is True and f["closes_at"] is None
    assert f["closes_at_text"] == "Program Application Deadline: None. The program remains open until funding is expended."
    assert fields("<p>Status: Closed</p><p>Application Deadline: ongoing</p>")["rolling"] is None


@pytest.mark.parametrize("name, body, expected", [
    ("Geothermal Rebate Program", "", "rebate"),
    ("Maryland Energy Storage Income Tax Credit", "", "tax_credit"),
    ("Jane E. Lawton Conservation Loan Program", "", "loan"),
    ("Community Solar Grant Program", "", "grant"),
    ("Residential and Commercial Energy Storage Program", "<p>Type of Program: Rebate Program</p>", "rebate"),
    ("Megawatts For Maryland", "<p>Type of Grant Program: Competitive Auction (closed bids)</p>", "grant"),
    ("Energy Challenge", "<p>Program Type: Competitive Challenge</p>", "other"),
    ("Solar Technical Assistance Program", "<p>Type of Program: Non-competitive program.</p>", None),
])
def test_funding_type_rules(name, body, expected):
    assert me.funding_type_for_page(name, section(body)) == expected


def test_program_name_strips_the_fiscal_year_prefix():
    assert me.program_name(section("", "FY27 Commercial & Community Buildings Grant Program"), None) == "Commercial & Community Buildings Grant Program"
    assert me.program_name(section("", "FY25 Maryland RISE Program"), None) == "Maryland RISE Program"
    assert me.program_name('<section class="mdgov-section"><div class="ms-rtestate-field"></div></section>', "From Title") == "From Title"


# ---------- normalize ----------

def test_normalize_open_grant_with_labels_and_federal_money():
    p = normalize(SOLARAPP)
    assert p.name == "Maryland SolarAPP+ Implementation Grant Program" and p.agency_code == "MD-MEA"
    assert p.level == "state" and p.jurisdiction == "MD" and p.funding_type == "grant"
    assert p.funding_source == "pass_through" and p.alns == ["81.041"]
    assert p.status == "open" and p.opens_at == date(2026, 7, 1) and p.closes_at == date(2026, 11, 18) and p.rolling is None
    assert p.closes_at_text.startswith("Funding Opportunity Announcement Issue Date: July 1, 2026; Application Deadline: 3:00 PM ET, November 18, 2026")
    assert p.eligibility_text.startswith("Target Audience: Maryland counties, cities, towns")
    assert p.applicant_pairs() == [("county", "counties"), ("municipality", "cities"), ("municipality", "towns")]
    assert p.category_pairs() == [("energy", "mea")]
    assert (p.amount_min, p.amount_max) == (None, None) and p.summary


def test_normalize_now_open_prose_with_launch_date_and_municipal_wording():
    p = normalize(CCB)
    assert p.name == "Commercial & Community Buildings Grant Program"
    assert p.status == "open" and p.opens_at == date(2026, 9, 9) and p.closes_at == date(2026, 12, 9)
    assert ("municipality", "municipal") in p.applicant_pairs() and ("county", "county") in p.applicant_pairs()
    assert p.source_url == "https://energy.maryland.gov/Pages/Commercial%26CommunityBuildingsGrantProgram.aspx"


def test_normalize_transportation_index_adds_a_category():
    p = normalize(EVSE)
    assert p.status == "open" and p.closes_at == date(2026, 12, 9)
    assert p.category_pairs() == [("energy", "mea"), ("transportation", "transportation/pages/incentives.aspx")]
    assert ("municipality", "local governments") in p.applicant_pairs() and ("school", "local education agencies") in p.applicant_pairs()


def test_normalize_closed_prose_with_may_apply_sentence():
    p = normalize(LGEM)
    assert p.status == "closed" and p.closes_at == date(2025, 12, 5)   # the stated deadline is kept even though the page says CLOSED
    assert p.closes_at_text == "Application Deadline: 5:00 P.M. ET, December 5, 2025"
    assert p.applicant_pairs() == [("county", "counties"), ("municipality", "cities"), ("municipality", "towns")]
    assert p.funding_type is None                                     # "Program" with no type keyword anywhere


def test_normalize_fy_status_line():
    p = normalize(RESILIENT)
    assert p.status == "closed" and p.closes_at == date(2025, 12, 31) and p.applicant_pairs() == []


def test_normalize_labels_in_the_next_cell_and_now_open_prose():
    p = normalize(STORAGE)
    assert p.status == "open" and p.closes_at == date(2027, 5, 31) and p.funding_type == "rebate"
    assert ("household", "households") in p.applicant_pairs()


def test_normalize_two_fiscal_years_first_status_wins():
    p = normalize(MSAP)
    assert p.status == "open" and p.opens_at == date(2026, 7, 29) and p.closes_at == date(2027, 5, 31)
    assert p.funding_type == "rebate" and p.applicant_pairs() == [("household", "homeowner"), ("household", "households")]


def test_normalize_rolling_technical_assistance():
    p = normalize(SOLAR_TA)
    assert p.status == "open" and p.rolling is True and p.closes_at is None and p.funding_type is None
    assert p.applicant_pairs() == []                                   # "provides ... to state and local government entities" is not an applicant sentence


def test_normalize_page_with_nothing_to_read_is_unknown():
    p = normalize(LAWTON)
    assert p.status == "unknown" and p.closes_at_text is None and p.funding_type == "loan"
    assert p.applicant_pairs() == [] and p.eligibility_text is None


def test_normalize_closed_portal_with_future_announcement_is_forecasted():
    p = normalize(MEGAWATTS)
    assert p.status == "forecasted" and p.opens_at == date(2026, 10, 26) and p.closes_at == date(2026, 11, 30)
    assert p.applicant_pairs() == [("business", "businesses")] and p.funding_type == "grant"
    # the day after the announcement the same page, unchanged, reads closed again (the portal line still says so)
    assert normalize(MEGAWATTS).status == "forecasted"
    assert me.normalize(RawRecord(source_connector=me.CONNECTOR, source_id=MEGAWATTS, payload=payload(MEGAWATTS)), today=date(2026, 10, 27)).status == "closed"


def test_normalize_funding_depletion_is_exhausted():
    p = normalize(COMMERCIAL_SOLAR)
    assert p.status == "exhausted" and p.closes_at == date(2026, 2, 11) and p.applicant_pairs() == []


def test_normalize_invents_nothing_from_a_bare_page():
    raw = RawRecord(source_connector=me.CONNECTOR, source_id="pages/bare.aspx", payload={
        "url": f"{me.BASE}/Pages/Bare.aspx", "title": None, "description": None, "index": {"pages/renewables.aspx": "Grants"},
        "main_html": section("<p>A program.</p>", "Bare Program"),
    })
    p = me.normalize(raw, today=TODAY)
    assert p.status == "unknown" and p.opens_at is None and p.closes_at is None and p.closes_at_text is None and p.rolling is None
    assert p.summary is None and p.eligibility_text is None and p.applicant_types == [] and p.funding_type is None
    assert p.match_required is None and p.alns == [] and p.funding_source == "direct"
    assert p.record_hash


def test_hash_is_stable_and_changes_with_the_index_heading():
    assert normalize(SOLARAPP).record_hash == normalize(SOLARAPP).record_hash
    archived = normalize(SOLARAPP, index={"transportation/pages/incentives.aspx": "Archived Programs"})
    assert archived.status == "closed" and archived.record_hash != normalize(SOLARAPP).record_hash


def test_classify_page():
    assert me.classify_page(None) == {"status": "unknown"}
    assert me.classify_page(payload(SOLARAPP), TODAY) == {"status": "open", "closes_at": date(2026, 11, 18)}
    assert me.classify_page(payload(LAWTON), TODAY) == {"status": "unknown", "closes_at": None}
