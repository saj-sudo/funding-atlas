"""South Dakota's agency connectors (sd_goed, sd_dot, sd_danr) against saved pages, and the shared rules South Dakota added."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 14)
AGENCIES = ["sd_goed", "sd_dot", "sd_danr"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def page(name: str, slug: str) -> dict:
    return mod(name).SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))


def programs(name: str, slug: str, today: date = TODAY) -> dict:
    m = mod(name)
    records = m.SITE.records_for(slug, m.PAGES[slug], [page(name, slug)], 0)
    return {sid: m.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today) for sid, payload in records}


def every(name: str, today: date = TODAY) -> dict:
    out: dict = {}
    for slug in mod(name).PAGES:
        out.update(programs(name, slug, today))
    return out


def tags(name: str, sid: str) -> set[str]:
    return {t.value for t in every(name)[sid].applicant_types}


def text(name: str, slug: str) -> str:
    return " ".join(t for _, t in page(name, slug)["blocks"])


def test_every_page_reads_into_ten_records():
    total = 0
    for name in AGENCIES:
        m = mod(name)
        for slug in m.PAGES:
            assert page(name, slug)["blocks"], (name, slug)
        got = every(name)
        for sid, p in got.items():
            assert p.name and p.jurisdiction == "SD" and p.source_url.startswith(m.BASE), (name, sid)
        total += len(got)
    assert total == 10


def test_goed():
    got = every("sd_goed")
    assert {s: (p.name, p.status) for s, p in got.items()} == {
        "cdbg": ("Community Development Block Grants", "unknown"),
        "liip": ("Local Infrastructure Improvement", "unknown"),
    }
    # a month and a day with no year: not a date, the sentence kept
    assert got["cdbg"].closes_at is None and got["cdbg"].closes_at_text == "Deadlines are April 1 and October 1."
    assert got["liip"].closes_at_text == "January 31 for consideration at the March board meeting"
    assert got["cdbg"].funding_source == "pass_through" and got["liip"].funding_source == "direct"
    assert tags("sd_goed", "cdbg") == {"municipality", "county"}          # "Local governments interested in funding ..."
    assert tags("sd_goed", "liip") == {"municipality", "county"}
    # the CAPER notice's comment dates are not read; the tabs printed twice are read once; the forms tab is not read
    cdbg = text("sd_goed", "cdbg")
    assert "CAPER" not in cdbg and "August 3, 2026" not in cdbg and "Regular CDBG Application" not in cdbg
    liip = [t for _, t in page("sd_goed", "liip")["blocks"]]
    assert len(liip) == len(set(liip))


def test_dot():
    got = every("sd_dot")
    assert list(got) == ["bridge-improvement", "economic-development", "economic-development#agri-business",
                         "economic-development#community-access", "ta"]
    big = got["bridge-improvement"]
    assert (big.status, big.closes_at) == ("open", date(2027, 1, 2))            # "deadline: Saturday, Jan. 2, 2027"
    assert big.summary is None or not big.summary.startswith("Notable changes")
    assert got["ta"].status == "unknown" and got["ta"].closes_at == date(2026, 10, 1)
    assert got["ta"].funding_source == "pass_through"
    assert {got[s].name for s in got if s.startswith("economic")} == {"Industrial Park Road Grants", "Agri-Business Road Grants", "Community Access Grants"}
    assert got["economic-development"].closes_at_text == "Applications are due April 15, July 15, or October 15."
    assert got["economic-development#community-access"].closes_at_text == "Applications are due July 15."
    assert {got[s].status for s in got if s.startswith("economic")} == {"unknown"}
    # each program's own paragraph only: the Agri-Business sentence is not in the Industrial Park record
    ip = " ".join(t for _, t in mod("sd_dot").SITE.records_for("economic-development", mod("sd_dot").PAGES["economic-development"],
                                                              [page("sd_dot", "economic-development")], 0)[0][1]["page"]["blocks"])
    assert "Agri-Business grants" not in ip
    assert tags("sd_dot", "bridge-improvement") == {"county"}               # "to be eligible for a BIG grant, a county must"
    assert tags("sd_dot", "economic-development") == {"municipality", "county"}
    assert tags("sd_dot", "economic-development#agri-business") == {"municipality", "county"}   # not "business": the purpose
    assert tags("sd_dot", "economic-development#community-access") == {"municipality"}         # not "schools": the purpose
    assert tags("sd_dot", "ta") == set()                                    # the page names no applicant


def test_danr():
    got = every("sd_danr")
    assert [p.name for p in got.values()] == ["Drinking Water Project Funding", "Sanitary and Storm Sewer Project Funding",
                                             "Solid Waste Disposal and Recycling Project Funding"]
    for sid, p in got.items():
        assert p.status == "unknown" and p.closes_at is None and p.funding_type == "loan", sid
        assert "on or before the first day of January" in p.closes_at_text, sid      # the application's, not the plan's
    assert tags("sd_danr", "drinking-water") == {"special_district", "state", "municipality", "county", "tribe", "nonprofit"}
    assert tags("sd_danr", "solid-waste") == {"individual", "county", "municipality", "tribe", "special_district"}
    assert [c.value for c in got["drinking-water"].categories] == ["water"]


def test_fetch_and_fallback(monkeypatch):
    m = mod("sd_danr")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "sd_danr" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == list(m.PAGES)
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["solid-waste"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["solid-waste"] == prior["solid-waste"]


def test_the_shared_rules_south_dakota_added():
    for s in ("The Industrial Park grants will be made to any local unit of government for new industry.",
              "Local governments interested in funding through this program should work with their planning district.",
              "Community Access Grants are state funds for towns less than 5,000 in population.",
              "SB 1 states that in order to be eligible for a BIG grant, a county must impose a wheel tax.",
              "Be sponsored by one of the following entities: a special purpose district; a municipality, county, or township."):
        assert hl.APPLICANT_SENTENCE_RE.search(s), s
    assert not hl.APPLICANT_SENTENCE_RE.search("Funds for the project are limited.")
    assert hl.clause_cut("grants to any local unit of government for the development of new agri-business industries") == \
        "grants to any local unit of government "
    # the yearless hook is off unless an agency sets it
    assert hl.AgencyPageConnector.YEARLESS_RE is None
