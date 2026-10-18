"""pa.gov grants connector tests. Mapping tests run against saved fixtures (never the network); the small
parsers and the status rules are tested directly."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import pa_grants as pa
from pipeline.models import RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "pa_grants"
TODAY = date(2026, 10, 17)


def load(source_id: str) -> RawRecord:
    payload = json.loads((FIXTURES / (source_id.replace("/", "_") + ".json")).read_text())
    return RawRecord(source_connector=pa.CONNECTOR, source_id=source_id, payload=payload)


def normalize(source_id: str):
    return pa.normalize(load(source_id), TODAY)


# ---------- plumbing ----------

def test_search_key_is_read_from_the_page_or_fails_loudly():
    assert pa.read_search_key('<div data-search-hub="All Grants" data-api-key="xx3f-abc"></div>') == "xx3f-abc"
    with pytest.raises(RuntimeError):
        pa.read_search_key("<html>no key here</html>")


def test_search_body_and_source_id_rules():
    body = pa.search_body(200, 100)
    assert body["searchHub"] == "All Grants" and body["firstResult"] == 200 and body["numberOfResults"] == 100
    assert pa.source_id_for("https://www.pa.gov/en/grants/search/grant-details/pema/10") == "pema/10"
    assert pa.source_id_for("https://www.pa.gov/grants/search/grant-details/PennDOT/025") == "penndot/25"
    assert pa.source_id_for("https://www.pa.gov/grants/search") is None
    assert pa.detail_url("dced/51") == "https://www.pa.gov/grants/search/grant-details/dced/51"


class _Response:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _Client:
    """Serves the saved Coveo page whatever is asked; totalCount is clamped so the walk stops after one page."""

    def __init__(self, page):
        self.page = page
        self.calls = []

    def post(self, url, json=None, headers=None):
        self.calls.append((url, json["firstResult"], headers["Authorization"]))
        return _Response(self.page)


def test_iter_hits_walks_one_page_keeps_copapwp_fields_and_dedupes():
    page = json.loads((FIXTURES / "search_page1.json").read_text())
    page = page | {"totalCount": len(page["results"])}
    client = _Client(page)
    hits = list(pa.iter_hits(client, "key-1"))
    assert len(hits) == len({pa.source_id_for(r["raw"]["copapwpurl"]) for r in page["results"]})
    assert all(k.startswith("copapwp") for h in hits for k in h)
    assert client.calls == [(pa.COVEO_URL, 0, "Bearer key-1")]
    assert list(pa.iter_hits(_Client(page), "k", limit=2)) == hits[:2]


def test_parse_detail_decodes_the_escaped_attribute():
    page = ('<div id="pageApiData" data-page-api-data="{&quot;slug&quot;:&quot;pema10&quot;,'
            '&quot;title&quot;:&quot;Hazard Mitigation &amp; Resilience&quot;,&quot;status&quot;:&quot;Closed&quot;}"></div>')
    assert pa.parse_detail(page) == {"slug": "pema10", "title": "Hazard Mitigation & Resilience", "status": "Closed"}
    assert pa.parse_detail("<div></div>") is None
    assert pa.parse_detail('<div data-page-api-data="not json"></div>') is None


# ---------- rules ----------

@pytest.mark.parametrize("rec, expected", [
    ({"status": "Accepting applications", "openDate": "2026-09-14T12:00:00-00:00", "closeDate": "2026-10-30T12:00:00-00:00"}, "open"),
    ({"status": "Accepting applications", "closeDate": "2026-01-01T12:00:00-00:00"}, "open"),           # past deadline: the views drop it
    ({"status": "Closed", "openDate": "2026-11-02T12:00:00-00:00", "closeDate": "2026-12-18T12:00:00-00:00"}, "forecasted"),
    ({"status": "Closed", "openDate": "2026-12-01T12:00:00-00:00"}, "forecasted"),                        # no close date
    ({"status": "Closed", "openDate": "2028-11-27T12:00:00-00:00", "closeDate": "2018-12-27T12:00:00-00:00"}, "closed"),  # inconsistent
    ({"status": "Closed", "openDate": "2022-01-01T12:00:00-00:00", "closeDate": "2022-03-25T12:00:00-00:00"}, "closed"),
    ({"status": "Closed", "openDate": "1641038400000", "closeDate": "1648209600000"}, "closed"),            # epoch ms strings
    ({"status": "Paused"}, "unknown"),
    ({}, "unknown"),
])
def test_status_rules(rec, expected):
    assert pa.status_fields(rec, TODAY)["status"] == expected


def test_dates_from_iso_and_epoch_millis():
    assert pa.parse_when("2026-09-14T12:00:00-00:00") == date(2026, 9, 14)
    assert pa.parse_when("1648209600000") == date(2022, 3, 25)
    assert pa.parse_when(1648209600000) == date(2022, 3, 25)
    assert pa.parse_when("") is None and pa.parse_when(None) is None


@pytest.mark.parametrize("value, expected", [
    ("Grant ", "grant"), ("Grant; grant agreement", "grant"), (["Grant", " grant agreement"], "grant"),
    ("Loan", "loan"), ("Loan program", "loan"), ("Tax credit", "tax_credit"), ("tax refund", "tax_credit"),
    ("Disaster reimbursement", "other"), ("Fund", "other"), ("Incentitive payment", "other"),
    ("", None), (None, None), ("Prize", None),
])
def test_funding_type_map(value, expected):
    assert pa.funding_type_for(value) == expected


def test_funding_source_is_pass_through_only_when_federal_is_named():
    assert pa.funding_source_for("Federal") == "pass_through"
    assert pa.funding_source_for("Federal and State") == "pass_through"
    assert pa.funding_source_for(["Federal STOP Violence Against Women"]) == "pass_through"
    assert pa.funding_source_for("State") == "direct"
    assert pa.funding_source_for("Commonwealth Financing Authority (CFA)") == "direct"
    assert pa.funding_source_for("") == "direct"


@pytest.mark.parametrize("text, expected", [
    ("", (None, None)), ("N/A ", (None, None)), ("None", (None, None)), ("No", (None, None)),
    ("No match required", (False, None)), ("Match is not required.", (False, None)),
    ("30% of the amount requested ", (True, 30.0)),
    ("75% federal share\n25% local share", (True, None)),
    ("Matched by local funding in an amount not less than 30% of the non-federal share", (True, 30.0)),
    ("Local match required; see guidelines.", (True, None)),
])
def test_match_fields(text, expected):
    assert pa.match_fields(text) == expected


def test_rolling_comes_from_the_cycle_wording_not_the_date():
    assert pa.rolling_for("Reoccurring") is True and pa.rolling_for("Re-occurring") is True
    assert pa.rolling_for("Continuous") is True and pa.rolling_for("Revolving Loan Fund") is True
    assert pa.rolling_for("rolling deadline") is True
    assert pa.rolling_for("Annual") is None and pa.rolling_for("") is None and pa.rolling_for(None) is None


def test_applicant_tags_from_categories_then_free_text():
    tags = pa.applicant_tags({
        "applicantCategory": "Municipality; Public Agency; Other Legal Entity; Business",
        "applicantType": "Cities; Townships; Counties; Special district governments; State agencies. ",
    })
    pairs = sorted((t.value, t.source_code) for t in tags)
    assert ("municipality", "Municipality") in pairs and ("business", "Business") in pairs
    assert ("county", "counties") in pairs and ("state", "state agencies") in pairs
    assert not any(c in ("Public Agency", "Other Legal Entity") for _, c in pairs)
    assert len({v for v, _ in pairs}) == len(pairs)        # a type is tagged once
    assert pa.applicant_tags({"applicantCategory": ["Nonprofit", " School", " Individual",
                                                    " Native American Tribal Organization or Government"]}) == [
        t for t in pa.applicant_tags({"applicantCategory": "Nonprofit; School; Individual; Native American Tribal Organization or Government"})
    ]
    assert {t.value for t in pa.applicant_tags({"applicantCategory": "Nonprofit; School; Individual; Native American Tribal Organization or Government"})} == {
        "nonprofit", "school", "individual", "tribe"}
    assert pa.applicant_tags({"applicantCategory": "Public Agency", "populationServedType": "low-income residents"}) == []


def test_category_map_keeps_the_text_as_source_code():
    assert pa.category_tags({"category": "Community & economic development"})[0].value == "infrastructure"
    assert pa.category_tags({"category": "Environment & water"})[0].value == "water"
    assert [(t.value, t.source_code) for t in pa.category_tags({"category": ["Agriculture"]})] == [("other", "Agriculture")]
    assert pa.category_tags({"category": "Transportation; Energy"}) and len(pa.category_tags({"category": "Transportation; Energy"})) == 2
    assert pa.category_tags({}) == []


def test_record_falls_back_to_the_hit_when_the_detail_is_missing():
    rec = pa.record({"hit": {"copapwppagetitle": "Coastal Zone Management", "copapwpapplicationstatus": "Accepting applications",
                             "copapwpopendate": "1756612800000", "copapwpfundingtype": ["Grant"],
                             "copapwpfundingagency": ["Environment & water"]}, "detail": {}})
    assert rec["title"] == "Coastal Zone Management" and rec["status"] == "Accepting applications"
    assert rec["fundingType"] == ["Grant"] and rec["issuingAgency"] == ["Environment & water"]
    rec = pa.record({"hit": {"copapwppagetitle": "Hit title"}, "detail": {"title": "Detail title"}})
    assert rec["title"] == "Detail title"


# ---------- fixtures ----------

def test_normalize_open_grant_with_award_range_and_single_percent_match():
    p = normalize("penndot/25")
    assert p.name == "Multimodal Transportation Fund (MTF) Program" and p.status == "open"
    assert p.opens_at == date(2026, 9, 14) and p.closes_at == date(2026, 10, 30)
    assert p.level == "state" and p.jurisdiction == "PA" and p.source_url.endswith("/grant-details/penndot/25")
    assert p.administering_agency == "Transportation" and p.agency_code == "PA-PENNDOT"
    assert p.funding_type == "grant" and p.funding_source == "direct" and p.alns == []
    assert p.amount_min is None and p.amount_max == 3000000
    assert p.match_required is True and p.match_pct == 30.0
    assert p.closes_at_text == "Annual" and p.rolling is None
    assert ("municipality", "Municipality") in p.applicant_pairs() and ("business", "businesses") in p.applicant_pairs()
    assert p.category_pairs() == [("transportation", "Transportation")]
    assert p.eligibility_text.startswith("Eligibility: Multimodal Transportation Fund Success Manual")
    assert "Applicant type: Municipalities; Councils of governments" in p.eligibility_text
    assert "Population served:" in p.eligibility_text
    assert p.summary and p.external_number is None and p.eligibility_structured is None


def test_normalize_closed_federal_pass_through_with_two_percentages():
    p = normalize("pema/10")
    assert p.name == "Hazard Mitigation Grant Program (HMGP)" and p.status == "closed"
    assert p.opens_at == date(2022, 1, 1) and p.closes_at == date(2022, 3, 25)
    assert p.agency_code == "PA-PEMA" and p.administering_agency == "Emergency Management Agency"
    assert p.funding_source == "pass_through" and p.alns == [] and p.funding_type == "grant"
    assert p.match_required is True and p.match_pct is None
    assert p.closes_at_text == "Upon Disaster Declaration" and p.rolling is None
    assert {v for v, _ in p.applicant_pairs()} >= {"municipality", "county", "state"}
    assert p.category_pairs() == [("infrastructure", "Community & economic development")]
    assert "Eligibility: https://www.fema.gov/" in p.eligibility_text


def test_normalize_the_duplicate_round_under_another_agency():
    p = normalize("dced/51")
    assert p.status == "closed" and p.agency_code == "PA-DCED" and p.funding_source == "direct"
    assert p.amount_min == 100000 and p.amount_max == 3000000
    assert p.match_required is True and p.match_pct == 30.0
    assert p.slug != normalize("penndot/25").slug


def test_normalize_recurring_program_keeps_the_placeholder_date_and_is_rolling():
    p = normalize("dced/2")
    assert p.name.startswith("Act 47") and p.status == "open"
    assert p.closes_at == date(2035, 12, 31) and p.rolling is True and p.closes_at_text == "Reoccurring"


def test_normalize_closed_with_a_future_open_date_is_forecasted():
    p = normalize("dmva/1")
    assert p.status == "forecasted" and p.opens_at == date(2026, 11, 2) and p.closes_at == date(2026, 12, 18)


def test_normalize_inconsistent_dates_stay_closed():
    p = normalize("pema/14")
    assert p.status == "closed" and p.opens_at == date(2028, 11, 27) and p.closes_at == date(2018, 12, 27)
    assert p.funding_type == "other"


def test_normalize_tax_credit_and_federal_loan():
    tc = normalize("dced/57")
    assert tc.funding_type == "tax_credit" and tc.status == "open" and tc.closes_at == date(2035, 6, 30)
    loan = normalize("dep/31")
    assert loan.funding_type == "loan" and loan.funding_source == "pass_through" and loan.rolling is True
    assert loan.closes_at == date(2999, 7, 1) and loan.closes_at_text == "Revolving Loan Fund"


def test_normalize_open_with_no_close_date():
    p = normalize("pccd/63")
    assert p.status == "open" and p.closes_at is None and p.opens_at == date(2026, 7, 22)
    assert p.funding_source == "pass_through"


def test_normalize_invents_nothing_from_a_bare_record():
    raw = RawRecord(source_connector=pa.CONNECTOR, source_id="x/1",
                    payload={"hit": {"copapwpurl": "https://www.pa.gov/en/grants/search/grant-details/x/1"},
                             "detail": {"title": "Bare", "status": "Weird"}})
    p = pa.normalize(raw, TODAY)
    assert p.status == "unknown" and p.opens_at is None and p.closes_at is None and p.closes_at_text is None
    assert p.funding_type is None and p.funding_source == "direct" and p.match_required is None and p.rolling is None
    assert p.applicant_types == [] and p.categories == [] and p.alns == []
    assert p.summary is None and p.eligibility_text is None and p.agency_code is None and p.administering_agency is None


def test_hash_is_stable_across_loads_and_ignores_last_modified():
    a, b = normalize("penndot/25"), normalize("penndot/25")
    assert a.record_hash == b.record_hash
    raw = load("penndot/25")
    raw.payload["detail"]["last_modified"] = "2030-01-01T00:00:00Z"
    assert pa.normalize(raw, TODAY).record_hash == a.record_hash
