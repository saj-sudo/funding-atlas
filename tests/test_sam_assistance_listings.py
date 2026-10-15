"""SAM.gov Assistance Listings connector tests. Mapping tests run against saved fixtures (never the
network); the refetch gate and the lookup classifier are pure functions tested directly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from connectors import sam_assistance_listings as sam
from pipeline.models import ALL_APPLICANT_TYPES, RawRecord

FIXTURES = Path(__file__).parent / "fixtures" / "sam_assistance_listings"


def load(number: str) -> RawRecord:
    payload = json.loads((FIXTURES / f"programs_{number}.json").read_text())
    return RawRecord(source_connector=sam.CONNECTOR, source_id=number, payload=payload)


def test_search_params_match_plan():
    p = sam.search_params(2, 1000)
    assert p == {"index": "cfda", "q": "", "page": 2, "size": 1000, "sort": "-modifiedDate",
                 "mode": "search", "is_active": "true"}
    assert "is_active" not in sam.search_params(0, 100, q="14.218", active=None)


def test_normalize_cooperative_agreement_with_award_range():
    p = sam.normalize(load("97.106"))
    assert p.source_id == "97.106" and p.external_number == "97.106" and p.alns == ["97.106"]
    assert p.name == "Securing the Cities Program"
    assert p.level == "federal" and p.jurisdiction == "US" and p.funding_source == "direct"
    assert p.status == "unknown" and p.opens_at is None and p.closes_at is None
    assert p.source_url == "https://sam.gov/fal/8fdfa74764584e68866bd2c86952b754/view"
    assert p.administering_agency == "FEMA" and p.agency_code == "70FH10"
    assert p.funding_type == "cooperative_agreement"           # F002 wins over F010
    assert (p.amount_min, p.amount_max) == (502000, 2109867)   # FY2026 entry, not FY2025
    assert p.match_required is False
    assert p.closes_at_text == "2026-06-01 to 2026-08-31: Refer to Cooperative Agreement; See Notice of Funding Opportunity [ NOFO]"
    assert p.eligibility_text == "State, Local, and Tribal entities"
    assert p.applicant_pairs() == [("state", "ET26020"), ("tribe", "ET26040")]
    assert p.categories == [] and p.eligibility_structured is None
    assert "​" not in p.summary and p.summary.startswith("Goal:")


def test_normalize_formula_grant_lists_municipality():
    p = sam.normalize(load("14.218"))
    assert p.funding_type == "grant" and p.status == "unknown"
    assert ("municipality", "ET24010") in p.applicant_pairs()
    assert ("county", "ET24020") in p.applicant_pairs()
    assert p.match_required is False      # formula yes, matching no: only the matching flag is stored
    assert p.closes_at_text.startswith("2025-11-15 to 2026-08-16: See below.;")


def test_normalize_matching_required_state_only():
    p = sam.normalize(load("66.458"))
    assert p.match_required is True
    assert {v for v, _ in p.applicant_pairs()} == {"state", "tribe"}
    assert p.closes_at_text == "Contact the headquarters or regional location, as appropriate for application deadlines"


def test_normalize_invents_nothing_from_a_bare_hit():
    raw = RawRecord(source_connector=sam.CONNECTOR, source_id="93.00Y", payload={
        "hit": {"_id": "abc", "programNumber": "93.00Y", "title": "Bare &amp; minimal", "isActive": False},
        "detail": {},
    })
    p = sam.normalize(raw)
    assert p.name == "Bare & minimal" and p.status == "closed"
    assert p.funding_type is None and p.amount_max is None and p.match_required is None
    assert p.closes_at_text is None and p.summary is None and p.eligibility_text is None
    assert p.applicant_types == [] and p.administering_agency is None
    assert p.alns == ["93.00Y"] and p.record_hash


def test_unrestricted_and_local_codes_expand():
    raw = RawRecord(source_connector=sam.CONNECTOR, source_id="1.000", payload={
        "hit": {"_id": "x", "programNumber": "1.000", "title": "U", "isActive": True},
        "detail": {"data": {"eligibility": {"applicant": {"types": ["ET11010", "ET26010", "ET21010", "ET59999"]}}}},
    })
    pairs = sam.normalize(raw).applicant_pairs()
    assert {v for v, c in pairs if c == "ET11010"} == set(ALL_APPLICANT_TYPES)
    assert [v for v, c in pairs if c == "ET26010"] == ["county", "municipality"]
    assert not [c for _, c in pairs if c in ("ET21010", "ET59999")]   # federal / other: not represented


@pytest.mark.parametrize("codes, expected", [
    (["F010", "F002"], "cooperative_agreement"),
    (["F002", "F001"], "grant"),
    (["F004"], "loan"),
    (["N004"], "other"),
    ([], None),
])
def test_funding_type_priority_is_order_independent(codes, expected):
    assert sam.funding_type_for(codes) == expected
    assert sam.funding_type_for(list(reversed(codes))) == expected


def test_needs_detail_gate():
    hit = {"modifiedDate": "2026-10-09T01:00:21-04:00"}
    good_prior = {"hit": dict(hit), "detail": {"data": {"title": "x"}}}
    assert sam.needs_detail(hit, None)
    assert not sam.needs_detail(hit, good_prior)
    assert sam.needs_detail({"modifiedDate": "2026-10-10T00:00:00-04:00"}, good_prior)
    assert sam.needs_detail({}, good_prior)                                   # no stamp: refetch
    assert sam.needs_detail(hit, {"hit": dict(hit), "detail": {}})            # empty detail never frozen
    assert sam.needs_detail(hit, {"hit": dict(hit), "detail": {"errorCode": "x"}})


def test_classify_hit():
    assert sam.classify_hit(None) is None
    assert sam.classify_hit({"isActive": False}) == {"status": "closed"}
    assert sam.classify_hit({"isActive": True}) == {"status": "unknown"}


def test_search_fixture_shape():
    page = json.loads((FIXTURES / "search_page0.json").read_text())
    assert page["page"]["totalPages"] >= 1 and page["page"]["totalElements"] > 2000
    hit = page["_embedded"]["results"][0]
    assert {"_id", "programNumber", "title", "isActive", "modifiedDate", "organizationHierarchy"} <= set(hit)
