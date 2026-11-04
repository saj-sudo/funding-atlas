"""Massachusetts One Stop connector tests, against the saved index, nine program pages and the MassDevelopment page
(never the network): the program list and its agencies, the round's dates, the status rule, the applicant lines on
each template, the fallback when a page fails."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import urldefrag

import httpx
import pytest

from connectors import hand_list as hl
from connectors import ma_onestop as ma
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "ma_onestop"
TODAY = date(2026, 11, 4)


def read(name: str) -> str:
    return (FIX / f"{name}.html").read_text(encoding="utf-8")


def index() -> dict:
    return ma.parse_index(read("index"))


def programs() -> dict[str, dict]:
    return {p["source_id"]: p for p in index()["programs"]}


def normalize(sid: str, today: date = TODAY):
    program = programs()[sid]
    plain, fragment = urldefrag(program["url"])
    page = ma.parse_page(read("massdev" if fragment else sid), fragment or None)
    return ma.normalize(RawRecord(source_connector=ma.CONNECTOR, source_id=sid, payload={"program": program, "round": index()["round"], "page": page}), today)


def test_fixtures_carry_no_scripts_or_contacts():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "ma__contact-us" not in text and "McKenzie" not in text


def test_index_lists_fourteen_programs_under_three_agencies():
    got = programs()
    assert len(got) == 14
    assert [p["agency_code"] for p in got.values()].count("MA-EOED") == 5
    assert [p["agency_code"] for p in got.values()].count("MA-EOHLC") == 4
    assert [p["agency_code"] for p in got.values()].count("MA-MASSDEV") == 5
    assert got["massworks"]["url"] == "https://www.mass.gov/orgs/massworks"
    assert got["massworks"]["agency"] == "Executive Office of Economic Development"
    assert got["massdev#site-readiness-program"]["url"].endswith("/grant-programs/#site-readiness-program")
    assert got["housing-choice-grant-program"]["title"] == "Housing Choice Grant Program"


def test_source_ids():
    assert ma.source_id_for("https://www.mass.gov/how-to/housing-choice-grant-program") == "housing-choice-grant-program"
    assert ma.source_id_for("https://www.massdevelopment.com/x/grant-programs/#tdi-equity-investment-program") == "massdev#tdi-equity-investment-program"


def test_round_dates_come_from_the_key_dates_lines_not_the_heading():
    rnd = index()["round"]
    assert rnd["heading"] == "FY27 Round of the One Stop: Key Dates"
    opens, closes, line = ma.round_dates(rnd["lines"])
    assert (opens, closes) == (date(2026, 1, 23), date(2026, 6, 3))
    assert line == "Full Application Submission Period : May 4, 2026 – June 3, 2026"
    assert "​" not in " ".join(rnd["lines"])


@pytest.mark.parametrize("opens, closes, today, status", [
    (date(2026, 1, 23), date(2026, 6, 3), date(2026, 11, 4), "closed"),
    (date(2026, 1, 23), date(2026, 6, 3), date(2026, 5, 1), "open"),
    (date(2026, 1, 23), date(2026, 6, 3), date(2026, 6, 3), "open"),
    (date(2027, 1, 20), date(2027, 6, 2), date(2026, 11, 4), "forecasted"),
    (None, date(2027, 6, 2), date(2026, 11, 4), "open"),
    (date(2026, 1, 23), None, date(2026, 11, 4), "unknown"),
])
def test_status_rule(opens, closes, today, status):
    assert ma.status_for(opens, closes, today) == status


def test_every_program_carries_the_one_round():
    for sid in programs():
        p = normalize(sid)
        assert (p.status, p.opens_at, p.closes_at) == ("closed", date(2026, 1, 23), date(2026, 6, 3))
        assert p.closes_at_text == "Full Application Submission Period : May 4, 2026 – June 3, 2026"
        assert p.eligibility_structured == {"one_stop_round": "FY27 Round of the One Stop: Key Dates"}
        assert p.jurisdiction == "MA" and p.level == "state" and p.funding_type == "grant" and p.funding_source == "direct"


def test_round_without_a_deadline_is_unknown():
    program = programs()["massworks"]
    raw = RawRecord(source_connector=ma.CONNECTOR, source_id="massworks", payload={"program": program, "round": {"heading": "Key Dates", "lines": ["Opens: January 23, 2026"]}, "page": None})
    p = ma.normalize(raw, TODAY)
    assert p.status == "unknown" and p.closes_at is None and p.opens_at == date(2026, 1, 23) and p.summary is None


def test_applicants_on_each_template():
    assert normalize("rural-development-fund").eligibility_text.startswith("Eligible municipalities and other public entities are invited")   # info-details
    assert "open to municipalities" in normalize("housingworks-infrastructure-program-hwip").eligibility_text   # how-to
    assert normalize("massworks").eligibility_text.startswith("MassWorks provides grants to communities")   # orgs
    hc = normalize("housing-choice-grant-program")
    assert "a community must have a current Housing Choice Community" in hc.eligibility_text
    assert [t.value for t in hc.applicant_types] == ["municipality"]
    assert [t.value for t in normalize("mbta-communities-catalyst-fund").applicant_types] == ["municipality"]
    assert normalize("community-planning-grant-program").eligibility_text is None
    assert normalize("massdev#tdi-equity-investment-program").eligibility_text is None


def test_contacts_and_chrome_are_not_read():
    page = ma.parse_page(read("housing-choice-grant-program"))
    text = " ".join(t for _, t in page["blocks"])
    assert "Coordinator" not in text and "Table of Contents" not in text and "feedback" not in text.lower()
    assert page["title"] == "Housing Choice Grant Program"


def test_massdevelopment_sections_are_read_by_id():
    page = ma.parse_page(read("massdev"), "underutilized-properties-program")
    assert page["title"] == "Underutilized Properties Program"
    assert page["blocks"][0] == ("p", "Targets underutilized, abandoned, or vacant properties.")
    assert ma.parse_page(read("massdev"), "no-such-section") == {"title": "", "blocks": []}


def test_fields_and_categories():
    p = normalize("mbta-communities-catalyst-fund")
    assert (p.name, p.administering_agency, p.agency_code) == ("MBTA Communities Catalyst Fund", "Executive Office of Housing and Livable Communities", "MA-EOHLC")
    assert [(c.value, c.source_code) for c in p.categories] == [("housing", "Executive Office of Housing and Livable Communities")]
    assert [c.value for c in normalize("massworks").categories] == ["infrastructure"]
    assert [c.value for c in normalize("massdev#brownfields-funding").categories] == ["infrastructure"]
    assert p.source_url == "https://www.mass.gov/how-to/mbta-communities-catalyst-fund"
    assert p.summary and p.record_hash


class _Site:
    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        if url == ma.INDEX_URL:
            return read("index")
        if "massdevelopment.com" in url:
            return read("massdev")
        return read(url.rstrip("/").rsplit("/", 1)[-1])


def test_fetch_reads_the_index_then_each_page_once(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    site = _Site()
    monkeypatch.setattr(ma, "_get", site)
    records = ma.fetch()
    assert [r.source_id for r in records] == list(programs())
    assert len(site.calls) == 1 + 9 + 1   # the index, nine mass.gov pages, MassDevelopment once
    assert records[0].payload["page"]["title"] == "MassWorks"
    prior = {r.source_id: r.payload for r in records}
    url = programs()["rural-development-fund"]["url"]
    monkeypatch.setattr(ma, "_get", _Site(broken={url}))
    again = {r.source_id: r.payload for r in ma.fetch(prior=prior)}
    assert again["rural-development-fund"]["page"] == prior["rural-development-fund"]["page"]
    assert {r.source_id: r.payload for r in ma.fetch()}["rural-development-fund"]["page"] is None
    monkeypatch.setattr(ma, "_get", _Site(broken={ma.INDEX_URL}))
    with pytest.raises(httpx.ConnectError):
        ma.fetch()
    monkeypatch.setattr(ma, "_get", _Site())
    assert [r.source_id for r in ma.fetch(limit=3)] == list(programs())[:3]


def test_resolve_missing_is_unknown():
    assert ma.resolve_missing("massworks") == {"status": "unknown"}
