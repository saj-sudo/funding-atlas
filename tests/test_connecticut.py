"""Connecticut's four agency connectors (ct_doh, ct_dot, ct_deep, ct_demhs) and their base, against saved pages."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import connecticut_portal as cp
from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 5)
AGENCIES = ["ct_doh", "ct_dot", "ct_deep", "ct_demhs"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def program(name: str, slug: str, today: date = TODAY):
    m = mod(name)
    page = m.SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))
    return m.normalize(RawRecord(source_connector=name, source_id=slug, payload={"path": m.PAGES[slug], "page": page}), today)


def tags(name: str, slug: str) -> set[str]:
    return {t.value for t in program(name, slug).applicant_types}


def test_every_page_reads_on_its_template():
    for name in AGENCIES:
        for slug in mod(name).PAGES:
            p = program(name, slug)
            page = mod(name).SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))
            assert p.name and p.jurisdiction == "CT" and len(page["blocks"]) >= 2, (name, slug)
            assert p.source_url.startswith("https://portal.ct.gov/")


def test_templates():
    def first(name, slug):
        return cp.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))["blocks"]
    assert any("only available to Connecticut towns and cities" in t for _, t in first("ct_doh", "small-cities"))      # older
    assert any("urbanized area municipal governments" in t for _, t in first("ct_dot", "lotcip"))                     # main column
    assert any("now closed" in t for _, t in first("ct_dot", "ccgp"))                                                # sections only
    assert any("sole eligible entity" in t for _, t in first("ct_demhs", "slcgp"))                                   # tabs
    assert not any("@ct.gov" in t for n in AGENCIES for s in mod(n).PAGES for _, t in first(n, s))


def test_status():
    assert (program("ct_deep", "oswa").status, program("ct_deep", "oswa").closes_at) == ("open", date(2026, 11, 6))
    assert (program("ct_deep", "ugcg").status, program("ct_deep", "ugcg").closes_at) == ("open", date(2026, 12, 4))
    assert program("ct_deep", "oswa", date(2026, 11, 7)).status == "unknown"
    assert program("ct_dot", "ccgp").status == "closed"
    p = program("ct_doh", "small-cities")
    assert (p.status, p.closes_at) == ("unknown", date(2026, 9, 11))      # a past deadline; "Registration is NOW Open" is a course
    for slug in mod("ct_demhs").PAGES:
        assert program("ct_demhs", slug).status == "unknown"


def test_shared_deadline_wordings():
    assert hl.deadline(["Applications must be submitted by November 6, 2026, Appraisals must be submitted by "
                        "December 4, 2026"])[1] == date(2026, 11, 6)
    assert hl.deadline(["*NEW* Through December 4, 2026, the Department is currently accepting applications"])[1] == date(2026, 12, 4)
    assert hl.deadline(["Anticipated Grant Implementation Period: June 1, 2028 through December 31, 2030"]) == (None, None)
    assert hl.deadline(["Projects run through December 31, 2028."]) == (None, None)       # "through" needs "accepting"


def test_applicants():
    assert tags("ct_doh", "small-cities") == {"municipality"}
    assert tags("ct_dot", "lotcip") == {"municipality"}
    assert tags("ct_deep", "oswa") == {"municipality", "nonprofit"}
    assert tags("ct_demhs", "mgp") == {"municipality"}                     # Urban Act and STEAP grants-in-aid to towns
    assert tags("ct_demhs", "hmgp") == {"municipality"}                    # not the homeowners it applies on behalf of
    assert {"municipality", "county", "tribe"} <= tags("ct_demhs", "slcgp")
    assert tags("ct_demhs", "empg") == set() and tags("ct_demhs", "hsgp") == set()   # the State is the applicant


def test_categories_and_funding_source():
    assert program("ct_doh", "small-cities").category_pairs() == [("infrastructure", "community development")]
    assert program("ct_deep", "ugcg").category_pairs() == [("parks", "recreation and conservation")]
    assert program("ct_doh", "small-cities").funding_source == "pass_through"
    assert program("ct_deep", "oswa").funding_source == "direct"


def test_fetch_and_fallback(monkeypatch):
    m = mod("ct_deep")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "ct_deep" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == ["oswa", "ugcg"]
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["oswa"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["oswa"] == prior["oswa"]
    assert m.resolve_missing("oswa") == {"status": "unknown"}


@pytest.mark.parametrize("name", AGENCIES)
def test_module_contract(name):
    m = mod(name)
    assert m.CONNECTOR == name and m.AGENCY_CODE.startswith("CT-") and m.CATEGORY_LABEL
    assert callable(m.fetch) and callable(m.normalize) and callable(m.resolve_missing)
