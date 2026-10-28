"""Illinois CSFA connector tests. Everything runs against the saved pages (never the network): the list table, the
agency table, six native opportunity pages with their programs, and three GMS rows."""

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
GMS_DNR = "gms-03fbb261-9c67-41da-a64b-7cd5b2532e35"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def list_rows() -> dict[str, dict]:
    return {r["source_id"]: r for r in il.parse_list(read("OpportunityList.html"))}


def payload(source_id: str) -> dict:
    row = list_rows()[source_id]
    agencies = il.parse_agencies(read("AgencyList.html"))
    out = {"list": row, "agency_name": agencies.get(il.split_agency(row["agency"])[1] or ""),
           "opportunity": None, "program": None, "program_id": None}
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
    assert len(rows) == 9
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


def test_gms_row_has_only_what_the_list_says():
    p = normalize(GMS_DNR)
    assert p.administering_agency == "Department Of Natural Resources" and p.agency_code == "IL-DNR"
    assert p.external_number is None and p.summary is None and p.eligibility_text is None
    assert p.applicant_types == [] and p.categories == []
    assert (p.funding_type, p.funding_source, p.match_required) == (None, "direct", None)
    assert p.source_url.startswith("https://il.amplifund.com/Public/Opportunities/Details/")


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


def test_fetch_reads_each_program_once_and_never_amplifund(pages):
    records = il.fetch()
    assert len(records) == 9
    assert not any("amplifund" in url for url in pages.calls)
    programs = [u for u in pages.calls if "Program.aspx" in u]
    assert len(programs) == len(set(programs)) == 5
    by_id = {r.source_id: r.payload for r in records}
    assert by_id["nofo-4240"]["program"] is by_id["nofo-4334"]["program"]
    assert by_id[GMS_DNR]["opportunity"] is None and by_id[GMS_DNR]["agency_name"] == "Department Of Natural Resources"


def test_fetch_limit_and_unreadable_detail_falls_back_to_prior(monkeypatch, pages):
    first = {r.source_id: r.payload for r in il.fetch()}
    monkeypatch.setattr(il, "_get", _Pages(broken={il.OPPORTUNITY_URL.format(n="2023")}))
    again = il.fetch(prior=first)
    got = {r.source_id: r.payload for r in again}
    assert got["nofo-2023"]["opportunity"] == first["nofo-2023"]["opportunity"]
    assert got["nofo-2023"]["program"] == first["nofo-2023"]["program"]
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
