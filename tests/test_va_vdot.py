"""Virginia VDOT connector tests, against the saved index and six program pages (never the network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import va_vdot as va
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "va_vdot"
TODAY = date(2026, 11, 3)


def read(name: str) -> str:
    return (FIX / f"{name}.html").read_text(encoding="utf-8")


def cards() -> dict[str, dict]:
    return {c["slug"]: c for c in va.parse_cards(read("index"))}


def normalize(slug: str, today: date = TODAY):
    return va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id=slug, payload={"card": cards()[slug], "page": va.parse_page(read(slug))}), today)


def test_cards_parse_and_process_pages_are_excluded():
    got = cards()
    assert set(got) == {"access-roads-programs", "other-programs", "revenue-sharing", "state-of-good-repair", "urban-program", "transportation-alternatives"}
    assert got["revenue-sharing"]["url"] == "https://www.vdot.virginia.gov/doing-business/for-localities/local-assistance/revenue-sharing/"
    assert got["revenue-sharing"]["blurb"].endswith("for use by a county, city, or town to construct or improve the highway systems.")
    assert "locally-administered-projects" in read("index") and "training-and-outreach" in read("index")


def test_fixtures_carry_no_scripts_or_contacts():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "@vdot.virginia.gov" not in text


def test_split_spans_are_joined_into_words():
    page = va.parse_page(read("revenue-sharing"))
    assert page["title"] == "Revenue sharing"
    text = " ".join(page["paragraphs"])
    assert "applications are biennial" in text and "appl ications" not in text


def test_cycle_sentences():
    assert normalize("state-of-good-repair").closes_at_text == "The application period typically opens the first week of October and closes by mid-December each year."
    assert normalize("urban-program").closes_at_text == "Change requests are due February 1st to be included in the following fiscal year."
    assert normalize("revenue-sharing").closes_at_text.startswith("Funding applications are biennial and must be submitted")
    assert normalize("access-roads-programs").closes_at_text is None


def test_every_record_is_unknown_without_a_full_date():
    for slug in cards():
        assert normalize(slug).status == "unknown" and normalize(slug).closes_at is None


@pytest.mark.parametrize("sentence, status", [
    ("Applications are due March 1, 2027.", "open"), ("Applications are due March 1, 2026.", "unknown"),
    ("The application period is now closed.", "closed"), (None, "unknown"),
])
def test_status_for(sentence, status):
    assert va.status_for(sentence, va.closes_at_for(sentence), TODAY) == status


def test_section_and_blurb_are_applicant_text():
    p = normalize("revenue-sharing")
    assert p.eligibility_text.startswith("For localities (VDOT section): VDOT administers the Revenue Sharing Program")
    assert {"municipality", "county"} <= {t.value for t in p.applicant_types}
    assert "localities" in {t.source_code for t in p.applicant_types}


def test_a_page_with_no_applicant_sentence_still_tags_from_the_section():
    p = normalize("access-roads-programs")
    assert p.eligibility_text.startswith("For localities (VDOT section)")
    assert {t.value for t in p.applicant_types} == {"municipality", "county"}


def test_urban_program_names_municipalities():
    p = normalize("urban-program")
    assert any("A municipality qualifies for the urban program" in line for line in p.eligibility_text.split("\n"))


def test_fields():
    p = normalize("state-of-good-repair")
    assert p.name == "State of Good Repair Program" and p.source_url.endswith("/local-assistance/state-of-good-repair/")
    assert (p.administering_agency, p.agency_code, p.funding_type, p.funding_source, p.categories) == ("Department of Transportation", "VA-VDOT", None, "direct", [])
    assert p.summary and p.eligibility_structured is None


def test_card_fields_stand_in_when_the_page_could_not_be_read():
    p = va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id="revenue-sharing", payload={"card": cards()["revenue-sharing"], "page": None}), TODAY)
    assert p.name == "Revenue sharing" and p.summary.startswith("VDOT administers") and p.status == "unknown"


class _Site:
    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        return read("index") if url == va.INDEX_URL else read(url.rstrip("/").rsplit("/", 1)[-1])


def test_fetch_reads_the_index_then_each_program_page(monkeypatch):
    monkeypatch.setattr(va.time, "sleep", lambda s: None)
    monkeypatch.setattr(va, "_get", _Site())
    records = va.fetch()
    assert [r.source_id for r in records] == list(cards())
    assert records[0].payload["page"]["title"]
    prior = {r.source_id: r.payload for r in records}
    url = cards()["urban-program"]["url"]
    monkeypatch.setattr(va, "_get", _Site(broken={url}))
    assert {r.source_id: r.payload for r in va.fetch(prior=prior)}["urban-program"]["page"] == prior["urban-program"]["page"]
    assert {r.source_id: r.payload for r in va.fetch()}["urban-program"]["page"] is None
    monkeypatch.setattr(va, "_get", _Site(broken={va.INDEX_URL}))
    with pytest.raises(httpx.ConnectError):
        va.fetch()
    monkeypatch.setattr(va, "_get", _Site())
    assert len(va.fetch(limit=2)) == 2


def test_resolve_missing_is_unknown():
    assert va.resolve_missing("revenue-sharing") == {"status": "unknown"}
