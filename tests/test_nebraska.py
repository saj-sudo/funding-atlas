"""Nebraska's agency connectors (ne_ded) against saved pages, and the shared rules Nebraska DED added."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 14)
AGENCIES = ["ne_ded"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def page(name: str, slug: str) -> dict:
    return mod(name).SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))


def programs(name: str, slug: str, today: date = TODAY) -> dict:
    """Every record a page makes (six for the CDBG page), by source_id."""
    m = mod(name)
    records = m.SITE.records_for(slug, m.PAGES[slug], [page(name, slug)], 0)
    return {sid: m.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today) for sid, payload in records}


def program(name: str, sid: str, today: date = TODAY):
    return programs(name, sid.split("#")[0], today)[sid]


def tags(name: str, sid: str) -> set[str]:
    return {t.value for t in program(name, sid).applicant_types}


def text(name: str, slug: str) -> str:
    return " ".join(t for _, t in page(name, slug)["blocks"])


def test_every_page_reads():
    for name in AGENCIES:
        m = mod(name)
        for slug in m.PAGES:
            for p in programs(name, slug).values():
                assert p.name and p.jurisdiction == "NE" and p.source_url.startswith(m.BASE), (name, slug)
            assert page(name, slug)["blocks"], (name, slug)


def test_ded_reader_takes_the_programs_own_title_and_drops_the_breadcrumb():
    assert page("ne_ded", "cccff")["title"] == "Civic and Community Center Financing Fund (CCCFF)"   # not a photo caption's `h1`
    assert page("ne_ded", "cdbg")["title"] == "Community Development Block Grant (CDBG)"
    for slug in mod("ne_ded").PAGES:
        assert not text("ne_ded", slug).startswith("Home /"), slug


def test_ded_reader_stops_before_the_resources_news_and_contacts():
    # CCCFF's press-release dates ("Apr 6, 2026") would read as rounds
    t = text("ne_ded", "cccff")
    assert "Apr 6, 2026" not in t and "Press Releases" not in t and "tia.loftin" not in t
    assert "Grant Management Resources" not in text("ne_ded", "cdbg")


def test_cdbg_is_one_record_per_funding_opportunity():
    got = programs("ne_ded", "cdbg")
    assert list(got) == ["cdbg", "cdbg#public-works-infrastructure", "cdbg#planning", "cdbg#tourism-development",
                         "cdbg#public-works-facilities", "cdbg#downtown-revitalization"]
    assert got["cdbg"].name == "CDBG Economic Development"
    assert got["cdbg#public-works-facilities"].name == "CDBG Public Works - Facilities"


def test_cdbg_statuses_a_window_is_open_and_a_deadline_with_no_year_is_not_a_date():
    got = programs("ne_ded", "cdbg")
    assert {sid: p.status for sid, p in got.items()} == {
        "cdbg": "open",                             # "Application Period: July 1, 2026 to June 30, 2027"
        "cdbg#tourism-development": "open",
        "cdbg#public-works-infrastructure": "unknown",   # "Application Deadline: Sept. 15", no year: not guessed
        "cdbg#planning": "unknown",
        "cdbg#public-works-facilities": "unknown",
        "cdbg#downtown-revitalization": "unknown",
    }
    assert got["cdbg"].opens_at == date(2026, 7, 1) and got["cdbg"].closes_at == date(2027, 6, 30)
    for sid in ("cdbg#planning", "cdbg#downtown-revitalization"):
        assert got[sid].closes_at is None
        assert got[sid].closes_at_text == "Application Deadline: Sept. 15"      # kept for the reader, not turned into a date


def test_cdbg_window_closes_when_it_has_passed():
    assert program("ne_ded", "cdbg", date(2027, 7, 1)).status == "unknown"


def test_cdbg_applicants_are_counties_and_municipalities_not_the_entitlement_cities():
    for p in programs("ne_ded", "cdbg").values():
        assert {t.value for t in p.applicant_types} == {"municipality", "county"}
        assert "not designated as a CDBG Entitlement Community" in p.eligibility_text    # the stored text keeps the carve-out


def test_cdbg_is_hud_money_passed_through_the_state():
    assert {p.funding_source for p in programs("ne_ded", "cdbg").values()} == {"pass_through"}
    # RCRP is ARPA money (its page says so); the Trust Fund, CCCFF and SBDF are state money
    assert {s: program("ne_ded", s).funding_source for s in ("rcrp", "nahtf", "cccff", "sbdf")} == {
        "rcrp": "pass_through", "nahtf": "direct", "cccff": "direct", "sbdf": "direct"}


def test_cccff_schedule_is_read_from_its_opens_and_closes_lines():
    p = program("ne_ded", "cccff")
    # "Pre-Application Period Opens: 1/1/2027 8:00 AM (CST) Pre-Application Period Closes: 1/15/2027 6:00 PM (CST)"
    assert (p.status, p.opens_at, p.closes_at) == ("forecasted", date(2027, 1, 1), date(2027, 1, 15))
    assert program("ne_ded", "cccff", date(2027, 1, 5)).status == "open"
    assert program("ne_ded", "cccff", date(2027, 1, 16)).status == "unknown"
    assert tags("ne_ded", "cccff") == {"municipality", "tribe"}
    assert p.funding_source == "direct"


def test_nahtf_takes_its_applicants_from_the_list_under_a_paragraph_label():
    assert tags("ne_ded", "nahtf") == {"municipality", "county", "housing_authority"}
    p = program("ne_ded", "nahtf")
    assert "Local and Governmental Subdivisions" in p.eligibility_text
    # the application dates sit in AmpliFund buttons, not in the page's text
    assert p.status == "unknown" and p.closes_at is None


def test_rcrp_and_sbdf_applicants():
    assert tags("ne_ded", "rcrp") == {"municipality", "county"}
    assert tags("ne_ded", "sbdf") == {"municipality", "county", "nonprofit"}
    assert program("ne_ded", "sbdf").status == "unknown"       # "Deadlines depend on funding availability"


def test_ded_waits_the_crawl_delay_its_robots_ask_for(monkeypatch):
    m = mod("ne_ded")
    assert m.SITE.DELAY_S == 3.0 and hl.HandListConnector.DELAY_S == hl.DELAY_S
    naps: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", naps.append)
    monkeypatch.setattr(hl, "get", lambda c, u: (FIX / "ne_ded" / f"{next(s for s, p in m.PAGES.items() if u == m.BASE + p)}.html").read_text(encoding="utf-8"))
    m.fetch()
    assert naps == [3.0] * (len(m.PAGES) - 1)
    # no URL it reads carries a query string (the robots file disallows `/*?`)
    assert not any("?" in p for p in m.PAGES.values())


def test_ded_fetch_and_fallback(monkeypatch):
    m = mod("ne_ded")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "ne_ded" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == ["cdbg", "cdbg#public-works-infrastructure", "cdbg#planning", "cdbg#tourism-development",
                                              "cdbg#public-works-facilities", "cdbg#downtown-revitalization",
                                              "cccff", "nahtf", "rcrp", "sbdf"]
    assert [r.source_id for r in m.fetch(limit=2)] == ["cdbg", "cdbg#public-works-infrastructure"]
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["cdbg"],)))
    again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
    assert all(again[sid] == prior[sid] for sid in prior if sid.startswith("cdbg"))
    assert m.resolve_missing("cccff") == {"status": "unknown"}


def test_the_shared_phrasings_nebraska_ded_added():
    # "not designated as ..." defines the applicants; its "not" must not drop the line, and the clause is cut before tagging
    line = "Every Nebraska county or incorporated municipality not designated as a CDBG Entitlement Community is eligible to apply."
    assert hl.NEGATION_RE.search(line)
    assert " ".join(hl.clause_cut(line).split()) == "Every Nebraska county or incorporated municipality is eligible to apply."
    assert {t.value for t in hl.applicant_tags([hl.clause_cut(line)])} == {"municipality", "county"}
    # a local government that "are eligible", at the end of the sentence
    assert hl.APPLICANT_SENTENCE_RE.search("Local governments and Nebraska nonprofits are eligible.")
    assert not hl.APPLICANT_SENTENCE_RE.search("Projects in rural areas are eligible.")
    # opens and closes in one line
    assert hl.OPENS_RE.search("Pre-Application Period Opens: 1/1/2027") and hl.OPENS_RE.search("Open Date: 10/27/2025")
    assert hl.DUE_RE.search("Pre-Application Period Closes: 1/15/2027") and hl.DUE_RE.search("Close Date: 6/1/2026")
    assert not hl.DUE_RE.search("The window closes soon")


def test_dates_after_the_deadline_word_win_over_the_opening_date():
    s = ["Pre-Application Period Opens: 1/1/2027 8:00 AM (CST) Pre-Application Period Closes: 1/15/2027 6:00 PM (CST)"]
    assert hl.deadline(s)[1] == date(2027, 1, 15) and hl.opening(s) == date(2027, 1, 1)
    # a deadline word with its date before it still reads ("June 1, 2027 is the deadline")
    assert hl.deadline(["June 1, 2027 is the deadline."])[1] == date(2027, 6, 1)
    # a sentence with an opening word only is unchanged
    assert hl.opening(["Applications open on March 1, 2027."]) == date(2027, 3, 1)


def test_tagger_reads_local_and_governmental_subdivisions():
    assert {t.value for t in hl.applicant_tags(["Local and Governmental Subdivisions"])} == {"municipality", "county"}


@pytest.mark.parametrize("name", AGENCIES)
def test_module_contract(name):
    m = mod(name)
    assert m.CONNECTOR == name and m.AGENCY_CODE.startswith("NE-") and m.CATEGORY_LABEL
    assert callable(m.fetch) and callable(m.normalize) and callable(m.resolve_missing)


def test_a_page_without_a_body_reads_as_no_blocks():
    m = mod("ne_ded")
    assert m.parse_page("<html><h1>Gone</h1></html>") == {"title": "Gone", "blocks": []}
