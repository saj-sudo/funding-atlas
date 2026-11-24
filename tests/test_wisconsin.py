"""Wisconsin DOA's State CDBG programs (wi_doa) against saved pages (12.9)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from connectors import wi_doa as m
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "wi_doa"
TODAY = date(2026, 11, 24)


def page(slug: str) -> dict:
    return m.parse_page((FIX / f"{slug}.html").read_text(encoding="utf-8"))


def every(today: date = TODAY) -> dict:
    out: dict = {}
    for slug, path in m.PAGES.items():
        for sid, payload in m.SITE.records_for(slug, path, [page(slug)], 0):
            out[sid] = m.normalize(RawRecord(source_connector="wi_doa", source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def texts(slug: str) -> list[str]:
    return [t for _, t in page(slug)["blocks"]]


def test_six_records_titled_from_the_page_heading():
    progs = every()
    assert list(progs) == ["public-facilities", "planning", "public-facilities-economic-development", "economic-development",
                           "emergency-assistance", "affordable-housing-conversion"]
    assert progs["public-facilities"].name == "CDBG - Public Facilities Program (PF)"
    assert progs["affordable-housing-conversion"].name == "Affordable Housing Conversion Program"
    for sid, p in progs.items():
        assert p.jurisdiction == "WI" and p.agency_code == "WI-DOA", sid
        assert p.source_url.startswith("https://energyandhousing.wi.gov/Pages/AgencyResources/"), sid
        assert p.funding_source == "pass_through" and p.categories[0].value == "infrastructure", sid


def test_sharepoint_text_is_folded_and_the_read_stops_at_the_contact_block():
    for slug in m.PAGES:
        lines = texts(slug)
        assert lines, slug
        assert not any("​" in t for t in lines), slug
        assert not any("@" in t or "PO Box" in t or "(608)" in t or "Mailing Address" in t for t in lines), slug
        assert not any(t.lower().startswith("contact") for t in lines), slug
    pf = texts("public-facilities")
    assert pf[0] == "Program Overview"   # no zero-width spaces before it
    assert not any(t.endswith("(PDF)") or t.endswith("(Word)") for t in pf)   # document links
    # words the editor split across spans are whole
    assert any(t.startswith("For each Grant Application received") for t in texts("economic-development"))
    # a list item that wraps a paragraph is read once
    eap = texts("emergency-assistance")
    assert eap.count("Acquisition and demolition of dwellings unable to be repaired.") == 1


def test_status_what_each_page_says():
    progs = every()
    pf = progs["public-facilities"]
    assert (pf.status, pf.closes_at, pf.closes_at_text) == ("unknown", None, "Typically applications are due in mid-May each year.")
    plng = progs["planning"]
    assert (plng.status, plng.rolling, plng.closes_at_text) == ("open", True, "Applications are accepted on a continuous basis.")
    for sid in ("public-facilities-economic-development", "economic-development"):
        assert (progs[sid].status, progs[sid].rolling, progs[sid].closes_at) == ("open", True, None), sid
        assert "may be submitted at any time" in progs[sid].closes_at_text
    eap = progs["emergency-assistance"]
    assert (eap.status, eap.rolling, eap.closes_at) == ("unknown", None, None)
    assert "within 90 days of the disaster event" in eap.closes_at_text


def test_affordable_housing_conversion_is_forecasted_until_the_application_is_available():
    ahc = every()["affordable-housing-conversion"]
    assert (ahc.status, ahc.opens_at, ahc.closes_at) == ("forecasted", date(2027, 1, 18), date(2027, 5, 15))
    assert ahc.closes_at_text == "Applications Due May 15, 2027"
    assert every(date(2027, 2, 1))["affordable-housing-conversion"].status == "open"
    late = every(date(2027, 6, 1))["affordable-housing-conversion"]
    assert (late.status, late.closes_at) == ("unknown", date(2027, 5, 15))


def test_applicants():
    progs = every()
    for sid, p in progs.items():
        assert tags(p) == {"municipality", "county"}, sid   # never the business or the residents a grant benefits
    assert progs["public-facilities"].eligibility_text.startswith("Grants are awarded to units of general local government")
    assert "to assist businesses to create or retain jobs" in progs["economic-development"].eligibility_text
    assert "business assistance needs" in progs["emergency-assistance"].eligibility_text
    # the Planning page names no applicant: the hub's sentence, quoted by hand, dated and attributed
    plng = progs["planning"].eligibility_text
    assert plng.startswith("DEHCR Community Resources page (/Pages/CommunityResources.aspx), read 2026-11-24: Planning Program")
    assert "provides grant funds to local governments" in plng


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
    assert len(m.fetch(limit=2)) == 2
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["planning"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["planning"] == prior["planning"]
    assert "planning" not in [r.source_id for r in m.fetch()]
