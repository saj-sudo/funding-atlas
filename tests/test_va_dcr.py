"""Virginia DCR connector tests, against the six saved pages (never the network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from connectors import va_dcr as va
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "va_dcr"
TODAY = date(2026, 11, 3)


def read(slug: str) -> str:
    return (FIX / f"{slug}.html").read_text(encoding="utf-8")


def normalize(slug: str, today: date = TODAY):
    return va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id=slug, payload={"path": va.PAGES[slug], "page": va.parse_page(read(slug))}), today)


def test_fixtures_carry_no_scripts_questions_or_addresses():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "@dcr.virginia.gov" not in text


def test_page_title_and_blocks_stop_at_questions():
    page = va.parse_page(read("lwcf"))
    assert page["title"] == "Land and Water Conservation Fund - General Information"
    assert page["blocks"][0] == ("label", "2026 LWCF Grant Round is now closed.")
    assert not any("Questions" in t for _, t in page["blocks"])


def test_the_labelled_list_is_the_applicant_passage():
    p = normalize("lwcf")
    assert p.eligibility_text.split("\n") == ["Counties, cities and towns", "Park and recreation authorities", "Tribes", "State agencies"]
    assert {t.value for t in p.applicant_types} == {"municipality", "county", "tribe", "state"}


@pytest.mark.parametrize("slug, phrase", [
    ("trailfnd", "Funding may be awarded to city, county, town, tribal or other government entities."),
    ("trail-access-program", "Eligible applicants include local (city, county, town) or tribal governments"),
    ("vlcf", "State agencies, local governments, other public bodies"),
])
def test_applicant_sentences_in_prose(slug, phrase):
    p = normalize(slug)
    assert phrase in p.eligibility_text
    assert {"municipality", "county"} <= {t.value for t in p.applicant_types}


def test_a_negated_applicant_sentence_tags_nothing():
    p = normalize("abpp-grants")
    assert "not eligible to apply" in p.eligibility_text and p.applicant_types == []


def test_project_sites_being_eligible_is_not_an_applicant_sentence():
    assert normalize("orlp").eligibility_text is None and normalize("orlp").applicant_types == []


def test_round_sentence_prefers_closed_over_mentions():
    assert normalize("trailfnd").closes_at_text == "The 2026 RTP grant closed on May 5, 2026."
    assert normalize("vlcf").closes_at_text.startswith("The Surry-Skiffes Creek grant round closed")
    assert normalize("lwcf").closes_at_text == "2026 LWCF Grant Round is now closed."


@pytest.mark.parametrize("slug, status, closes_at", [
    ("lwcf", "closed", None), ("trailfnd", "closed", date(2026, 5, 5)), ("vlcf", "closed", None),
    ("orlp", "unknown", None), ("trail-access-program", "unknown", None), ("abpp-grants", "unknown", None),
])
def test_status_and_closing_date(slug, status, closes_at):
    p = normalize(slug)
    assert (p.status, p.closes_at) == (status, closes_at)


@pytest.mark.parametrize("sentence, closes_at, today, status", [
    ("The round is now open; applications are due March 1, 2027.", date(2027, 3, 1), TODAY, "open"),
    ("Applications are due March 1, 2026.", date(2026, 3, 1), TODAY, "unknown"),
    ("The 2026 round is now closed.", None, TODAY, "closed"),
    (None, None, TODAY, "unknown"),
])
def test_status_for(sentence, closes_at, today, status):
    assert va.status_for(sentence, closes_at, today) == status


def test_closes_at_for():
    assert va.closes_at_for("The 2026 RTP grant closed on May 5, 2026.") == date(2026, 5, 5)
    assert va.closes_at_for("Applications are due by November 1 of each year.") is None
    assert va.closes_at_for("The board met on June 9, 2026.") is None


def test_federal_wording_and_match():
    assert normalize("lwcf").funding_source == "pass_through" and normalize("lwcf").match_required is True
    assert normalize("trailfnd").funding_source == "pass_through"          # Federal Highway Administration
    assert normalize("abpp-grants").funding_source == "pass_through"       # pass-through entity
    assert normalize("trail-access-program").funding_source == "direct" and normalize("vlcf").funding_source == "direct"


def test_category_from_the_index_title():
    assert normalize("lwcf").category_pairs() == [("parks", "Recreation Oriented Grants")]
    assert normalize("vlcf").categories == []


def test_fields():
    p = normalize("trail-access-program")
    assert p.source_url == "https://www.dcr.virginia.gov/recreational-planning/trail-access-program"
    assert (p.administering_agency, p.agency_code, p.jurisdiction, p.funding_type) == ("Department of Conservation and Recreation", "VA-DCR", "VA", "grant")
    assert p.summary.startswith("The Trail Access Grants program is a 100% reimbursement program")
    assert p.opens_at is None and p.rolling is None and p.eligibility_structured is None


class _Pages:
    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        return read(url.rsplit("/", 1)[-1])


def test_fetch_reads_the_six_pages_and_falls_back(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    monkeypatch.setattr(hl, "get", _Pages())
    records = va.fetch()
    assert [r.source_id for r in records] == list(va.PAGES)
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", _Pages(broken={va.BASE + va.PAGES["orlp"]}))
    again = va.fetch(prior=prior)
    assert {r.source_id: r.payload for r in again}["orlp"] == prior["orlp"]
    assert "orlp" not in {r.source_id for r in va.fetch()}
    monkeypatch.setattr(hl, "get", _Pages())
    assert len(va.fetch(limit=2)) == 2


def test_resolve_missing_is_unknown():
    assert va.resolve_missing("lwcf") == {"status": "unknown"}
