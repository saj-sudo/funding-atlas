"""Maryland DNR connector tests. Mapping tests run against saved page fixtures (never the network); the index
parser, name, status, deadline and applicant rules are pure functions tested directly."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import maryland_sharepoint as sp
from connectors import md_dnr as dn
from pipeline.models import RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "md_dnr"
TODAY = date(2026, 10, 16)

CPP = "land/pages/programopenspace/cpp.aspx"
LWCF = "land/pages/lwcf-grants.aspx"
WIF = "boating/pages/grants.aspx"
POS = "land/pages/programopenspace/home.aspx"
KMB = "met/pages/grant_programs.aspx"
GATEWAY = "ccs/pages/funding/grantsgateway.aspx"
LEGACY = "forests/pages/programapps/forestlegacy.aspx"
TAX = "met/pages/tax_benefits.aspx"
GREENSPACE = "land/pages/greenspace-equity-program.aspx"


def payload(source_id: str) -> dict:
    return json.loads((FIXTURES / f"{sp.fixture_name(source_id)}.json").read_text())


def normalize(source_id: str, **overrides):
    p = {**payload(source_id), **overrides}
    return dn.normalize(RawRecord(source_connector=dn.CONNECTOR, source_id=source_id, payload=p), today=TODAY)


def section(body: str, h1: str = "Some Program") -> str:
    return (f'<section class="mdgov-section"><div id="ctl00_PlaceHolderMain_editmodepanel2"><h1>{h1}</h1></div>'
            f'<div id="ctl00_PlaceHolderMain_RichHtmlField1__ControlWrapper_RichHtmlField" class="ms-rtestate-field">'
            f'{body}</div></section>')


def fields(body: str, today: date = TODAY) -> dict:
    return dn.status_fields_for(section(body), today)


# ---------- enumeration ----------

def test_index_links_group_pages_by_section_and_unit():
    data = json.loads((FIXTURES / "index__pages__grantsandloans.json").read_text())
    links = dn.index_links(data["url"], data["main_html"])
    assert len(links) == 21                                          # 19 live + 2 dead, all distinct after normalization
    assert links[CPP] == {"url": "https://dnr.maryland.gov/land/Pages/ProgramOpenSpace/cpp.aspx",
                          "section": "Financial and Technical Resources", "unit": "Land Acquisition and Planning", "listed": True}
    assert links["wildlife/pages/habitat/milo.aspx"]["section"] == "Cost-share Programs"
    assert links["wildlife/pages/habitat/milo.aspx"]["unit"] == "Wildlife and Heritage Service"
    assert links["boating/pages/pumpout/grants.aspx"]["url"].startswith("https://")       # linked as http://
    assert links["met/pages/grant-ee-ci-cu.aspx"]["unit"] == "Maryland Environmental Trust"   # three fragment links -> one page
    assert links["forests/pages/programapps/fcmp.aspx"]["section"] == "Financial and Technical Resources"  # first of two sections
    assert not [sid for sid in links if "cbtrust" in sid or sid.endswith(".pdf") or sid == dn.INDEX_PATH]
    assert WIF not in links                                          # hand-added, not on the index


def test_hand_added_wif_is_enumerated_as_unlisted():
    entry = dn.HAND_ADDED[WIF]
    assert entry["listed"] is False and entry["unit"] == "Boating Services"
    assert payload(WIF)["listed"] is False and payload(CPP)["listed"] is True


# ---------- names ----------

def test_name_rule_unit_h1_falls_back_to_the_first_h2():
    assert dn.program_name(section("<h2>Community Parks and Playgrounds Program</h2>", "Land Acquisition and Planning"), None) == "Community Parks and Playgrounds Program"
    assert dn.program_name(section("<h2>Tax Benefits of Conservation Easement Donations</h2>", ""), "T") == "Tax Benefits of Conservation Easement Donations"
    assert dn.program_name(section("<h2>Application period opens on September 3, 2026.</h2>", "Keep Maryland Beautiful Grant Program"), None) == "Keep Maryland Beautiful Grant Program"
    assert dn.program_name(section("<p>no headings</p>", ""), "From Title") == "From Title"


# ---------- status rules ----------

def test_closed_sentence_and_forecast_month():
    f = fields("<p>UPDATE: The application period for LWCF grant funding is now closed.</p><p>Check back in April 2027 for information about the next round of funding.</p>")
    assert f["status"] == "forecasted" and f["opens_at"] is None and f["closes_at"] is None
    assert f["closes_at_text"] == ("UPDATE: The application period for LWCF grant funding is now closed. "
                                   "Check back in April 2027 for information about the next round of funding.")
    assert fields("<p>Applications are not currently being accepted.</p><p>Check back in April 2026.</p>")["status"] == "closed"   # past month
    assert fields("<p>The application period for the Fiscal Year 2028 grant is now closed.</p>")["status"] == "closed"
    assert fields("<p>Applications are not being accepted. The next round opens on March 1, 2027.</p>")["opens_at"] == date(2027, 3, 1)


def test_open_sentences_negation_and_rolling():
    assert fields("<p>The 2025 VFA Grant application period is now open and closes on September 15, 2025 at 4:00 p.m.</p>") == {
        "status": "open", "opens_at": None, "closes_at": date(2025, 9, 15), "rolling": None,
        "closes_at_text": "The 2025 VFA Grant application period is now open and closes on September 15, 2025 at 4:00 p.m.",
    }
    f = fields("<p>Applications are accepted on a rolling basis and evaluated annually.</p>")
    assert f["status"] == "open" and f["rolling"] is True
    assert fields("<p>The WIF is no longer accepting applications through the Grants Gateway solicitation.</p>")["status"] == "unknown"
    assert fields("<p>Applications are not accepted on a rolling basis.</p>")["status"] == "unknown"


def test_deadline_sentences_take_the_latest_application_date():
    body = ("<p>FY2028 Request for Solicitation OPENS on July 15, 2026</p>"
            "<p>Beneficial Use Applications due: September 18, 2026 by 11:59 p.m.</p>"
            "<p>All Other Applications due: December 11, 2026 by 11:59 p.m.</p>"
            "<p>*will be accepted on a rolling basis</p>"
            "<p>You will be notified by February 1, 2027, if your application was approved.</p>"
            "<p>Final grant reports are due by March 2, 2028.</p>")
    f = fields(body)
    assert f["status"] == "open" and f["opens_at"] == date(2026, 7, 15) and f["closes_at"] == date(2026, 12, 11)
    assert f["rolling"] is None                                      # a dated deadline beats the footnote
    assert "notified" not in f["closes_at_text"] and "reports" not in f["closes_at_text"]
    assert f["closes_at_text"].startswith("FY2028 Request for Solicitation OPENS on July 15, 2026")


def test_deadline_only_pages_are_open_ahead_and_unknown_after():
    assert fields("<p>The Application deadline is December 1, 2026.</p>")["status"] == "open"
    f = fields("<p>Submit applications for State Waterway Improvement Funds via the link below by September 18, 2026, at 11:59 PM.</p>")
    assert f["status"] == "unknown" and f["closes_at"] == date(2026, 9, 18)
    assert fields("<p>You can submit a VFA application for purchases made since January 1, 2025.</p>")["closes_at"] is None   # no deadline word
    assert fields("<p>Funds are allocated annually to the 23 counties based on a formula.</p>")["status"] == "unknown"


@pytest.mark.parametrize("text, expected", [
    ("Check back in April 2027", (True, None)),
    ("Check back in April 2026", (False, None)),
    ("opens on March 1, 2027", (True, date(2027, 3, 1))),
    ("opens on March 1, 2026", (False, date(2026, 3, 1))),
    ("next round", (False, None)),
])
def test_future_marker(text, expected):
    assert dn.future_marker(text, TODAY) == expected


# ---------- normalize ----------

def test_normalize_cpp_closed_with_unit_h1_and_municipal_corporations():
    p = normalize(CPP)
    assert p.name == "Community Parks and Playgrounds Program" and p.agency_code == "MD-DNR"
    assert p.status == "closed" and p.closes_at is None and p.opens_at is None
    assert p.closes_at_text == "The application period for the Fiscal Year 2028 Community Parks and Playgrounds Program grant is now closed."
    assert p.applicant_pairs() == [("municipality", "municipal")]
    assert p.category_pairs() == [("parks", "Land Acquisition and Planning")]
    assert p.funding_type is None and p.funding_source == "direct" and p.summary


def test_normalize_lwcf_forecasted_federal_government_entities():
    p = normalize(LWCF)
    assert p.name == "Land and Water Conservation Fund Grants"
    assert p.status == "forecasted" and p.opens_at is None and p.closes_at is None
    assert p.closes_at_text.startswith("UPDATE: The application period for LWCF grant funding is now closed. Check back in April 2027")
    assert p.funding_source == "pass_through" and p.alns == ["15.916"] and p.funding_type == "grant"
    assert p.applicant_pairs() == [("county", "county"), ("municipality", "municipality"), ("state", "state agency"), ("tribe", "tribe")]


def test_normalize_wif_hand_added_past_deadline_is_unknown():
    p = normalize(WIF)
    assert p.status == "unknown" and p.closes_at == date(2026, 9, 18)
    assert p.closes_at_text == "Submit applications for State Waterway Improvement Funds via the link below by September 18, 2026, at 11:59 PM."
    assert ("municipality", "local governments") in p.applicant_pairs() and ("county", "local governments") in p.applicant_pairs()
    assert p.category_pairs() == [("water", "Boating Services")] and p.funding_type == "grant"


def test_normalize_pos_local_formula_to_counties():
    p = normalize(POS)
    assert p.name == "Program Open Space Local" and p.funding_type == "formula"
    assert p.status == "unknown" and p.closes_at_text is None
    assert p.applicant_pairs() == [("county", "county")]


def test_normalize_keep_maryland_beautiful_dated_window():
    p = normalize(KMB)
    assert p.status == "open" and p.opens_at == date(2026, 9, 3) and p.closes_at == date(2026, 12, 1) and p.rolling is None
    assert p.closes_at_text == "Application period opens on September 3, 2026. The Application deadline is December 1, 2026."
    assert ("municipality", "municipalities") in p.applicant_pairs() and ("nonprofit", "nonprofits") in p.applicant_pairs()
    assert p.category_pairs() == [("other", "Maryland Environmental Trust")] and p.funding_type == "grant"


def test_normalize_grants_gateway_latest_deadline_not_closed_not_rolling():
    p = normalize(GATEWAY)
    assert p.name == "Grants Gateway"
    assert p.status == "open" and p.opens_at == date(2026, 7, 15) and p.closes_at == date(2026, 12, 11) and p.rolling is None
    assert "no longer accepting" not in p.closes_at_text
    assert p.applicant_pairs() == [] and p.category_pairs() == [("water", "Watershed & Climate Services")]


def test_normalize_forest_legacy_rolling_private_land():
    p = normalize(LEGACY)
    assert p.status == "open" and p.rolling is True and p.closes_at is None
    assert p.funding_source == "pass_through" and p.alns == ["10.676"]
    assert p.applicant_pairs() == [] and p.category_pairs() == [("other", "Forest Service")]


def test_normalize_empty_h1_and_unit_h1_fall_back_to_h2():
    assert normalize(TAX).name == "Tax Benefits of Conservation Easement Donations" and normalize(TAX).status == "unknown"
    p = normalize(GREENSPACE)
    assert p.name == "Greenspace Equity Program" and p.status == "closed"


def test_normalize_invents_nothing_from_a_bare_page():
    raw = RawRecord(source_connector=dn.CONNECTOR, source_id="land/pages/bare.aspx", payload={
        "url": f"{dn.BASE}/land/Pages/Bare.aspx", "title": None, "description": None,
        "section": "Financial and Technical Resources", "unit": "Land Acquisition and Planning", "listed": True,
        "main_html": section("<h2>Bare Program</h2><p>A program for parks.</p>", "Land Acquisition and Planning"),
    })
    p = dn.normalize(raw, today=TODAY)
    assert p.name == "Bare Program" and p.status == "unknown"
    assert p.opens_at is None and p.closes_at is None and p.closes_at_text is None and p.rolling is None
    assert p.summary is None and p.eligibility_text is None and p.applicant_types == [] and p.funding_type is None
    assert p.match_required is None and p.alns == [] and p.category_pairs() == [("parks", "Land Acquisition and Planning")]
    assert p.record_hash


def test_hash_is_stable_and_changes_with_the_index_facts():
    assert normalize(CPP).record_hash == normalize(CPP).record_hash
    moved = normalize(CPP, unit="Maryland Environmental Trust")
    assert moved.category_pairs() == [("other", "Maryland Environmental Trust")] and moved.record_hash != normalize(CPP).record_hash


def test_classify_page():
    assert dn.classify_page(None) == {"status": "unknown"}
    assert dn.classify_page(payload(KMB), TODAY) == {"status": "open", "closes_at": date(2026, 12, 1)}
    assert dn.classify_page(payload(CPP), TODAY) == {"status": "closed", "closes_at": None}
