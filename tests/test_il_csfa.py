"""Illinois CSFA connector tests. Everything runs against the saved pages (never the network): the list table, the
agency table, six native opportunity pages with their programs, and five GMS rows with their AmpliFund pages."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import il_csfa as il
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "il_csfa"
TODAY = date(2026, 10, 28)
GMS_NO_END = "gms-0f9fad21-8730-4308-9a6e-d2b062587e1b"
GMS_DATED = "gms-385d1fbd-95b2-42eb-9181-29efa73ee574"
GMS_DNR = "gms-03fbb261-9c67-41da-a64b-7cd5b2532e35"          # CMP Coastal: "units of local government" free text
GMS_NEGATED = "gms-10ebd914-6f5a-43f4-a311-5574c65e5ba6"      # PR Wildlife FY27: "not open to ... local units of government"
GMS_SCIP = "gms-abba654d-8098-44ea-bc9f-f998bc64abcd"         # ICJIA SCIP: Grants.gov-style labels


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def list_rows() -> dict[str, dict]:
    return {r["source_id"]: r for r in il.parse_list(read("OpportunityList.html"))}


def payload(source_id: str) -> dict:
    row = list_rows()[source_id]
    agencies = il.parse_agencies(read("AgencyList.html"))
    out = {"list": row, "agency_name": agencies.get(il.split_agency(row["agency"])[1] or ""),
           "opportunity": None, "program": None, "program_id": None, "amplifund": None}
    if row["kind"] == "gms":
        out["amplifund"] = il.parse_amplifund(read(f"amplifund_{source_id[4:]}.html"))
    if row["kind"] == "nofo":
        n = source_id.split("-", 1)[1]
        opp_html = read(f"opportunity_{n}.html")
        csfa = il.program_number(opp_html)
        out.update(opportunity=il.parse_fields(opp_html), program=il.parse_fields(read(f"program_{csfa}.html")),
                   program_id=csfa)
    return out


def normalize(source_id: str):
    return il.normalize(RawRecord(source_connector=il.CONNECTOR, source_id=source_id, payload=payload(source_id)), TODAY)


# ---------- parsing ----------

def test_list_has_both_row_shapes():
    rows = list_rows()
    assert len(rows) == 11
    assert {r["kind"] for r in rows.values()} == {"nofo", "gms"}
    assert rows["nofo-2023"]["url"] == "https://omb.illinois.gov/public/gata/csfa/Opportunity.aspx?nofo=2023"
    assert rows["nofo-2023"]["agency"] == "DCEO (420)" and rows["nofo-2023"]["award_range"] == "$250000 - $25000000"


def test_gms_rows_are_keyed_by_the_amplifund_guid_and_link_straight_to_it():
    row = list_rows()[GMS_DATED]
    assert row["url"] == "https://il.amplifund.com/Public/Opportunities/Details/385d1fbd-95b2-42eb-9181-29efa73ee574"
    assert "GMS.aspx" not in row["url"]


def test_amplifund_target_none_without_url_parameter():
    assert il.amplifund_target("GMS.aspx") is None


def test_parse_agencies_maps_number_to_name():
    agencies = il.parse_agencies(read("AgencyList.html"))
    assert agencies["420"] == "Department Of Commerce And Economic Opportunity"
    assert agencies["422"] == "Department Of Natural Resources" and len(agencies) >= 30


def test_parse_fields_keeps_lines_apart():
    program = il.parse_fields(read("program_2608.html"))
    assert program["div_Program_Name"] == "Business Attraction Prime Sites"
    assert program["div_Eligible_Applicants"] == "Nonprofit Organizations; For-Profit Organizations;"
    assert program["div_Applicant_Eligibility"].count("\n") >= 2


@pytest.mark.parametrize("text, expected", [
    ("04/03/2025 - No end date", (date(2025, 4, 3), None, True)),
    ("09/20/2021 - 06/30/2027", (date(2021, 9, 20), date(2027, 6, 30), False)),
    ("garbage", (None, None, False)),
])
def test_date_range(text, expected):
    assert il.date_range(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("$250000 - $25000000", (250000, 25000000)), ("$0 - $250000", (0, 250000)), ("Not Applicable", (None, None)),
])
def test_amount_fields(text, expected):
    assert il.amount_fields(text) == expected


# ---------- mapping ----------

def test_native_row_fields():
    p = normalize("nofo-2023")
    assert p.source_url.endswith("Opportunity.aspx?nofo=2023")
    assert p.external_number == "420-45-2608"
    assert p.level == "state" and p.jurisdiction == "IL" and p.alns == []
    assert p.administering_agency == "Department Of Commerce And Economic Opportunity" and p.agency_code == "IL-DCEO"
    assert (p.funding_type, p.funding_source, p.match_required) == ("grant", "direct", True)
    assert (p.amount_min, p.amount_max) == (250000, 25000000)
    assert p.summary and "Prime Sites" in p.summary


def test_federal_source_is_pass_through_and_not_applicable_award_is_null():
    assert normalize("nofo-4337").funding_source == "pass_through"
    assert (normalize("nofo-4337").amount_min, normalize("nofo-4337").amount_max) == (None, None)


def test_gms_row_reads_its_amplifund_page():
    p = normalize(GMS_DNR)
    assert p.administering_agency == "Department Of Natural Resources" and p.agency_code == "IL-DNR"
    assert p.external_number == "422-30-0103" and p.summary and "coastal" in p.summary
    assert p.eligibility_text.startswith("Eligible applicants: Government Organizations; Education Organizations; Nonprofit Organizations")
    assert "units of local government" in p.eligibility_text
    assert {"municipality", "county"} <= {t.value for t in p.applicant_types}
    assert (p.funding_type, p.funding_source) == (None, "pass_through")       # "Federal Or Federal Pass Through"
    assert p.source_url.startswith("https://il.amplifund.com/Public/Opportunities/Details/")
    assert p.eligibility_structured["eligible_applicants"] == ["Government Organizations", "Education Organizations", "Nonprofit Organizations"]
    assert p.eligibility_structured["submission_timeline"] in ("Rolling", "One Time")


def test_gms_row_without_an_amplifund_page_has_only_what_the_list_says():
    data = payload(GMS_DNR)
    data["amplifund"] = None
    p = il.normalize(RawRecord(source_connector=il.CONNECTOR, source_id=GMS_DNR, payload=data), TODAY)
    assert p.external_number is None and p.summary is None and p.eligibility_text is None
    assert p.applicant_types == [] and p.categories == []
    assert (p.funding_type, p.funding_source, p.match_required) == (None, "direct", None)


def test_amplifund_fields_and_no_contact():
    fields = il.parse_amplifund(read(f"amplifund_{GMS_SCIP[4:]}.html"))
    assert fields["CSFA Number"] and fields["Funding Sources"] == "Federal Or Federal Pass Through"
    assert fields["Eligible Applicants"].startswith("State Governments, County Governments, City or township governments")
    assert not any(k in fields for k in il.AMPLIFUND_CONTACT)
    assert "Matching Requirement" not in fields                       # absent on this page: match_required stays null


def test_grants_gov_style_labels_tag_by_table():
    pairs = normalize(GMS_SCIP).applicant_pairs()
    assert ("county", "County Governments") in pairs and ("municipality", "City or township governments") in pairs
    assert ("state", "State Governments") in pairs and ("special_district", "Special District Governments") in pairs
    assert normalize(GMS_SCIP).category_pairs() == [("public_safety", "Law, Justice, and Legal Services")]
    assert normalize(GMS_SCIP).match_required is None


def test_a_negated_sentence_tags_nothing():
    """PR Wildlife Restoration: "This opportunity is currently not open to Forest Preserve Districts or local units of
    government." names local units of government only to exclude them."""
    p = normalize(GMS_NEGATED)
    assert "not open to" in p.eligibility_text
    assert not {"municipality", "county"} & {t.value for t in p.applicant_types}
    assert p.category_pairs() == [("other", "Natural Resources")]


@pytest.mark.parametrize("text, expected", [
    ("Education Employment, Labor, and Training", ["Education", "Employment, Labor, and Training"]),
    ("Environment, Natural Resources", ["Environment", "Natural Resources"]),
    ("Law, Justice, and Legal Services", ["Law, Justice, and Legal Services"]),
    ("Natural Resources", ["Natural Resources"]),
    ("Something New, Housing", ["Something New, Housing"]),
    ("", []),
])
def test_split_categories(text, expected):
    assert il.split_categories(text) == expected


def test_nofo_quotes_feed_the_tagger_and_the_text_for_the_rounds_that_have_them():
    row = {**list_rows()["nofo-2004"], "source_id": "nofo-4240"}
    data = {**payload("nofo-2004"), "list": row}
    data["program"] = {**data["program"], "div_Applicant_Eligibility": "SEE NOFO"}
    p = il.normalize(RawRecord(source_connector=il.CONNECTOR, source_id="nofo-4240", payload=data), TODAY)
    assert {"municipality", "county"} <= {t.value for t in p.applicant_types}
    assert "NOFO (read 2026-11-03): This grant opportunity will be limited to the following types of entities: Units of local government" in p.eligibility_text
    assert il.nofo_quotes("nofo-2004") == [] and il.nofo_quotes(GMS_DNR) == []
    assert all(n.isdigit() and read_on.startswith("2026-") and quotes for n, (read_on, quotes) in il.NOFO_QUOTES.items())


def test_unknown_agency_number_falls_back_to_the_list_text():
    data = payload(GMS_DNR)
    data["agency_name"] = None
    p = il.normalize(RawRecord(source_connector=il.CONNECTOR, source_id=GMS_DNR, payload=data), TODAY)
    assert p.administering_agency == "DNR"


# ---------- status and dates ----------

def test_dates_and_rolling():
    open_ended = normalize("nofo-2010")
    assert open_ended.opens_at == date(2022, 4, 5) and open_ended.closes_at is None
    assert open_ended.closes_at_text == "No end date" and open_ended.rolling is True
    dated = normalize("nofo-2023")
    assert dated.closes_at == date(2027, 6, 30) and dated.closes_at_text is None and dated.rolling is None


@pytest.mark.parametrize("start, end, today, status", [
    (date(2026, 1, 1), None, TODAY, "open"),
    (date(2026, 1, 1), date(2026, 12, 1), TODAY, "open"),
    (date(2026, 1, 1), date(2026, 10, 28), TODAY, "open"),
    (date(2026, 1, 1), date(2026, 10, 27), TODAY, "closed"),
    (date(2026, 11, 1), date(2026, 12, 1), TODAY, "forecasted"),
])
def test_status_for(start, end, today, status):
    assert il.status_for(start, end, today) == status


def test_every_row_on_the_list_is_open_on_the_fixture_day():
    assert {normalize(sid).status for sid in list_rows()} == {"open"}


# ---------- applicants and categories ----------

def test_government_organizations_alone_tags_nothing():
    assert normalize("nofo-2004").applicant_types == []


def test_portal_types_then_free_text_without_duplicates():
    pairs = normalize("nofo-4240").applicant_pairs()
    values = [v for v, _ in pairs]
    assert len(values) == len(set(values))
    assert ("nonprofit", "Nonprofit Organizations") in pairs and ("individual", "Individuals") in pairs
    assert ("business", "For-Profit Organizations") in pairs


def test_local_government_free_text_tags_municipality_and_county():
    values = {v for v, _ in normalize("nofo-2010").applicant_pairs()}
    assert {"municipality", "county"} <= values


def test_categories_and_eligibility_text():
    assert normalize("nofo-2010").category_pairs() == [("public_safety", "Public Safety")]
    assert normalize("nofo-2023").category_pairs() == [("infrastructure", "Economic Development")]
    p = normalize("nofo-2010")
    assert p.eligibility_text.startswith("Eligible applicants: Government Organizations")
    assert "Applicant eligibility: Only units of general local government" in p.eligibility_text
    assert p.eligibility_structured == {"eligible_applicants": ["Government Organizations"], "subject_area": "Public Safety"}


# ---------- fetch ----------

class _Pages:
    """A stand-in for `_get`: URL -> saved page, failing for URLs in `broken`."""

    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        if url == il.LIST_URL:
            return read("OpportunityList.html")
        if url == il.AGENCY_URL:
            return read("AgencyList.html")
        if "amplifund.com" in url:
            return read(f"amplifund_{url.rstrip('/').rsplit('/', 1)[-1]}.html")
        n = url.rsplit("=", 1)[1]
        if url.startswith(il.OPPORTUNITY_URL.split("{")[0]):
            return read(f"opportunity_{n}.html")
        return read(f"program_{n}.html")


@pytest.fixture
def pages(monkeypatch):
    monkeypatch.setattr(il.time, "sleep", lambda s: None)
    stub = _Pages()
    monkeypatch.setattr(il, "_get", stub)
    return stub


def test_fetch_reads_each_program_once_and_each_amplifund_page(pages):
    records = il.fetch()
    assert len(records) == 11
    assert len([url for url in pages.calls if "amplifund.com" in url]) == 5
    programs = [u for u in pages.calls if "Program.aspx" in u]
    assert len(programs) == len(set(programs)) == 5
    by_id = {r.source_id: r.payload for r in records}
    assert by_id["nofo-4240"]["program"] is by_id["nofo-4334"]["program"]
    assert by_id[GMS_DNR]["opportunity"] is None and by_id[GMS_DNR]["agency_name"] == "Department Of Natural Resources"
    assert by_id[GMS_DNR]["amplifund"]["CSFA Number"] == "422-30-0103" and by_id["nofo-2023"]["amplifund"] is None


def test_fetch_limit_and_unreadable_detail_falls_back_to_prior(monkeypatch, pages):
    first = {r.source_id: r.payload for r in il.fetch()}
    monkeypatch.setattr(il, "_get", _Pages(broken={il.OPPORTUNITY_URL.format(n="2023")}))
    again = il.fetch(prior=first)
    got = {r.source_id: r.payload for r in again}
    assert got["nofo-2023"]["opportunity"] == first["nofo-2023"]["opportunity"]
    assert got["nofo-2023"]["program"] == first["nofo-2023"]["program"]
    monkeypatch.setattr(il, "_get", _Pages(broken={list_rows()[GMS_DNR]["url"]}))
    assert {r.source_id: r.payload for r in il.fetch(prior=first)}[GMS_DNR]["amplifund"] == first[GMS_DNR]["amplifund"]
    assert {r.source_id: r.payload for r in il.fetch()}[GMS_DNR]["amplifund"] is None
    assert len(il.fetch(limit=2)) == 2


# ---------- resolve_missing ----------

def test_resolve_missing_gms_is_unknown_without_a_request(monkeypatch):
    monkeypatch.setattr(il, "_get", lambda *a: pytest.fail("no request for GMS"))
    assert il.resolve_missing(GMS_DNR) == {"status": "unknown"}


def test_resolve_missing_native_ended_range_closes(monkeypatch):
    html = read("opportunity_2023.html").replace("09/20/2021 - 06/30/2027", "09/20/2021 - 06/30/2026")
    monkeypatch.setattr(il, "_get", lambda client, url: html)
    assert il.resolve_missing("nofo-2023") == {"status": "closed", "closes_at": date(2026, 6, 30)}


def test_resolve_missing_native_still_open_or_dateless_is_unknown(monkeypatch):
    monkeypatch.setattr(il, "_get", lambda client, url: read("opportunity_2023.html"))
    assert il.resolve_missing("nofo-2023") == {"status": "unknown"}


def test_resolve_missing_unreadable_is_none(monkeypatch):
    def boom(client, url):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(il, "_get", boom)
    assert il.resolve_missing("nofo-2023") is None
