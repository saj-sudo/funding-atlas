"""Grants.gov connector tests. Mapping tests run against saved fixtures (never the network);
the parser helpers are tested directly."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from connectors import grants_gov as gg
from pipeline.models import ALL_APPLICANT_TYPES, RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "grants_gov"


def test_search_body_matches_plan():
    body = gg.search_body(200, 100)
    assert body["eligibilities"] == "01|02|99"
    assert body["oppStatuses"] == "forecasted|posted"
    assert body["rows"] == 100 and body["startRecordNum"] == 200
    assert set(body) == {"keyword", "oppNum", "eligibilities", "agencies", "oppStatuses", "aln",
                         "fundingCategories", "fundingInstruments", "rows", "startRecordNum", "sortBy"}


@pytest.mark.parametrize("raw, expected", [
    ("10/15/2026", date(2026, 10, 15)),
    ("2026-10-15T00:00:00", date(2026, 10, 15)),
    ("Oct 15, 2026 12:00:00 AM EDT", date(2026, 10, 15)),
    ("October 15, 2026", date(2026, 10, 15)),
    (1792022400000, date(2026, 10, 15)),
    ("", None), (None, None), ("TBD", None),
])
def test_parse_date(raw, expected):
    assert gg.parse_date(raw) == expected


def test_parse_int_and_bool():
    assert gg.parse_int("1,500,000") == 1500000
    assert gg.parse_int("$0") == 0
    assert gg.parse_int("none") is None
    assert gg.parse_int(None) is None
    assert gg.parse_bool("Yes") is True and gg.parse_bool("No") is False
    assert gg.parse_bool(True) is True and gg.parse_bool(None) is None


def test_strip_html():
    assert gg.strip_html("<p>Hello&nbsp;<b>world</b></p><p>again</p>") == "Hello world again"


def test_normalize_minimal_hit_without_detail():
    raw = RawRecord(source_connector="grants_gov", source_id="1", payload={
        "hit": {"id": "1", "number": "X-1", "title": "T", "agencyCode": "DOT", "agency": "DOT",
                "openDate": "01/02/2026", "closeDate": "", "oppStatus": "posted", "alnist": ["20.205"]},
        "detail": {},
    })
    p = gg.normalize(raw)
    assert p.status == "open" and p.opens_at == date(2026, 1, 2) and p.closes_at is None
    assert p.alns == ["20.205"] and p.funding_type is None and p.amount_max is None
    assert p.applicant_types == [] and p.record_hash  # nothing invented


def test_unrestricted_expands_to_every_applicant_type():
    raw = RawRecord(source_connector="grants_gov", source_id="2", payload={
        "hit": {"id": "2", "title": "U", "oppStatus": "forecasted"},
        "detail": {"synopsis": {"applicantTypes": [{"id": "99"}, {"id": "25"}],
                                "fundingInstruments": [{"id": "CA"}],
                                "fundingActivityCategories": [{"id": "ENV"}, {"id": "ZZ"}],
                                "costSharing": "No", "awardCeiling": "250000"}},
    })
    p = gg.normalize(raw)
    assert {t.value for t in p.applicant_types} == set(ALL_APPLICANT_TYPES)
    assert all(t.source_code == "99" for t in p.applicant_types)
    assert p.funding_type == "cooperative_agreement" and p.match_required is False
    assert p.category_pairs() == [("other", "ZZ"), ("water", "ENV")]
    assert p.amount_max == 250000 and p.status == "forecasted"


def _fixture_pairs():
    search = FIXTURES / "search2_page1.json"
    details = sorted(FIXTURES.glob("fetch_*.json"))
    if not search.exists() or not details:
        return []
    hits = {str(h["id"]): h for h in json.loads(search.read_text())["data"]["oppHits"]}
    out = []
    for d in details:
        oid = d.stem.removeprefix("fetch_")
        if oid in hits:
            out.append((hits[oid], json.loads(d.read_text())["data"]))
    return out


@pytest.mark.skipif(not _fixture_pairs(), reason="fixtures not captured yet: run scripts/probe_grants_gov.py")
def test_normalize_real_fixtures():
    for hit, detail in _fixture_pairs():
        p = gg.normalize(RawRecord(source_connector="grants_gov", source_id=str(hit["id"]),
                                   payload={"hit": hit, "detail": detail}))
        assert p.name and p.status in ("open", "forecasted")
        assert p.opens_at is not None
        assert p.administering_agency
        assert p.applicant_types, "eligibility codes did not map; check APPLICANT_CODES against the fixture"
        assert p.eligibility_text
        assert p.alns
