"""California Grants Portal connector tests. Mapping tests run against the saved CSV sample (never the network); the
value parsers are tested directly."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from connectors import ca_grants as ca
from pipeline.models import RawRecord

FIXTURE = Path(__file__).parent / "fixtures" / "ca_grants" / "grants_sample.csv"
TODAY = date(2026, 10, 27)


def rows() -> dict[str, dict]:
    return {r["PortalID"]: r for r in ca.parse_csv(FIXTURE.read_bytes().decode("utf-8-sig"))}


def normalize(source_id: str):
    return ca.normalize(RawRecord(source_connector=ca.CONNECTOR, source_id=source_id, payload=rows()[source_id]), TODAY)


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


class _Client:
    def __init__(self, content: bytes):
        self.content, self.calls = content, []

    def get(self, url):
        self.calls.append(url)
        return _Response(self.content)


@pytest.fixture(autouse=True)
def _no_cached_file(monkeypatch):
    monkeypatch.setattr(ca, "_last_rows", None)


# ---------- plumbing ----------

def test_fixture_carries_the_byte_order_mark_and_parse_csv_drops_it():
    assert FIXTURE.read_bytes().startswith(b"\xef\xbb\xbf")
    assert ca.parse_csv("﻿PortalID,Title\r\n1,A\r\n,B\r\n") == [{"PortalID": "1", "Title": "A"}]


def test_fetch_rows_reads_the_download_path_and_remembers_the_file():
    client = _Client(FIXTURE.read_bytes())
    got = ca.fetch_rows(client)
    assert client.calls == [ca.CSV_URL]
    assert "/api/" not in ca.CSV_URL and ca.RESOURCE_ID in ca.CSV_URL
    assert len(got) == len(rows()) == 10
    assert set(ca._last_rows) == set(rows())


def test_resolve_missing_gone_is_unknown_present_is_its_label(monkeypatch):
    ca.fetch_rows(_Client(FIXTURE.read_bytes()))
    assert ca.resolve_missing("999999") == {"status": "unknown"}
    assert ca.resolve_missing("150669") == {"status": "closed", "closes_at": date(2026, 4, 3)}


def test_resolve_missing_unreadable_is_none(monkeypatch):
    def boom(client):
        raise OSError("down")
    monkeypatch.setattr(ca, "fetch_rows", boom)
    assert ca.resolve_missing("150669") is None


def test_constants_and_source_url():
    p = normalize("192288")
    assert p.source_url == rows()["192288"]["GrantURL"]
    assert p.level == "state" and p.jurisdiction == "CA" and p.agency_code is None and p.alns == []
    assert p.administering_agency == rows()["192288"]["AgencyDept"]


def test_external_number_is_grant_id_when_present():
    assert normalize("192621").external_number == "Victim Compensation Board"
    assert normalize("192288").external_number is None


# ---------- status and dates ----------

@pytest.mark.parametrize("source_id, status", [
    ("192288", "open"), ("192864", "forecasted"), ("150669", "closed"), ("171528", "closed"),
])
def test_status_is_the_portal_label(source_id, status):
    assert normalize(source_id).status == status


def test_status_unknown_label():
    assert ca.status_for("paused") == "unknown" and ca.status_for("") == "unknown"


def test_dates_are_the_date_part():
    p = normalize("150669")
    assert p.opens_at == date(2025, 9, 30) and p.closes_at == date(2026, 4, 3)
    assert p.closes_at_text is None and p.rolling is None


def test_ongoing_deadline_is_rolling_text():
    p = normalize("190509")
    assert p.closes_at is None and p.closes_at_text == "Ongoing" and p.rolling is True


def test_forecasted_text_open_date_kept_as_text():
    p = normalize("192864")
    assert p.opens_at is None and p.closes_at_text == "Opens: Fall 2026"


# ---------- money ----------

@pytest.mark.parametrize("text, expected", [
    ("Between $250,000.00 and $4,000,000.00", (250000, 4000000)),
    ("$1,500,000.00", (1500000, 1500000)),
    ("Dependant on number of submissions received, application process, etc.", (None, None)),
    ("", (None, None)),
])
def test_amount_fields(text, expected):
    assert ca.amount_fields(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Not Required", (False, None)), ("25%", (True, 25.0)), ("", (None, None)), ("See guidelines", (None, None)),
])
def test_match_fields(text, expected):
    assert ca.match_fields(text) == expected


def test_money_on_records():
    p = normalize("191505")
    assert (p.amount_min, p.amount_max, p.match_required, p.match_pct) == (250000, 4000000, True, 100.0)


@pytest.mark.parametrize("source_id, funding_type, funding_source", [
    ("192288", "grant", "pass_through"),   # Federal
    ("171528", "loan", "direct"),          # State
    ("1797", "grant", "pass_through"),     # Grant; Loan, Federal and State: first token
])
def test_funding_type_and_source(source_id, funding_type, funding_source):
    p = normalize(source_id)
    assert (p.funding_type, p.funding_source) == (funding_type, funding_source)


# ---------- applicants and categories ----------

def test_public_agency_alone_tags_nothing():
    assert rows()["152751"]["ApplicantType"] == "Public Agency"
    assert normalize("152751").applicant_types == []


def test_notes_name_cities_and_counties():
    assert rows()["192288"]["ApplicantType"] == "Public Agency"
    assert normalize("192288").applicant_pairs() == [("county", "counties"), ("municipality", "cities")]


def test_portal_types_then_notes_without_duplicates():
    pairs = normalize("191505").applicant_pairs()
    values = [v for v, _ in pairs]
    assert len(values) == len(set(values))
    assert ("nonprofit", "Nonprofit") in pairs and ("tribe", "Tribal Government") in pairs
    assert ("municipality", "local government") in pairs


def test_categories_map_and_keep_the_portal_word():
    assert normalize("190509").category_pairs() == [
        ("other", "Disadvantaged Communities"), ("parks", "Parks & Recreation"), ("water", "Environment & Water"),
    ]
    # a label that names two topics carries both, as it does for pa.gov's and Illinois's economic development
    assert normalize("150669").category_pairs() == [
        ("housing", "Housing, Community and Economic Development"),
        ("infrastructure", "Housing, Community and Economic Development"),
    ]


def test_eligibility_text_and_structured():
    p = normalize("192288")
    assert p.eligibility_text.startswith("Applicant type: Public Agency\nEligibility: ")
    assert p.eligibility_structured["funding_method"] == rows()["192288"]["FundingMethod"]
    assert p.eligibility_structured["loi_required"] == (rows()["192288"]["LOI"] == "Yes")


# ---------- change detection ----------

def test_last_updated_and_change_notes_do_not_move_the_hash():
    row = dict(rows()["192288"])
    before = ca.normalize(RawRecord(source_connector=ca.CONNECTOR, source_id="192288", payload=row), TODAY).record_hash
    row.update(LastUpdated="2030-01-01 00:00:00", ChangeNotes="Made minor revisions to spacing.", ContactInfo="x")
    after = ca.normalize(RawRecord(source_connector=ca.CONNECTOR, source_id="192288", payload=row), TODAY).record_hash
    assert before == after


def test_every_fixture_row_normalizes():
    for source_id in rows():
        p = normalize(source_id)
        assert p.name and p.source_url.startswith("http")
