"""Texas eGrants connector tests. Everything runs against the saved pages (never the network): the Active page, two
trimmed archive pages and a page past the end."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import tx_egrants as tx
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "tx_egrants"
TODAY = date(2026, 10, 28)
ALERRT27 = "alerrt-travel-assistance-fy2027"
COUNTY27 = "county-essential-services-grant-grant-program-fy2027"
MUSIC27 = "music-educational-and-community-programs-fy2027"
VAWA27 = "violence-against-women-justice-and-training-program-fy2027"
ALERRT25 = "alerrt-travel-assistance-fy2025"
BORDER_ZONE = "border-zone-fire-departments-bzfd-fy2027"
BORDER_PROSECUTION = "border-prosecution-unit-bpu-fy2026"
COUNTY25 = "county-essential-services-grant-program-fy2025"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def cards() -> dict[str, dict]:
    out = {}
    for name in ("active.html", "archive_0.html", "archive_1.html"):
        for card in tx.parse_cards(read(name)):
            out[card["slug"]] = card
    return out


def normalize(slug: str):
    return tx.normalize(RawRecord(source_connector=tx.CONNECTOR, source_id=slug, payload={"listed": "x", "card": cards()[slug]}), TODAY)


def tags(slug: str) -> set[str]:
    return {t.value for t in normalize(slug).applicant_types}


# ---------- parsing ----------

def test_cards_parse_from_each_page():
    assert [c["slug"] for c in tx.parse_cards(read("active.html"))] == [ALERRT27, COUNTY27, MUSIC27, VAWA27]
    assert len(tx.parse_cards(read("archive_0.html"))) == 4 and len(tx.parse_cards(read("archive_1.html"))) == 2
    assert tx.parse_cards(read("archive_end.html")) == []


def test_a_card_has_every_labelled_field():
    c = cards()[ALERRT27]
    assert c["name"] == "ALERRT Travel Assistance, FY2027"
    assert (c["available"], c["due"], c["total_funds"]) == ("09/01/2026", "08/31/2027", "$TBD")
    assert c["purpose"][0].startswith("The purpose of this announcement is to solicit applications from law enforcement")
    assert c["eligible"][0].startswith("Applications may be submitted by independent school districts")


def test_eligible_text_in_a_bare_block_is_still_read():
    """22 cards hold the text outside any <p>."""
    assert cards()[BORDER_PROSECUTION]["eligible"][0].startswith("Counties within the Texas border region")


def test_fixtures_carry_no_scripts_or_hidden_inputs():
    for name in ("active.html", "archive_0.html", "archive_1.html", "archive_end.html"):
        html = read(name)
        assert "<script" not in html and 'type="hidden"' not in html and "csrf_token" not in html


def test_archive_urls():
    assert tx.archive_url(0) == "https://egrants.gov.texas.gov/fundingopp/archive"
    assert tx.archive_url(1) == "https://egrants.gov.texas.gov/fundingopp/archive/P25"
    assert tx.archive_url(5) == "https://egrants.gov.texas.gov/fundingopp/archive/P125"


# ---------- status and dates ----------

@pytest.mark.parametrize("slug, status", [(ALERRT27, "open"), (MUSIC27, "open"), (ALERRT25, "closed")])
def test_status_comes_from_the_dates(slug, status):
    assert normalize(slug).status == status


def test_a_round_on_the_active_page_past_its_due_date_is_closed():
    p = normalize(VAWA27)
    assert p.status == "closed" and p.opens_at == date(2025, 12, 15) and p.closes_at == date(2026, 2, 12)


@pytest.mark.parametrize("available, due, expected", [
    (date(2026, 9, 1), date(2027, 8, 31), "open"),
    (date(2026, 9, 1), date(2026, 10, 28), "open"),        # the due day itself is open
    (date(2026, 9, 1), date(2026, 10, 27), "closed"),
    (date(2026, 11, 1), date(2027, 1, 1), "forecasted"),
    (None, None, "open"),
])
def test_status_for(available, due, expected):
    assert tx.status_for(available, due, TODAY) == expected


def test_a_date_cell_that_is_not_a_date_goes_to_the_cycle_text():
    card = {**cards()[ALERRT27], "due": "Rolling", "available": "TBD"}
    assert tx.closes_text_for(card) == "Due date: Rolling; Available: TBD"
    assert tx.closes_text_for(cards()[ALERRT27]) is None


# ---------- applicants ----------

def test_units_of_local_government_and_school_districts():
    assert tags(ALERRT27) == {"county", "municipality", "higher_ed", "school"}


def test_counties_only_and_invitation_only():
    p = normalize(COUNTY27)
    assert {t.value for t in p.applicant_types} == {"county"}
    assert p.eligibility_structured == {"total_funds": "$TBD", "invitation_only": True}
    assert normalize(COUNTY25).eligibility_structured["invitation_only"] is True


def test_nonprofit_only_round():
    assert tags(MUSIC27) == {"nonprofit"}


def test_the_negated_nonprofit_sentence_is_dropped_but_the_round_still_names_nonprofits_elsewhere():
    """'Non-profit applicants seeking to provide direct services to victims of crime are not eligible ...'"""
    negated = [s for p in cards()[VAWA27]["eligible"] for s in tx.sentences(p) if tx.NEGATION_RE.search(s)]
    assert any("are not eligible under this solicitation" in s for s in negated)
    assert {t.value for t in tx.applicant_types_for(negated)} == {"nonprofit"}      # the dropped sentence alone would tag it
    assert "nonprofit" in tags(VAWA27)                                               # named as eligible in another sentence


def test_applicant_tags_drop_only_the_negated_sentence():
    got = tx.applicant_tags(["Volunteer Fire Departments are not eligible.", "Applications may be submitted by cities and counties."])
    assert {t.value for t in got} == {"municipality", "county"}
    assert tx.applicant_tags(["Non-profit applicants are not eligible under this solicitation."]) == []
    assert tx.applicant_tags([]) == []


def test_border_zone_fire_departments_tag_counties_and_cities_not_volunteer_departments():
    assert tags(BORDER_ZONE) == {"county", "municipality"}


# ---------- mapping ----------

def test_fields():
    p = normalize(ALERRT27)
    assert p.source_url == "https://egrants.gov.texas.gov/fundingopp/page/alerrt-travel-assistance-fy2027"
    assert (p.level, p.jurisdiction, p.administering_agency, p.agency_code) == ("state", "TX", "Office of the Governor", None)
    assert (p.funding_source, p.amount_min, p.amount_max, p.match_required, p.rolling) == ("direct", None, None, None, None)
    assert p.categories == [] and p.alns == [] and p.external_number is None
    assert p.summary.startswith("The purpose of this announcement") and p.eligibility_text.count("\n") >= 1


def test_total_funds_is_kept_verbatim_and_a_bare_dollar_is_not():
    assert normalize(ALERRT25).eligibility_structured == {"total_funds": "$2.9 Million"}
    assert normalize(BORDER_ZONE).eligibility_structured is None
    assert normalize(ALERRT25).amount_max is None


def test_funding_type_from_the_title_keyword():
    assert normalize(COUNTY25).funding_type == "grant"            # "County Essential Services Grant Program, FY2025"
    assert normalize(ALERRT27).funding_type is None               # no keyword in "ALERRT Travel Assistance, FY2027"


def test_every_saved_round_normalizes():
    for slug in cards():
        p = normalize(slug)
        assert p.name and p.source_url.startswith("https://egrants.gov.texas.gov/fundingopp/page/")


# ---------- fetch ----------

class _Pages:
    """A stand-in for `_get`: URL -> saved page. `broken` URLs raise a connection error."""

    def __init__(self, broken=(), endless=False):
        self.broken, self.calls, self.endless = set(broken), [], endless

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        if url == tx.ACTIVE_URL:
            return read("active.html")
        if url == tx.archive_url(0):
            return read("archive_0.html")
        if url == tx.archive_url(1):
            return read("archive_1.html")
        return read("archive_0.html") if self.endless else read("archive_end.html")


@pytest.fixture
def pages(monkeypatch):
    monkeypatch.setattr(tx.time, "sleep", lambda s: None)
    stub = _Pages()
    monkeypatch.setattr(tx, "_get", stub)
    return stub


def test_fetch_reads_active_then_the_archive_until_an_empty_page(pages):
    records = tx.fetch()
    assert [r.source_id for r in records][:4] == [ALERRT27, COUNTY27, MUSIC27, VAWA27]
    assert len(records) == 10 and len({r.source_id for r in records}) == 10
    assert pages.calls == [tx.ACTIVE_URL, tx.archive_url(0), tx.archive_url(1), tx.archive_url(2)]
    assert records[0].payload["listed"] == "active" and records[-1].payload["listed"] == "archive"
    assert len(tx.fetch(limit=3)) == 3


def test_a_round_on_both_lists_is_one_record_and_the_active_copy_wins(monkeypatch, pages):
    class Both(_Pages):
        def __call__(self, client, url):
            if url == tx.archive_url(0):
                return read("active.html")
            return super().__call__(client, url)

    monkeypatch.setattr(tx, "_get", Both())
    records = tx.fetch()
    assert [r.source_id for r in records].count(ALERRT27) == 1
    assert next(r for r in records if r.source_id == ALERRT27).payload["listed"] == "active"


def test_a_page_that_cannot_be_read_aborts_the_run(monkeypatch, pages):
    for broken in (tx.ACTIVE_URL, tx.archive_url(1)):
        monkeypatch.setattr(tx, "_get", _Pages(broken={broken}))
        with pytest.raises(httpx.ConnectError):
            tx.fetch()


def test_an_archive_longer_than_the_cap_aborts_loudly(monkeypatch, pages):
    monkeypatch.setattr(tx, "_get", _Pages(endless=True))
    with pytest.raises(RuntimeError, match="more than 20 pages"):
        tx.fetch()


# ---------- _get, through a real client ----------

def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_get_retries_a_dropped_connection(monkeypatch):
    monkeypatch.setattr(tx.time, "sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("reset")
        return httpx.Response(200, text="ok")

    assert tx._get(_client(handler), "https://x.test/") == "ok" and len(calls) == 3


def test_get_does_not_retry_an_http_error_status():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500, text="boom")

    with pytest.raises(httpx.HTTPStatusError):
        tx._get(_client(handler), "https://x.test/")
    assert len(calls) == 1


# ---------- resolve_missing ----------

def test_a_round_on_neither_list_is_unknown_without_a_request(monkeypatch):
    monkeypatch.setattr(tx, "_get", lambda *a: pytest.fail("no request"))
    monkeypatch.setattr(tx, "_client", lambda: pytest.fail("no client"))
    assert tx.resolve_missing(ALERRT27) == {"status": "unknown"}
