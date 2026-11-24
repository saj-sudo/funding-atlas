"""Oklahoma Department of Commerce (ok_commerce) against saved pages (12.9)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from connectors import ok_commerce as m
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "ok_commerce"
TODAY = date(2026, 11, 24)
HUB_IDS = ["cdbg", "cdbg#small-cities", "cdbg#community-revitalization", "cdbg#water-wastewater-construction", "cdbg#edif",
           "cdbg#water-wastewater-engineering", "cdbg#reap"]


def page(slug: str) -> dict:
    return m.parse_page((FIX / f"{slug}.html").read_text(encoding="utf-8"))


def every(today: date = TODAY) -> dict:
    out: dict = {}
    for slug, path in m.PAGES.items():
        for sid, payload in m.SITE.records_for(slug, path, [page(slug)], 0):
            out[sid] = m.normalize(RawRecord(source_connector="ok_commerce", source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def test_the_hub_is_seven_records_and_the_fund_one():
    progs = every()
    assert list(progs) == HUB_IDS + ["odmrmf"]
    assert progs["cdbg"].name == "CDBG Capital Improvement Planning (CIP)"          # the first program keeps the page's id
    assert progs["cdbg#edif"].name == "CDBG Economic Development Infrastructure Financing (EDIF)"
    assert progs["cdbg#reap"].name == "CDBG Rural Economic Action Plan (REAP)"
    assert progs["odmrmf"].name == "Oklahoma Disaster Mitigation and Recovery Matching Fund Program (ODMRMF)"
    assert all(p.jurisdiction == "OK" and p.agency_code == "OK-COMMERCE" for p in progs.values())
    assert all(p.source_url == m.BASE + m.PAGES["cdbg"] for sid, p in progs.items() if sid != "odmrmf")
    assert progs["cdbg#small-cities"].summary.startswith("Oklahoma’s Small Cities program helps fund infrastructure")


def test_what_is_not_read():
    hub = " ".join(t for _, t in page("cdbg")["blocks"])
    # the SAM.gov how-to, the trainings, the State Plan hearing notice and its comment period, the resources
    for gone in ("DUNs", "Save the Dates", "Continuing Education", "Public Hearing", "December 18, 2026", "Davis Bacon",
                 "Section 3", "CIP Guidance", "Program Objectives"):
        assert gone not in hub, gone
    assert "Eligibility is generally limited to units of general local government" in hub
    # Coronavirus Relief and the Disaster Recovery entries are on the page and in no record
    assert "Coronavirus Relief" in hub and "Disaster Recovery" in hub
    records = dict(m.SITE.records_for("cdbg", m.PAGES["cdbg"], [page("cdbg")], 0))
    for sid, payload in records.items():
        text = " ".join(t for _, t in payload["page"]["blocks"])
        assert "Coronavirus" not in text and "Disaster Recovery" not in text, sid
    fund = [t for _, t in page("odmrmf")["blocks"]]
    assert "SWODA" in fund and not any("Policies" in t or "Annual Reporting" in t or "Return to top" in t for t in fund)


def test_no_page_states_a_round():
    for today in (TODAY, date(2026, 9, 1)):       # before the hearing's comment period closes too: it is not a round
        for sid, p in every(today).items():
            assert (p.status, p.opens_at, p.closes_at, p.closes_at_text) == ("unknown", None, None, None), sid


def test_funding_source_applicants_and_categories():
    progs = every()
    assert all(progs[sid].funding_source == "pass_through" for sid in HUB_IDS)          # "... from ... (HUD)"
    assert progs["odmrmf"].funding_source == "direct"                                   # "provided by the State Treasury"
    for sid in HUB_IDS:
        assert tags(progs[sid]) == {"municipality", "county"}, sid
        assert "units of general local government such as cities, towns, and counties" in progs[sid].eligibility_text
    assert "may apply under this category" in progs["cdbg#water-wastewater-construction"].eligibility_text
    # the fund's applicants are the planning districts: its purpose sentence ("to help local governments") tags no one
    fund = progs["odmrmf"]
    assert tags(fund) == set()
    assert "Substate Planning Districts (SSPDs) or Councils of Government (COGs)" in fund.eligibility_text
    assert "ACOG" in fund.eligibility_text and "to help local governments" not in fund.eligibility_text
    assert "to help local governments" in fund.summary
    cats = {sid: [c.value for c in p.categories] for sid, p in progs.items()}
    assert cats["cdbg"] == ["infrastructure"] and cats["cdbg#water-wastewater-engineering"] == ["water"]
    assert cats["cdbg#water-wastewater-construction"] == ["water"] and cats["odmrmf"] == ["public_safety"]
    assert all(p.funding_type == "grant" for p in progs.values())


def test_no_contact_is_stored():
    for slug in m.PAGES:
        text = " ".join(t for _, t in page(slug)["blocks"])
        assert "@" not in text and "405-" not in text and "800-" not in text, slug


def test_fetch_and_fallback(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", slept.append)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == HUB_IDS + ["odmrmf"]
    assert slept == [3.0]
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["cdbg"],)))
    again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
    assert list(again) == HUB_IDS + ["odmrmf"] and again["cdbg#reap"] == prior["cdbg#reap"]
    assert [r.source_id for r in m.fetch(prior={})] == ["odmrmf"]
