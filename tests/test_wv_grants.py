"""grants.wv.gov connector tests. Mapping tests run against the saved API response (never the network); the
status rules and the forecast-text reader are tested directly."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import wv_grants as wv
from pipeline.models import RawRecord

FIXTURE = Path(__file__).parent / "fixtures" / "wv_grants" / "availablegrants_sample.json"
TODAY = date(2026, 10, 18)


def items() -> dict[str, dict]:
    data = json.loads(FIXTURE.read_text())
    return {str(i["Id"]): i for i in data["properties"] if isinstance(i, dict)}


def normalize(source_id: str):
    return wv.normalize(RawRecord(source_connector=wv.CONNECTOR, source_id=source_id, payload=items()[source_id]), TODAY)


class _Response:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _Client:
    def __init__(self, data):
        self.data, self.calls = data, []

    def post(self, url, data=None):
        self.calls.append((url, data))
        return _Response(self.data)


# ---------- plumbing ----------

def test_fetch_list_posts_the_page_form_and_drops_the_padding():
    client = _Client(json.loads(FIXTURE.read_text()))
    got = wv.fetch_list(client)
    assert client.calls == [(wv.API_URL, {"siteurl": "grants.wv.gov", "listname": "AvailableGrants", "query": "", "maxItems": "1000"})]
    assert all(isinstance(i, dict) and i["Id"] for i in got) and len(got) == len(items())


def test_source_url_and_constants():
    p = normalize("78")
    assert p.source_url == "https://grants.wv.gov/grants/Pages/grantdetails.aspx?grantid=78"
    assert p.level == "state" and p.jurisdiction == "WV" and p.agency_code is None and p.alns == []


# ---------- rules ----------

@pytest.mark.parametrize("text, expected", [
    ("May 2023", date(2023, 5, 1)), ("Spring 2023", date(2023, 3, 1)), ("Summer 2023", date(2023, 6, 1)),
    ("Fall 2023", date(2023, 9, 1)), ("Tentative Fall 2022", date(2022, 9, 1)), ("March 18, 2024", date(2024, 3, 18)),
    ("October 1, 2024", date(2024, 10, 1)), ("Forecasted Spring 2027", date(2027, 3, 1)),
    ("Annual deadline of April 1st", None), ("Ongoing", None), ("rolling deadline", None),
    ("No further solicitations for applications expected due to grant timelines.", None), ("", None),
])
def test_forecast_date(text, expected):
    assert wv.forecast_date(text) == expected


@pytest.mark.parametrize("item, expected", [
    ({"PostedDate": "2026-01-01T05:00:00Z", "DueDate1": "2026-12-31T05:00:00Z"}, "open"),
    ({"PostedDate": "2027-01-01T05:00:00Z", "DueDate1": "2027-06-01T04:00:00Z", "Forecasted": "Ongoing"}, "forecasted"),
    ({"PostedDate": "2024-02-13T05:00:00Z", "DueDate1": "2024-04-01T04:00:00Z", "Forecasted": "Spring 2027"}, "forecasted"),
    ({"PostedDate": "2024-02-13T05:00:00Z", "DueDate1": "2024-04-01T04:00:00Z", "Forecasted": "Annual deadline of April 1st"}, "closed"),
    ({"PostedDate": "2024-02-13T05:00:00Z", "DueDate1": "2024-04-01T04:00:00Z", "Forecasted": "May 2023"}, "closed"),
    ({"PostedDate": "", "DueDate1": "", "Forecasted": "Spring 2023"}, "unknown"),
    ({"PostedDate": "", "DueDate1": "", "Forecasted": "No further solicitations for applications expected."}, "unknown"),
    ({"PostedDate": "2022-10-14T04:00:00Z", "DueDate1": "2023-02-24T05:00:00Z", "Forecasted": ""}, "closed"),
    ({"PostedDate": "2026-09-15T04:00:00Z", "DueDate1": "", "Forecasted": ""}, "unknown"),
    ({}, "unknown"),
])
def test_status_rules(item, expected):
    assert wv.status_fields(item, TODAY)["status"] == expected


def test_closes_text_prefers_forecast_then_important_dates():
    assert wv.closes_text_for({"Forecasted": "Annual deadline of April 1st", "ImportantDateTitle1": "x", "ImportantDate1": "2026-01-01T05:00:00Z"}) == "Annual deadline of April 1st"
    assert wv.closes_text_for({"Forecasted": "", "ImportantDateTitle1": "Intent to Apply due", "ImportantDate1": "2026-03-01T05:00:00Z",
                               "ImportantDateTitle2": "Deadline to apply", "ImportantDate2": "2026-04-30T04:00:00Z"}) == "Intent to Apply due: 2026-03-01; Deadline to apply: 2026-04-30"
    assert wv.closes_text_for({"Forecasted": "", "ImportantDateTitle1": "", "ImportantDate1": ""}) is None
    assert wv.closes_text_for({"Forecasted": "", "ImportantDateTitle1": "Forecasted Opening Date", "ImportantDate1": ""}) is None


def test_funding_source_only_from_an_explicit_pass_through():
    assert wv.funding_source_for({"TypeOfGrant": "Pass-through"}) == "pass_through"
    assert wv.funding_source_for({"TypeOfGrant": "Formula"}) == "direct"
    assert wv.funding_source_for({"TypeOfGrant": "Entitlement"}) == "direct"
    assert wv.funding_source_for({}) == "direct"


def test_categories_by_division_keyword_keep_the_division_as_source_code():
    assert wv.category_tags("West Virginia Department of Homeland Security, Justice and Community Services")[0].value == "public_safety"
    assert wv.category_tags("West Virginia Water Development Authority")[0].value == "water"
    assert wv.category_tags("WV DHHR, Bureau for Family Assistance")[0].value == "health"
    assert wv.category_tags("West Virginia Department of Economic Development, Community Advancement and Development")[0].value == "infrastructure"
    t = wv.category_tags("Department of Environmental Protection Office of the Advocate")[0]
    assert t.value == "other" and t.source_code.startswith("Department of Environmental Protection")
    assert wv.category_tags("") == []


# ---------- fixtures ----------

def test_normalize_active_item_with_municipal_eligibility():
    p = normalize("78")
    assert p.status == "open" and p.opens_at == date(2026, 1, 1) and p.closes_at == date(2026, 12, 31)
    assert p.administering_agency.startswith("Department of Environmental Protection")
    assert {v for v, _ in p.applicant_pairs()} >= {"municipality"} or {v for v, _ in p.applicant_pairs()} >= {"county"}
    assert p.eligibility_structured == {"type_of_grant": "Non-Competitive"} and p.funding_source == "direct"
    assert p.summary and p.eligibility_text


def test_normalize_future_posted_ongoing_item_is_forecasted_and_rolling():
    p = normalize("76")
    assert p.status == "forecasted" and p.opens_at == date(2027, 1, 1) and p.closes_at == date(2027, 6, 1)
    assert p.rolling is True and p.closes_at_text == "Ongoing"
    assert p.applicant_pairs() == []     # "State governments ... can apply": the shared keyword map knows "state agencies", not this


def test_normalize_past_due_with_cycle_text_is_closed_and_keeps_the_text():
    p = normalize("131")
    assert p.status == "closed" and p.closes_at == date(2024, 4, 1)
    assert p.closes_at_text.lower().startswith("annual deadline of april") and p.rolling is None


def test_normalize_rolling_deadline_past_due():
    p = normalize("141")
    assert p.status == "closed" and p.rolling is True and p.closes_at_text == "rolling deadline"


def test_normalize_items_with_no_dates_are_unknown():
    stale = normalize("95")
    assert stale.status == "unknown" and stale.opens_at is None and stale.closes_at is None and stale.closes_at_text == "Spring 2023"
    done = normalize("142")
    assert done.status == "unknown" and done.closes_at_text.startswith("No further solicitations")


def test_normalize_past_due_municipal_rounds_are_closed():
    for sid in ("201", "94"):
        p = normalize(sid)
        assert p.status == "closed" and p.closes_at and p.closes_at < TODAY
        assert any(v in ("municipality", "county") for v, _ in p.applicant_pairs()), sid


def test_normalize_invents_nothing_from_a_bare_item():
    p = wv.normalize(RawRecord(source_connector=wv.CONNECTOR, source_id="1", payload={"Id": "1", "Title": "Bare"}), TODAY)
    assert p.status == "unknown" and p.opens_at is None and p.closes_at is None and p.closes_at_text is None
    assert p.funding_type is None and p.funding_source == "direct" and p.rolling is None
    assert p.applicant_types == [] and p.categories == [] and p.summary is None and p.eligibility_text is None
    assert p.administering_agency is None and p.eligibility_structured is None


def test_hash_ignores_modified_and_contacts():
    a = normalize("78")
    item = dict(items()["78"])
    item["Modified"] = "2030-01-01T00:00:00Z"
    item["ContactName1"] = "Someone Else"
    b = wv.normalize(RawRecord(source_connector=wv.CONNECTOR, source_id="78", payload=item), TODAY)
    assert a.record_hash == b.record_hash
