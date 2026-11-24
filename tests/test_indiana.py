"""Indiana's OCRA (in_ocra) and INDOT (in_indot) against saved pages (milestone 12.9)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from connectors import in_indot, in_ocra
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 24)
CONSTRUCTION = ["cdbg-construction", "cdbg-construction#blight-clearance", "cdbg-construction#stormwater",
                "cdbg-construction#main-street", "cdbg-construction#water"]


def page(m, slug: str) -> dict:
    return m.parse_page((FIX / m.CONNECTOR / f"{slug}.html").read_text(encoding="utf-8"))


def every(m, today: date = TODAY) -> dict:
    out: dict = {}
    for slug, path in m.PAGES.items():
        for sid, payload in m.SITE.records_for(slug, path, [page(m, slug)], 0):
            out[sid] = m.normalize(RawRecord(source_connector=m.CONNECTOR, source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def texts(m, slug: str) -> list[str]:
    return [t for _, t in page(m, slug)["blocks"]]


# ---------- in_ocra ----------

def test_ocra_seven_records_the_construction_page_one_per_tab():
    progs = every(in_ocra)
    assert list(progs) == ["cdbg-planning", *CONSTRUCTION, "stellar"]
    assert progs["cdbg-planning"].name == "CDBG Planning Grants"
    assert [progs[sid].name for sid in CONSTRUCTION] == [
        "CDBG Facilities Program", "CDBG Blight Clearance Program", "CDBG Stormwater Improvements Program",
        "CDBG Main Street Revitalization Program", "CDBG Wastewater/Drinking Water Program"]
    assert progs["stellar"].name == "Stellar Pathways Program"   # its `h1` is the banner's placeholder, "Main Billboard"
    assert all(p.jurisdiction == "IN" and p.agency_code == "IN-OCRA" for p in progs.values())
    assert all(p.source_url == "https://www.in.gov/ocra/cdbg/cdbg-construction-grants" for sid, p in progs.items() if sid in CONSTRUCTION)


def test_ocra_tabs_are_headings_and_each_program_keeps_only_its_own_tab():
    kinds = dict((t, k) for k, t in page(in_ocra, "cdbg-construction")["blocks"])
    assert kinds["Blight Clearance Program"] == "label" and kinds["Wastewater/Drinking Water"] == "label"
    progs = every(in_ocra)
    assert progs["cdbg-construction#blight-clearance"].summary.startswith("The Blight Clearance Program (BCP) offers")
    assert progs["cdbg-construction#water"].summary.startswith("Many communities in Indiana struggle with inadequate water")
    # the planning page's nine tabs stay one record, each plan type under its heading
    assert {"Utility Study Plans", "Comprehensive Plans", "Feasibility Studies"} <= set(texts(in_ocra, "cdbg-planning"))


def test_ocra_where_the_read_stops_and_what_is_dropped():
    planning = texts(in_ocra, "cdbg-planning")
    assert "OCRA" not in planning and "Community Development Block Grants" not in planning   # the breadcrumb
    assert not any("For questions regarding" in t for t in planning)
    stellar = texts(in_ocra, "stellar")
    assert any(t.startswith("The lead applicant can be") for t in stellar)
    assert not any("Designees" in t or "Program Guide" in t or "Investment Statistics" in t for t in stellar)
    assert stellar.count("Enhancing Local Planning") == 1   # a card's paragraph, not read again as its list item
    assert "Main Billboard" not in stellar and "Stellar Pathways Program" not in stellar


def test_ocra_status_a_weekday_and_a_day_is_not_a_date():
    progs = every(in_ocra)
    # "The programs listed below are now accepting applications for the 2026 Round 2."; "due on Sunday, Dec. 13": no year.
    for sid in CONSTRUCTION:
        p = progs[sid]
        assert (p.status, p.closes_at, p.opens_at) == ("open", None, None)
        assert p.closes_at_text.startswith("2026 Round 2 applications are due on Sunday, Dec. 13")
    planning = progs["cdbg-planning"]
    assert (planning.status, planning.closes_at) == ("unknown", None)
    assert planning.closes_at_text.startswith("Applications are due on Sunday, July 12")
    stellar = progs["stellar"]
    assert (stellar.status, stellar.closes_at) == ("unknown", None)
    assert stellar.closes_at_text.startswith("Stellar Pathways workshops will take place on Tuesday, Oct. 27")


def test_ocra_funding_source_applicants_and_categories():
    progs = every(in_ocra)
    assert {sid: p.funding_source for sid, p in progs.items()} == {
        "cdbg-planning": "pass_through", **{sid: "pass_through" for sid in CONSTRUCTION}, "stellar": "direct"}
    for sid in ["cdbg-planning", *CONSTRUCTION]:
        assert tags(progs[sid]) == {"municipality", "county"}
    # the planning page names no applicant: the CDBG hub's sentences, quoted by hand, dated and attributed
    assert progs["cdbg-planning"].eligibility_text.startswith("OCRA's CDBG page (https://www.in.gov/ocra/cdbg/index), read 2026-11-24: ")
    assert "units of local government" in progs["cdbg-construction#stormwater"].eligibility_text
    assert tags(progs["stellar"]) == {"municipality", "county", "nonprofit"}
    assert progs["stellar"].eligibility_text.startswith("The lead applicant can be any county government, city, municipality, town")
    assert {sid: p.categories[0].value for sid, p in progs.items()} == {
        "cdbg-planning": "infrastructure", "cdbg-construction": "infrastructure",
        "cdbg-construction#blight-clearance": "infrastructure", "cdbg-construction#stormwater": "water",
        "cdbg-construction#main-street": "infrastructure", "cdbg-construction#water": "water", "stellar": "infrastructure"}
    assert all(p.funding_type == "grant" for p in progs.values())


# ---------- in_indot ----------

def test_indot_one_record_read_down_to_the_accordion():
    progs = every(in_indot)
    assert list(progs) == ["community-crossings"]
    p = progs["community-crossings"]
    assert (p.name, p.jurisdiction, p.agency_code) == ("Community Crossings Matching Grant Program", "IN", "IN-INDOT")
    lines = texts(in_indot, "community-crossings")
    assert "Cities and towns with populations less than 12,500: 80/20 match" in lines
    assert "INDOT" not in lines and "Local Public Agency Programs" not in lines   # the breadcrumb
    assert not any("Frequently Asked" in t or "Asset Management Plan" in t or "Title VI" in t or "October 31, 2025" in t for t in lines)


def test_indot_status_source_and_applicants():
    p = every(in_indot)["community-crossings"]
    # "awards were announced on Wednesday, October 28, 2026" is not a deadline; the next call is "each September": no date.
    assert (p.status, p.closes_at, p.opens_at) == ("unknown", None, None)
    assert p.closes_at_text == ("Moving forward, INDOT plans to issue the Community Crossings Matching Grant call each "
                                "September on an annual basis.")
    assert p.funding_source == "direct" and p.funding_type == "grant"
    assert tags(p) == {"municipality", "county"}
    assert p.categories[0].value == "transportation"


def test_no_contact_is_read_from_either_agency():
    for m in (in_ocra, in_indot):
        for slug in m.PAGES:
            assert not any("@" in t or "317-" in t for t in texts(m, slug))


def test_fetch_and_fallback(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", slept.append)
    for m in (in_ocra, in_indot):
        def site(client, url, broken=(), m=m):
            if url in broken:
                raise httpx.ConnectError("down")
            slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
            return (FIX / m.CONNECTOR / f"{slug}.html").read_text(encoding="utf-8")

        monkeypatch.setattr(hl, "get", site)
        records = m.fetch()
        assert {r.source_id.split("#")[0] for r in records} == set(m.PAGES)
        prior = {r.source_id: r.payload for r in records}
        first = next(iter(m.PAGES))
        monkeypatch.setattr(hl, "get", lambda c, u, site=site, m=m, first=first: site(c, u, broken=(m.BASE + m.PAGES[first],)))
        again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
        assert again == prior
        # a page that cannot be read and was never stored is skipped (OCRA's planning page: six records are left)
        assert len(m.fetch()) == len(records) - 1
    assert slept and set(slept) == {3.0}
