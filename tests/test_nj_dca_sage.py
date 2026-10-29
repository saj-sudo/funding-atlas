"""New Jersey DCA SAGE connector tests. Everything runs against the saved page (never the network): four RFPs across the
two divisions the page lists, with contacts removed, and an empty-list page built from the same chrome."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import nj_dca_sage as nj
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "nj_dca_sage"
TODAY = date(2026, 10, 28)
AHTF, LEAD, NRTC, VESO = (
    "affordable-housing-trust-fund-2027", "lead-safe-home-remediation-2026",
    "neighborhood-revitalization-tax-credit-planning-24", "volunteer-emergency-service-organization-loan-2027",
)


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def rfps() -> dict[str, dict]:
    parsed, _ = nj.parse_page(read("list.html"))
    return dict(zip(nj.unique_slugs([r["title"] for r in parsed]), parsed, strict=True))


def normalize(slug: str, today: date = TODAY):
    return nj.normalize(RawRecord(source_connector=nj.CONNECTOR, source_id=slug, payload=rfps()[slug]), today)


def tags(slug: str) -> set[str]:
    return {t.value for t in normalize(slug).applicant_types}


# ---------- parsing ----------

def test_the_page_parses_into_its_rfps_in_order_with_their_divisions():
    parsed, expected = nj.parse_page(read("list.html"))
    assert expected == len(parsed) == 4
    assert [r["title"] for r in parsed] == [
        "Affordable Housing Trust Fund 2027", "Lead-Safe Home Remediation 2026",
        "Neighborhood Revitalization Tax Credit Planning 24", "Volunteer Emergency Service Organization Loan 2027",
    ]
    assert [r["division"] for r in parsed] == [
        "Division of Housing and Community Resources", "Division of Housing and Community Resources",
        "Division of Housing and Community Resources", "Division on Fire Safety",
    ]


def test_fields_are_read_by_id_even_though_the_positions_are_not_contiguous():
    """The fixture keeps RFPs 0, 3, 5 and 9 of the original ten."""
    f = rfps()[AHTF]["fields"]
    assert f["rfpDueDate"] == "11/19/2026" and f["rfpMinimumAwardAmount"] == "$50,000.00"
    assert f["rfpMaximumAwardAmount"] == "$3,000,000.00" and f["rfpEstimateTotalRFPFunds"] == "$30,000,000.00"
    assert f["rfpEligibility"] == "Municipalities, for-profit and non-profit affordable housing developers"
    assert rfps()[VESO]["fields"]["rfpContractStartDate"] == ""


def test_the_program_contact_is_in_neither_the_fixture_nor_the_payload():
    page = read("list.html")
    assert "@" not in page and "mailto" not in page.lower() and "(609)" not in page and "<script" not in page
    assert 'type="hidden"' not in page
    for rfp in rfps().values():
        assert not [k for k in rfp["fields"] if "Contact" in k]


def test_unique_slugs():
    assert nj.unique_slugs(["Fund 2027", "Other", "Fund 2027", "Fund 2027"]) == ["fund-2027", "other", "fund-2027-2", "fund-2027-3"]


# ---------- status ----------

@pytest.mark.parametrize("due, expected", [
    (date(2026, 11, 19), "open"), (date(2026, 10, 28), "open"), (date(2026, 10, 27), "closed"), (None, "open"),
])
def test_status_for(due, expected):
    assert nj.status_for(due, TODAY) == expected


def test_a_past_deadline_reads_closed_and_a_future_one_open():
    assert normalize(AHTF).status == "open" and normalize(AHTF, date(2026, 11, 20)).status == "closed"
    assert normalize(AHTF).closes_at == date(2026, 11, 19) and normalize(AHTF).opens_at is None


# ---------- mapping ----------

def test_municipal_rfp_fields():
    p = normalize(AHTF)
    assert p.source_url == nj.LIST_URL and p.source_id == AHTF and p.name == "Affordable Housing Trust Fund 2027"
    assert (p.level, p.jurisdiction, p.agency_code) == ("state", "NJ", "NJ-DCA")
    assert p.administering_agency == "Department of Community Affairs, Division of Housing and Community Resources"
    assert (p.amount_min, p.amount_max, p.funding_source, p.rolling, p.closes_at_text) == (50000, 3000000, "direct", None, None)
    assert p.eligibility_text == "Municipalities, for-profit and non-profit affordable housing developers"
    assert p.summary.startswith("The Affordable Housing Trust Fund Program (AHTF) is to provide municipalities")
    assert p.eligibility_structured == {
        "division": "Division of Housing and Community Resources",
        "population": "Households that are low and moderate income as defined by the Council on Affordable Housing",
        "total_funds": "$30,000,000.00", "grant_period": "7/1/2026 - 6/30/2027",
    }
    assert p.categories == [] and p.alns == [] and p.external_number is None


def test_fire_safety_division_and_a_loan_with_no_grant_period():
    p = normalize(VESO)
    assert p.administering_agency == "Department of Community Affairs, Division on Fire Safety"
    assert p.funding_type == "loan" and (p.amount_min, p.amount_max) == (1000, 50000)
    assert "grant_period" not in p.eligibility_structured and p.eligibility_structured["division"] == "Division on Fire Safety"


def test_a_tax_credit_in_the_title_is_not_a_funding_type_here():
    """A planning grant named for the program it supports; the page gives it a grant period."""
    assert normalize(NRTC).funding_type is None
    assert nj.funding_type_of("Neighborhood Revitalization Tax Credit Planning 24") is None
    assert nj.funding_type_of("Volunteer Emergency Service Organization Loan 2027") == "loan"
    assert nj.funding_type_of("Home Repair Grant 2027") == "grant"
    assert nj.funding_type_of("Affordable Housing Trust Fund 2027") is None


def test_a_stale_looking_posting_is_repeated_not_corrected():
    p = normalize(NRTC)
    assert p.eligibility_structured["grant_period"] == "7/1/2023 - 6/3/2024" and p.closes_at == date(2026, 12, 31)
    assert p.status == "open"


@pytest.mark.parametrize("text, expected", [
    ("$50,000.00", 50000), ("$3,000,000.00", 3000000), ("1,000", 1000), ("", None), ("None", None), ("TBD", None),
])
def test_money(text, expected):
    assert nj.money(text) == expected


# ---------- applicants ----------

def test_municipalities_and_units_of_local_government_are_tagged():
    assert tags(AHTF) == {"municipality", "business", "nonprofit"}
    assert tags(LEAD) == {"municipality", "county", "nonprofit"}


def test_nonprofit_only_and_untagged_rounds():
    assert tags(NRTC) == {"nonprofit"}
    assert tags(VESO) == set()          # volunteer fire companies, first aid squads: not in the shared vocabulary


def test_a_negated_sentence_is_dropped():
    assert {t.value for t in nj.applicant_tags("Nonprofits may apply. Municipalities are not eligible.")} == {"nonprofit"}
    assert nj.applicant_tags("") == []


# ---------- fetch, through a real client with a mock transport ----------

def _patch(monkeypatch, handler) -> list[httpx.Request]:
    calls: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(nj, "_client", lambda: httpx.Client(transport=httpx.MockTransport(wrapped)))
    monkeypatch.setattr(nj.time, "sleep", lambda s: None)
    return calls


def test_fetch_reads_the_one_page(monkeypatch):
    calls = _patch(monkeypatch, lambda r: httpx.Response(200, text=read("list.html")))
    records = nj.fetch()
    assert [r.source_id for r in records] == [AHTF, LEAD, NRTC, VESO]
    assert [str(c.url) for c in calls] == [nj.LIST_URL]
    assert records[0].payload["division"] == "Division of Housing and Community Resources" and "fields" in records[0].payload
    assert len(nj.fetch(limit=2)) == 2


def test_an_honestly_empty_list_returns_no_records(monkeypatch):
    _patch(monkeypatch, lambda r: httpx.Response(200, text=read("empty.html")))
    assert nj.fetch() == []


def test_a_page_that_is_not_the_list_aborts_the_run(monkeypatch):
    _patch(monkeypatch, lambda r: httpx.Response(200, text="<html><body>Service unavailable</body></html>"))
    with pytest.raises(ValueError, match="not the RFP list page"):
        nj.fetch()


def test_a_layout_change_aborts_the_run(monkeypatch):
    """One deadline label renamed: the page now has four RFPs but only three deadline labels."""
    page = read("list.html").replace("Deadline for Submission:", "Due:", 1)
    _patch(monkeypatch, lambda r: httpx.Response(200, text=page))
    with pytest.raises(ValueError, match="found 4 RFPs but 3 deadline labels"):
        nj.fetch()


def test_an_http_error_aborts_the_run_without_a_retry(monkeypatch):
    calls = _patch(monkeypatch, lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(httpx.HTTPStatusError):
        nj.fetch()
    assert len(calls) == 1


def test_a_dropped_connection_is_retried(monkeypatch):
    seen = []

    def handler(request):
        seen.append(1)
        if len(seen) < 3:
            raise httpx.ConnectError("reset")
        return httpx.Response(200, text=read("list.html"))

    _patch(monkeypatch, handler)
    assert len(nj.fetch()) == 4 and len(seen) == 3


def test_three_dropped_connections_give_up(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("reset")

    calls = _patch(monkeypatch, handler)
    with pytest.raises(httpx.ConnectError):
        nj.fetch()
    assert len(calls) == nj.TRIES


# ---------- resolve_missing ----------

def test_an_rfp_that_left_the_page_is_unknown_without_a_request(monkeypatch):
    monkeypatch.setattr(nj, "_client", lambda: pytest.fail("no client"))
    assert nj.resolve_missing(AHTF) == {"status": "unknown"}
