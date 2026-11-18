"""Arizona State Parks (az_parks) against saved pages, and the tagger rule Arizona added (12.6j)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import az_parks as m
from connectors import hand_list as hl
from connectors.text import applicant_types_for
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "az_parks"
TODAY = date(2026, 11, 17)


def page(slug: str) -> dict:
    return m.parse_page((FIX / f"{slug}.html").read_text(encoding="utf-8"))


def every(today: date = TODAY) -> dict:
    out: dict = {}
    for slug, path in m.PAGES.items():
        for sid, payload in m.SITE.records_for(slug, path, [page(slug)], 0):
            out[sid] = m.normalize(RawRecord(source_connector="az_parks", source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def test_five_records_titled_from_the_page_heading():
    progs = every()
    assert list(progs) == ["lwcf", "competitive-lwcf", "ohv", "rtp", "route-66"]
    assert progs["rtp"].name == "Recreational Trails Program (RTP) Grants"
    assert progs["route-66"].name == "Route 66 Historic Revitalization Grant"   # not its first h2, a question
    assert all(p.jurisdiction == "AZ" for p in progs.values())


def test_the_read_stops_before_the_resources_and_the_faq():
    texts = [t for _, t in page("rtp")["blocks"]]
    assert any(t.startswith("Eligible Applicants:") for t in texts)
    assert not any("Start Here" in t or "Grants Manual" in t or "Have questions" in t for t in texts)
    assert not any("Frequently Asked" in t or "Keeper of the National Register" in t for _, t in page("route-66")["blocks"])


def test_status_no_page_dates_a_round_but_route_66():
    progs = every()
    for sid in ("lwcf", "competitive-lwcf", "ohv", "rtp"):
        assert progs[sid].status == "unknown" and progs[sid].closes_at is None
    # The pre-application deadline governs (the Vermont rule): past on the run date, so unknown with the date kept.
    r66 = progs["route-66"]
    assert (r66.status, r66.closes_at) == ("unknown", date(2026, 11, 6))
    assert "Pre-Application due" in r66.closes_at_text
    assert every(date(2026, 11, 1))["route-66"].status == "open"
    assert "typically in June and closing in October" in progs["competitive-lwcf"].closes_at_text


def test_funding_source_and_applicants():
    progs = every()
    assert {sid: p.funding_source for sid, p in progs.items()} == {
        "lwcf": "pass_through", "competitive-lwcf": "pass_through", "ohv": "direct", "rtp": "pass_through",
        "route-66": "pass_through"}
    assert {"municipality", "county", "tribe"} <= tags(progs["lwcf"])
    assert {"municipality", "county", "nonprofit"} <= tags(progs["ohv"])
    assert {"municipality", "county", "tribe", "nonprofit"} <= tags(progs["rtp"])
    assert {"municipality", "county", "business", "nonprofit", "tribe"} <= tags(progs["route-66"])
    assert all(p.categories and p.categories[0].value == "parks" for p in progs.values())


def test_local_heading_a_list_of_governments_is_local_governments():
    def values(text: str) -> set[str]:
        return {t.value for t in applicant_types_for(text)}

    assert {"municipality", "county"} <= values("Federal, State, Local, County, and Tribal Governments and Non-Profits")
    assert {"municipality", "county"} <= values("local, state, and federal government entities, including tribal governments")
    assert "municipality" not in values("local, domestic, national, and international markets")


def test_fetch_and_fallback(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == list(m.PAGES)
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["rtp"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["rtp"] == prior["rtp"]
