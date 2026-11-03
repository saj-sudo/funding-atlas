"""New York SFS connector tests. Everything runs against the saved answers (never the network): the search page with
four rows, one XML Return-to-Search answer, the closed page with three rows, and the four abstracts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import ny_sfs as ny
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "ny_sfs"
AFTYP3 = "AGM01-AFTYP3"           # Available; Governmental Entity, Not-For-Profit, Tribal Organization; announcement link
FPIG20 = "AGM01-FPIG20"           # Available; a 50-character title
RFA1278 = "CFS01-RFA-1278"        # Advertised Only - Not in SFS; Not-For-Profit; an Event ID with a space
ERPO = "DCJ01-EVT0000010"         # Available; Governmental Entity alone; an Event ID that another agency also uses
ABSTRACT_OF = {0: "abstract_0.html", 1: "abstract_1.html", 3: "abstract_3.html", 4: "abstract_4.html"}


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def rows() -> dict[int, dict]:
    return {r["n"]: r for r in ny.parse_rows(read("search.html"))}


def record(n: int, grid: str = "open") -> RawRecord:
    row = rows()[n]
    abstract = ny.parse_abstract(read(ABSTRACT_OF[n])) if n in ABSTRACT_OF else None
    return RawRecord(source_connector=ny.CONNECTOR, source_id=ny.row_key(row), payload={"grid": grid, "row": row, "abstract": abstract})


def normalize(n: int):
    return ny.normalize(record(n))


# ---------- the grid ----------

def test_rows_parse_from_the_search_page_with_every_cell():
    got = rows()
    assert sorted(got) == [0, 1, 3, 4]
    r = got[0]
    assert (r["event_id"], r["agency_code"], r["name"], r["status"]) == ("AFTYP3", "AGM01", "2027 TYCLF", "Available")
    assert r["eligibility"] == "Governmental Entity, Not-For-Profit, Tribal Organization"
    assert (r["posted"], r["release"], r["due"]) == ("10/02/26 10:10AM", "10/08/26 10:10AM", "12/01/2026 4:00PM EST")
    assert r["linked"] is True


def test_rows_parse_from_the_xml_return_answer_too():
    """Return to Search answers an XML partial whose CDATA holds the same grid."""
    assert read("return.xml").lstrip().startswith("<?xml")
    assert [r["event_id"] for r in ny.parse_rows(read("return.xml"))] == [r["event_id"] for r in ny.parse_rows(read("search.html"))]


def test_closed_rows_with_and_without_a_link():
    got = {r["event_id"]: r for r in ny.parse_rows(read("closed.html"))}
    assert set(got) == {"DCCTPR2025", "AGM-AFTYP1", "AGM-DPO27"}
    assert got["DCCTPR2025"]["linked"] is True and got["AGM-AFTYP1"]["linked"] is False
    assert got["AGM-AFTYP1"]["name"] == "AFTYP 2025" and got["AGM-AFTYP1"]["status"] == "Closed"
    assert "Individual" in got["AGM-DPO27"]["eligibility"]


def test_form_state_from_a_full_page_and_from_a_partial_answer():
    assert ny.form_state(read("search.html")) == ("FIXTURE-SID", "1")
    assert ny.form_state(read("return.xml")) == ("FIXTURE-SID", "1")
    assert ny.form_state(read("abstract_0.html")) == ("FIXTURE-SID", "1")
    with pytest.raises(RuntimeError, match="form state"):
        ny.form_state("<html><body>Session expired</body></html>")


def test_fixtures_carry_no_scripts_or_live_session_ids_or_contacts():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text.lower() and "FIXTURE-SID" in text
        assert "NY_GG_ABSTRT_VW_OPRID' >Contact Name<" in text or "abstract" not in path.name


def test_the_search_form_is_recognised():
    assert ny.has_search_form(read("search.html")) and ny.has_search_form(read("return.xml"))
    assert not ny.has_search_form(read("abstract_0.html"))


# ---------- the abstract ----------

def test_abstract_fields_and_the_announcement_link():
    a = ny.parse_abstract(read("abstract_0.html"))
    assert (a["event_id"], a["agency"], a["name"]) == ("AFTYP3", "AGRICULTURE & MARKETS", "2027 TYCLF")
    assert a["profile"] == "2027 Transportation for Youth to County and Local Fairs"
    assert a["announcement_url"] == "https://agriculture.ny.gov/funding-opportunities"
    assert (a["due"], a["total_funding"], a["contract_length"]) == ("December 1, 2026 / 04:00 PM", "$475,000.000", "0 Month(s)")
    assert a["questions_due"] == "Wednesday, November 04, 2026" and a["anticipated_award_date"] == ""
    assert a["eligibility"] == "Governmental Entity, Not-For-Profit, Tribal Organization"
    assert a["service_areas"] == "Agricultural Supports, Education Supports, Family Supports, Public Transportation Services"
    assert "contact" not in " ".join(a) and not any("@" in v for v in a.values())


def test_an_abstract_without_an_announcement_link_does_not_take_the_mailto():
    a = ny.parse_abstract(read("abstract_1.html").replace("Announcement Link", "Something Else"))
    assert a["announcement_url"] == ""


# ---------- dates and status ----------

@pytest.mark.parametrize("value, expected", [
    ("10/02/26 10:10AM", date(2026, 10, 2)), ("12/01/2026 4:00PM EST", date(2026, 12, 1)),
    ("12/01/2026\xa0 4:00PM EST", date(2026, 12, 1)), ("", None), ("TBD", None),
])
def test_parse_grid_date(value, expected):
    assert ny.parse_grid_date(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("December 1, 2026 / 04:00 PM", date(2026, 12, 1)), ("Wednesday, November 04, 2026", date(2026, 11, 4)),
    ("10/14/2026", date(2026, 10, 14)), ("", None), ("See RFP", None),
])
def test_parse_abstract_date(value, expected):
    assert ny.parse_abstract_date(value) == expected


@pytest.mark.parametrize("label, status", [
    ("Available", "open"), ("Advertised Only - Not in SFS", "open"), ("Anticipated", "forecasted"),
    ("Closed", "closed"), ("Cancelled", "unknown"), ("", "unknown"),
])
def test_status_is_the_grid_label(label, status):
    assert ny.status_for(label) == status


def test_dates_come_from_the_grid():
    p = normalize(0)
    assert (p.status, p.opens_at, p.closes_at, p.closes_at_text) == ("open", date(2026, 10, 8), date(2026, 12, 1), None)


def test_a_date_cell_that_is_not_a_date_goes_to_the_cycle_text():
    row = {**rows()[0], "due": "Rolling"}
    assert ny.closes_text_for(row) == "Due date: Rolling"
    assert ny.closes_text_for(rows()[0]) is None


# ---------- applicants and categories ----------

def test_the_labels_tag_by_table_and_governmental_entity_alone_tags_nothing():
    assert {(t.value, t.source_code) for t in ny.applicant_tags("For Profit, Governmental Entity, Individual, Not-For-Profit")} == {
        ("business", "For Profit"), ("individual", "Individual"), ("nonprofit", "Not-For-Profit")}
    assert ny.applicant_tags("Governmental Entity") == []


def test_a_governmental_entity_row_reads_its_profile_for_governmental_applicants():
    """ERPO: 'Governmental Entity' alone; the profile names municipal, city, town and county (and 'tribal', which is
    not a governmental type and is the portal's label to give)."""
    p = normalize(4)
    assert {t.value for t in p.applicant_types} == {"municipality", "county"}
    assert {t.source_code for t in p.applicant_types if t.value == "municipality"} == {"municipal", "city", "town", "local units of government"}
    assert "tribal" not in {t.source_code for t in p.applicant_types}


def test_a_profile_that_is_only_a_title_tags_nothing():
    """AFTYP3: three labels, and a profile that is the round's name ("... to County and Local Fairs"): a name is
    not an applicant statement, so the county fair does not tag a county."""
    assert {(t.value, t.source_code) for t in normalize(0).applicant_types} == {
        ("nonprofit", "Not-For-Profit"), ("tribe", "Tribal Organization")}
    assert ny.profile_tags("Municipal Waste Reduction and Recycling Program 2024") == []
    assert ny.profile_tags("Municipalities may apply.") == [ny.ApplicantTag(value="municipality", source_code="municipalities")]


def test_a_row_without_governmental_entity_never_reads_its_profile():
    p = normalize(3)      # Not-For-Profit alone; the profile talks of communities and families
    assert [(t.value, t.source_code) for t in p.applicant_types] == [("nonprofit", "Not-For-Profit")]
    row = {**rows()[3], "eligibility": "Governmental Entity, Not-For-Profit"}
    abstract = {"profile": "Counties and cities may apply."}
    assert {t.value for t in ny.applicant_tags_for(row, abstract)} == {"nonprofit", "county", "municipality"}
    assert {t.value for t in ny.applicant_tags_for(row, None)} == {"nonprofit"}


def test_profile_tags_drop_negated_sentences_and_beneficiaries():
    assert ny.profile_tags("Counties are not eligible. Towns and villages may apply to serve residents.") == [
        ny.ApplicantTag(value="municipality", source_code="towns")]
    assert ny.profile_tags("Services for low-income individuals and households.") == []
    assert ny.profile_tags("") == []


def test_service_areas_map_by_table_and_keep_the_label():
    assert [(c.value, c.source_code) for c in normalize(0).categories] == [
        ("other", "Agricultural Supports"), ("other", "Education Supports"), ("other", "Family Supports"),
        ("transportation", "Public Transportation Services")]
    assert {c.value for c in normalize(4).categories} == {"public_safety"}
    assert [c.value for c in ny.category_tags("Health Services, Housing and Shelter Services, Workforce Development")] == ["health", "housing", "workforce"]


# ---------- mapping ----------

def test_key_and_fields():
    p = normalize(3)
    assert p.source_id == RFA1278 and p.external_number == "RFA 1278"
    assert (p.level, p.jurisdiction, p.administering_agency, p.agency_code) == ("state", "NY", "Off of Children & Family Serv", "CFS01")
    assert p.name == "RFA 1278 Child Care Support Centers (Reissue)"
    assert (p.funding_type, p.funding_source, p.amount_min, p.amount_max, p.match_required, p.rolling) == ("grant", "direct", None, None, None, None)
    assert p.status == "open" and p.eligibility_structured["portal_status"] == "Advertised Only - Not in SFS"
    assert p.summary.startswith("The New York State (NYS) Office of Children and Family Services")
    assert p.eligibility_text == "Not-For-Profit" and p.alns == []


def test_structured_fields_only_when_the_source_has_a_value():
    assert normalize(0).eligibility_structured == {
        "portal_status": "Available", "posted_at": "2026-10-02", "total_funding": "$475,000.000",
        "contract_length": "0 Month(s)", "questions_due": "2026-11-04"}
    assert normalize(3).eligibility_structured["anticipated_award_date"] == "2027-03-01"


def test_source_url_is_the_announcement_link_or_the_portal():
    assert normalize(0).source_url == "https://agriculture.ny.gov/funding-opportunities"
    assert ny.source_url_for(None) == ny.PORTAL_URL
    assert ny.source_url_for({"announcement_url": "https://https://cdd.ny.gov/x"}) == ny.PORTAL_URL
    assert ny.source_url_for({"announcement_url": "agriculture.ny.gov/funding"}) == ny.PORTAL_URL


def test_funding_type_from_the_title_keyword_else_grant():
    assert normalize(1).funding_type == "grant"      # "... Implementation Grants"
    assert normalize(0).funding_type == "grant"      # "2027 TYCLF": the portal's word
    row = {**rows()[0], "name": "Clean Water Revolving Loan Fund"}
    assert ny.normalize(RawRecord(source_connector=ny.CONNECTOR, source_id="x", payload={"grid": "open", "row": row, "abstract": None})).funding_type == "loan"


def test_a_closed_row_normalizes_from_the_grid_alone():
    row = {r["event_id"]: r for r in ny.parse_rows(read("closed.html"))}["AGM-AFTYP1"]
    p = ny.normalize(RawRecord(source_connector=ny.CONNECTOR, source_id=ny.row_key(row), payload={"grid": "closed", "row": row, "abstract": None}))
    assert (p.source_id, p.status, p.closes_at) == ("AGM01-AGM-AFTYP1", "closed", date(2025, 2, 25))
    assert p.administering_agency == "AGRICULTURE & MARKETS"       # the table
    assert p.summary is None and p.categories == [] and p.source_url == ny.PORTAL_URL      # no abstract: no profile tags
    assert p.eligibility_structured == {"portal_status": "Closed", "posted_at": "2024-11-20"}
    assert {t.value for t in p.applicant_types} == {"nonprofit", "tribe"}


def test_a_closed_row_takes_the_agency_name_read_this_run_before_the_table():
    row = {**rows()[0], "agency_code": "XYZ01"}
    raw = RawRecord(source_connector=ny.CONNECTOR, source_id="x", payload={"grid": "closed", "row": row, "abstract": None, "agency": "Some Office"})
    assert ny.normalize(raw).administering_agency == "Some Office"
    raw.payload.pop("agency")
    assert ny.normalize(raw).administering_agency is None


def test_the_contact_is_not_in_the_payload():
    text = str(record(0).payload)
    assert "Contact Name" not in text and "@" not in text


def test_every_saved_row_normalizes():
    for n in rows():
        p = normalize(n)
        assert p.name and p.status == "open" and p.record_hash


# ---------- fetch ----------

class _Portal:
    """A stand-in for `_get` and `_post`: answers the saved pages by action and checks the state is tracked."""

    def __init__(self, broken=(), closed_rows=True, swap_abstract=False):
        self.broken, self.calls, self.closed_rows, self.swap_abstract = set(broken), [], closed_rows, swap_abstract

    def get(self, client):
        self.calls.append("GET")
        if "GET" in self.broken:
            raise httpx.ConnectError("down")
        return read("search.html")

    def post(self, client, page, action, **fields):
        ny.form_state(page)           # every post is built from a real answer
        self.calls.append(action)
        if action in self.broken:
            raise httpx.ConnectError("down")
        if action.startswith("AUC_NAME_LNK$"):
            n = int(action.split("$")[1])
            return read(ABSTRACT_OF[1 if self.swap_abstract and n == 0 else n])
        if action == ny.RETURN_ACTION:
            return read("return.xml")
        assert action == ny.SEARCH_ACTION and fields == {ny.STATUS_FIELD: ny.CLOSED}
        return read("closed.html") if self.closed_rows else read("search.html").replace("AUC_ID_COL$span$", "X$")


@pytest.fixture
def portal(monkeypatch):
    monkeypatch.setattr(ny.time, "sleep", lambda s: None)
    stub = _Portal()
    monkeypatch.setattr(ny, "_get", stub.get)
    monkeypatch.setattr(ny, "_post", stub.post)
    monkeypatch.setattr(ny, "_client", lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    return stub


def test_fetch_reads_every_open_abstract_then_the_closed_grid(portal):
    records = ny.fetch()
    assert [r.source_id for r in records] == [AFTYP3, FPIG20, RFA1278, ERPO, "AGM01-AGM-AFTYP1", "AGM01-AGM-DPO27", "DOH01-DCCTPR2025"]
    assert portal.calls == ["GET", "AUC_NAME_LNK$0", ny.RETURN_ACTION, "AUC_NAME_LNK$1", ny.RETURN_ACTION,
                            "AUC_NAME_LNK$3", ny.RETURN_ACTION, "AUC_NAME_LNK$4", ny.RETURN_ACTION, ny.SEARCH_ACTION]
    open_, closed = records[0], records[4]
    assert open_.payload["grid"] == "open" and open_.payload["abstract"]["event_id"] == "AFTYP3"
    assert closed.payload["grid"] == "closed" and closed.payload["abstract"] is None
    assert closed.payload["agency"] == "AGRICULTURE & MARKETS"               # from the abstracts read this run
    assert records[-1].payload["agency"] is None                           # DOH01 was on no open abstract


def test_fetch_with_a_limit_reads_that_many_abstracts_and_skips_the_closed_grid(portal):
    records = ny.fetch(limit=2)
    assert [r.source_id for r in records] == [AFTYP3, FPIG20]
    assert ny.SEARCH_ACTION not in portal.calls


def test_an_abstract_for_the_wrong_row_aborts(monkeypatch, portal):
    stub = _Portal(swap_abstract=True)
    monkeypatch.setattr(ny, "_post", stub.post)
    with pytest.raises(RuntimeError, match="answered for row 0"):
        ny.fetch()


def test_a_request_that_fails_aborts(monkeypatch, portal):
    for broken in ("GET", "AUC_NAME_LNK$3", ny.RETURN_ACTION, ny.SEARCH_ACTION):
        stub = _Portal(broken={broken})
        monkeypatch.setattr(ny, "_get", stub.get)
        monkeypatch.setattr(ny, "_post", stub.post)
        with pytest.raises(httpx.ConnectError):
            ny.fetch()


def test_a_closed_search_with_no_rows_aborts(monkeypatch, portal):
    stub = _Portal(closed_rows=False)
    monkeypatch.setattr(ny, "_post", stub.post)
    with pytest.raises(RuntimeError, match="closed search answered no rows"):
        ny.fetch()


def test_a_search_page_without_the_form_aborts(monkeypatch, portal):
    monkeypatch.setattr(ny, "_get", lambda client: "<html><body>Scheduled maintenance</body></html>")
    with pytest.raises(RuntimeError, match="without its search form"):
        ny.fetch()


def test_resolve_missing_is_unknown_without_a_request():
    assert ny.resolve_missing(AFTYP3) == {"status": "unknown"}


# ---------- the HTTP helpers, through a real client ----------

def test_request_retries_a_dropped_connection_but_not_an_http_error(monkeypatch):
    monkeypatch.setattr(ny.time, "sleep", lambda s: None)
    calls = []

    def flaky(request):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("reset")
        return httpx.Response(200, text="ok")

    assert ny._request(httpx.Client(transport=httpx.MockTransport(flaky)), "GET", "https://x.test/") == "ok" and len(calls) == 3
    with pytest.raises(httpx.HTTPStatusError):
        ny._request(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))), "GET", "https://x.test/")


def test_post_sends_the_form_state_of_the_previous_answer(monkeypatch):
    monkeypatch.setattr(ny.time, "sleep", lambda s: None)
    seen = {}

    def handler(request):
        seen.update(dict(httpx.QueryParams(request.content.decode())))
        return httpx.Response(200, text="ok")

    page = read("return.xml").replace("ICStateNum.value=1", "ICStateNum.value=7").replace("id='ICStateNum' value='1'", "id='ICStateNum' value='7'")
    ny._post(httpx.Client(transport=httpx.MockTransport(handler)), page, "AUC_NAME_LNK$3")
    assert (seen["ICSID"], seen["ICStateNum"], seen["ICAction"], seen["ICType"]) == ("FIXTURE-SID", "7", "AUC_NAME_LNK$3", "Panel")
