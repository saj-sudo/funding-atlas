"""Louisiana's Office of Community Development (la_ocd) against saved pages (12.9)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from connectors import la_ocd as m
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "la_ocd"
TODAY = date(2026, 11, 24)


def page(slug: str) -> dict:
    return m.parse_page((FIX / f"{slug}.html").read_text(encoding="utf-8"))


def every(today: date = TODAY) -> dict:
    out: dict = {}
    for slug, path in m.PAGES.items():
        for sid, payload in m.SITE.records_for(slug, path, [page(slug)], 0):
            out[sid] = m.normalize(RawRecord(source_connector="la_ocd", source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def test_six_records_the_cdbg_page_as_four():
    progs = every()
    assert list(progs) == ["lgap", "cwef", "cdbg", "cdbg#clearance", "cdbg#economic-development", "cdbg#make-a-difference"]
    assert progs["lgap"].name == "Local Government Assistance Program"
    assert progs["cdbg#clearance"].name == "Community Development Block Grant (CDBG): Clearance Program"
    assert all(p.jurisdiction == "LA" and p.administering_agency == m.AGENCY for p in progs.values())


def test_the_read_stops_at_resources_and_cdbg_cv_makes_no_record():
    assert not any(t in ("Resources", "Archived Resources") for _, t in page("lgap")["blocks"])
    progs = every()
    assert not any("CDBG-CV" in (p.summary or "") or "HVAC" in (p.summary or "") for p in progs.values())
    assert not any("cv" in sid for sid in progs)


def test_the_application_window_with_a_comma_after_the_year():
    progs = every()
    for sid in ("lgap", "cwef"):
        p = progs[sid]
        assert (p.status, p.opens_at, p.closes_at) == ("open", date(2026, 11, 2), date(2027, 2, 26))
        assert "November 2, 2026, through February 26, 2027" in p.closes_at_text
    assert every(date(2026, 10, 1))["lgap"].status == "forecasted"
    after = every(date(2027, 3, 1))["cwef"]
    assert (after.status, after.closes_at) == ("unknown", date(2027, 2, 26))   # past: unknown, the date kept
    assert all(progs[sid].status == "unknown" and progs[sid].closes_at is None for sid in progs if sid.startswith("cdbg"))


def test_funding_source_categories_and_applicants():
    progs = every()
    assert {sid: p.funding_source for sid, p in progs.items()} == {
        "lgap": "direct", "cwef": "direct", "cdbg": "pass_through", "cdbg#clearance": "pass_through",
        "cdbg#economic-development": "pass_through", "cdbg#make-a-difference": "pass_through"}
    assert progs["cwef"].categories[0].value == "water" and progs["lgap"].categories[0].value == "infrastructure"
    assert all({"municipality", "county"} <= tags(p) for p in progs.values())
    # "infrastructure improvements that assist for-profit businesses" names who a project serves
    assert "business" not in tags(progs["cdbg#economic-development"])
    assert "partners with local governments" in progs["cdbg"].eligibility_text
    assert "non-entitlement communities are eligible to apply" in progs["lgap"].eligibility_text


def test_fetch_and_fallback(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == ["lgap", "cwef", "cdbg", "cdbg#clearance", "cdbg#economic-development",
                                              "cdbg#make-a-difference"]
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["cwef"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["cwef"] == prior["cwef"]
