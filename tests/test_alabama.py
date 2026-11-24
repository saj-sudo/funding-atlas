"""Alabama's agency connectors (al_adem, al_dot) against saved pages (12.9). ADECA is not read: no fixture, no module."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 24)
AGENCIES = ["al_adem", "al_dot"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def page(name: str, slug: str) -> dict:
    return mod(name).SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))


def every(name: str, today: date = TODAY) -> dict:
    m = mod(name)
    out: dict = {}
    for slug, path in m.PAGES.items():
        for sid, payload in m.SITE.records_for(slug, path, [page(name, slug)], 0):
            out[sid] = m.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def texts(name: str, slug: str) -> list[str]:
    return [t for _, t in page(name, slug)["blocks"]]


def test_seven_records_named_from_the_pages():
    adem, dot = every("al_adem"), every("al_dot")
    assert {s: p.name for s, p in adem.items()} == {
        "srf": "State Revolving Fund (SRF)",
        "recycling": "Alabama Recycling Fund Grants",   # the grant section's own name, not the page's "Recycling Program"
        "319": "NPS Section 319(h) Grant",
    }
    assert {s: p.name for s, p in dot.items()} == {
        "tap": "Transportation Alternatives Program (TAP)",
        "atrip-ii": "Alabama Transportation Rehabilitation & Improvement Program II",
        "raa-annual-grant": "Rebuild Alabama Act Annual Grant Program",
        "industrial-access": "Industrial Access Program",
    }
    for name, got in (("al_adem", adem), ("al_dot", dot)):
        for p in got.values():
            assert p.jurisdiction == "AL" and p.level == "state" and p.source_url.startswith(mod(name).BASE)
    assert adem["srf"].agency_code == "AL-ADEM" and dot["tap"].agency_code == "AL-DOT"
    assert not any("adeca" in p.source_url for p in [*adem.values(), *dot.values()])


def test_adem_where_the_read_stops_and_what_is_dropped():
    srf = " ".join(texts("al_adem", "srf"))
    assert "may apply for SRF financing" in srf and "Project Priority List" in srf
    assert not any(w in srf for w in ("Needs Survey", "Intended Use Plan 2025", "Form 340", "srf@", "271-7714"))
    n319 = " ".join(texts("al_adem", "319"))
    assert "Priority Deadline is July 1st" in n319 and "Quick Guide" not in n319 and "303(d) List" not in n319


def test_adem_recycling_is_the_grant_section_only():
    blocks = dict(mod("al_adem").SITE.records_for("recycling", "/waste/recycling-program", [page("al_adem", "recycling")], 0))
    text = " ".join(t for _, t in blocks["recycling"]["page"]["blocks"])
    assert list(blocks) == ["recycling"]
    assert "reimbursement grants to local governments" in text and "March 1st of each year" in text
    assert "Grant Application deadline" in text                      # the announcement above the sections stays
    assert not any(w in text for w in ("Materials Recovery Facility", "annual report", "Statewide Solid Waste Reduction Goal",
                                       "334-274-4201", "Helpful Links", "A Plan for Boosting"))


def test_adem_status_dates_and_fields():
    got = every("al_adem")
    assert (got["srf"].status, got["srf"].closes_at, got["srf"].closes_at_text) == ("unknown", None, None)
    # a dated deadline that has passed: unknown, the date kept
    assert (got["recycling"].status, got["recycling"].closes_at) == ("unknown", date(2026, 3, 2))
    assert got["recycling"].closes_at_text.startswith("March 2nd, 2026: Grant Application deadline")
    assert every("al_adem", date(2026, 2, 1))["recycling"].status == "open"
    # a month and a day with no year is not a date; the line is kept
    assert (got["319"].status, got["319"].closes_at) == ("unknown", None)
    assert "Priority Deadline is July 1st" in got["319"].closes_at_text
    assert {s: (p.funding_type, p.funding_source) for s, p in got.items()} == {
        "srf": ("loan", "pass_through"), "recycling": ("grant", "direct"), "319": ("grant", "pass_through")}
    assert [c.value for c in got["srf"].categories] == ["water"] and [c.value for c in got["recycling"].categories] == ["other"]
    assert {"municipality", "county", "state"} <= tags(got["srf"])
    assert {"municipality", "county", "nonprofit"} <= tags(got["recycling"])
    assert {"municipality", "county", "nonprofit", "state", "higher_ed"} <= tags(got["319"])
    assert got["srf"].eligibility_text.startswith("Any public body, including counties")
    assert "Local governments – any municipality, county" in got["recycling"].eligibility_text
    assert got["srf"].summary.startswith("The Clean Water State Revolving Fund (CWSRF)")


def test_dot_pages_lead_in_contacts_and_awards():
    tap = texts("al_dot", "tap")
    assert tap[0].startswith("MAP-21 established")                  # "What is the Transportation Alternatives program?" removed
    assert "FY 2027 TAP Guidelines" in tap
    for slug in mod("al_dot").PAGES:
        joined = " ".join(texts("al_dot", slug))
        assert not any(w in joined for w in ("For questions", "334", "Awarded Projects", "SELECTED PROJECTS", "ALDOT News"))
    assert texts("al_dot", "atrip-ii") == ["FY 2027 ATRIP-II Application", "FY 2027 ATRIP-II Procedural Guidelines", "FY 2027 ATRIP-II FAQ's"]


def test_dot_status_and_the_industrial_access_table():
    got = every("al_dot")
    for sid in ("tap", "atrip-ii", "raa-annual-grant"):
        assert (got[sid].status, got[sid].closes_at, got[sid].closes_at_text) == ("unknown", None, None)
    ia = got["industrial-access"]
    assert (ia.status, ia.closes_at, ia.opens_at) == ("open", date(2027, 1, 8), None)     # the first deadline still ahead
    assert ia.closes_at_text.startswith("Application deadlines are: Friday, January 9, 2026; Friday, April 3, 2026")
    assert "March 10, 2026" not in ia.closes_at_text                                       # meeting dates are another line
    assert every("al_dot", date(2026, 3, 1))["industrial-access"].closes_at == date(2026, 4, 3)
    assert every("al_dot", date(2027, 8, 6))["industrial-access"].closes_at == date(2027, 8, 6)
    past = every("al_dot", date(2030, 1, 1))["industrial-access"]                          # every row passed: unknown, the last kept
    assert (past.status, past.closes_at) == ("unknown", date(2029, 8, 3))


def test_dot_funding_source_and_applicants():
    got = every("al_dot")
    assert {s: p.funding_source for s, p in got.items()} == {
        "tap": "pass_through", "atrip-ii": "direct", "raa-annual-grant": "direct", "industrial-access": "direct"}
    assert tags(got["tap"]) == {"municipality", "county"}
    assert got["tap"].eligibility_text == ("This program is application based for cities, towns, county commissions and "
                                           "metropolitan planning organizations.")
    assert tags(got["industrial-access"]) == {"municipality", "county"}
    assert got["industrial-access"].eligibility_text.startswith("The project sponsor (city or county)")
    # a page that names no applicant gives none
    for sid in ("atrip-ii", "raa-annual-grant"):
        assert got[sid].eligibility_text is None and not got[sid].applicant_types
    assert got["atrip-ii"].summary is None
    assert all(p.categories[0].value == "transportation" and p.funding_type == "grant" for p in got.values())


@pytest.mark.parametrize("name", AGENCIES)
def test_fetch_and_fallback(monkeypatch, name):
    m = mod(name)
    sleeps: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", sleeps.append)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / name / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == list(m.PAGES)
    assert sleeps == [3.0] * (len(m.PAGES) - 1)
    prior = {r.source_id: r.payload for r in records}
    last = list(m.PAGES)[-1]
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES[last],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}[last] == prior[last]
    assert [r.source_id for r in m.fetch()] == list(m.PAGES)[:-1]          # nothing stored: the page is skipped
