"""Florida's two connectors against saved pages (12.9): the Department of State's grant table (fl_dos) and the Department
of Environmental Protection's program pages (fl_dep)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import fl_dep, fl_dos
from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 24)
TABLE = (FIX / "fl_dos" / "program.html").read_text(encoding="utf-8")


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


# ---------- fl_dos ----------

def dos(today: date = TODAY) -> dict:
    return {fl_dos.slug(r["name"]): fl_dos.normalize(RawRecord(source_connector="fl_dos", source_id=fl_dos.slug(r["name"]), payload=r), today)
            for r in fl_dos.parse_rows(TABLE) if fl_dos.kept(r)}


def test_dos_reads_every_row_and_keeps_nine():
    rows = fl_dos.parse_rows(TABLE)
    assert len(rows) == 20   # 19 table rows, GPS/SCP as two
    assert {r["division"] for r in rows} == {"", "Arts and Culture", "Elections", "Historical Resources", "Library and Information Services"}
    assert list(dos()) == [
        "cultural-facilities", "general-program-support-gps", "specific-cultural-project-scp",
        "post-election-voting-system-audit", "abandoned-african-american-cemeteries", "small-matching", "special-category",
        "library-services-and-technology-act", "public-library-construction"]


def test_dos_leaves_out_what_the_site_calls_over_and_the_named_rows():
    out = {r["name"] for r in fl_dos.parse_rows(TABLE) if not fl_dos.kept(r)}
    assert {"America 250", "Fast Track Project", "Florida ARP", "Florida CARES", "African-American Cultural and Historical Grant"} <= out
    assert fl_dos.OUT <= out and len(out) == 5 + len(fl_dos.OUT)


def test_dos_a_row_with_two_bold_names_is_two_programs():
    progs = dos()
    gps, scp = progs["general-program-support-gps"], progs["specific-cultural-project-scp"]
    assert (gps.name, scp.name) == ("General Program Support (GPS)", "Specific Cultural Project (SCP)")
    assert gps.summary.startswith("The General Program Support (GPS) grant is designed to fund up to $150,000")
    assert "Specific Cultural Project" not in gps.summary and "More information" not in gps.summary
    assert gps.eligibility_structured["more_information"].endswith("/general-program-support/")
    assert scp.eligibility_structured["more_information"].endswith("/specific-cultural-projects/")
    assert gps.closes_at == scp.closes_at == date(2026, 7, 10)


def test_dos_status_is_the_application_period_against_the_run_date():
    progs = dos()
    # every period has passed on the run date: unknown, the dates kept
    assert all(p.status == "unknown" and p.closes_at and p.opens_at for p in progs.values())
    lib = progs["public-library-construction"]
    assert (lib.opens_at, lib.closes_at, lib.closes_at_text) == (date(2026, 6, 1), date(2026, 7, 10), "Application Period: 6/1/2026 - 7/10/2026")
    assert dos(date(2026, 5, 1))["public-library-construction"].status == "forecasted"
    assert dos(date(2026, 6, 1))["public-library-construction"].status == "open"
    assert dos(date(2026, 7, 10))["public-library-construction"].status == "open"
    assert dos(date(2026, 7, 11))["public-library-construction"].status == "unknown"
    assert progs["post-election-voting-system-audit"].closes_at == date(2026, 8, 5)
    assert fl_dos.status_fields("", TODAY) == {"status": "unknown", "opens_at": None, "closes_at": None, "closes_at_text": None}


def test_dos_funding_source_applicants_and_agency():
    progs = dos()
    assert {sid for sid, p in progs.items() if p.funding_source == "pass_through"} == {"library-services-and-technology-act"}
    assert tags(progs["public-library-construction"]) == {"municipality", "county"}
    assert progs["public-library-construction"].eligibility_text == "Eligible applicants are municipal and county governments."
    assert tags(progs["library-services-and-technology-act"]) == {"nonprofit"}   # not "household" from "Florida residents"
    # "Applicants must be associated with an Organization" names no applicant
    assert progs["cultural-facilities"].eligibility_text is None and not tags(progs["cultural-facilities"])
    assert all((p.jurisdiction, p.administering_agency, p.agency_code, p.source_url) ==
               ("FL", "Florida Department of State", "FL-DOS", "https://www.dosgrants.com/Program") for p in progs.values())
    assert progs["small-matching"].eligibility_structured["division"] == "Historical Resources"


def test_dos_fetch_limit_and_fallback(monkeypatch):
    monkeypatch.setattr(hl, "get", lambda c, u: TABLE if u == fl_dos.LIST_URL else (_ for _ in ()).throw(AssertionError(u)))
    records = fl_dos.fetch()
    assert [r.source_id for r in records] == list(dos())
    assert len(fl_dos.fetch(limit=3)) == 3
    prior = {r.source_id: r.payload for r in records}

    def down(client, url):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(hl, "get", down)
    assert {r.source_id: r.payload for r in fl_dos.fetch(prior=prior)} == prior
    assert fl_dos.fetch() == []
    assert fl_dos.resolve_missing("small-matching") == {"status": "unknown"}


# ---------- fl_dep ----------

def page(slug: str) -> dict:
    return fl_dep.parse_page((FIX / "fl_dep" / f"{slug}.html").read_text(encoding="utf-8"))


def dep(today: date = TODAY) -> dict:
    out: dict = {}
    for slug, path in fl_dep.PAGES.items():
        for sid, payload in fl_dep.SITE.records_for(slug, path, [page(slug)], 0):
            out[sid] = fl_dep.normalize(RawRecord(source_connector="fl_dep", source_id=sid, payload=payload), today)
    return out


def test_dep_seven_records_named_from_the_page_or_the_names_table():
    progs = dep()
    assert list(progs) == ["frdap", "lwcf", "rtp", "fct-parks", "srf", "srf#drinking-water", "water-quality"]
    assert progs["frdap"].name == "Florida Recreation Development Assistance Program"
    # the two cycle pages are titled "LWCF: Application Process, ..."
    assert (progs["lwcf"].name, progs["rtp"].name) == ("Land and Water Conservation Fund Program", "Recreational Trails Program")
    assert (progs["srf"].name, progs["srf#drinking-water"].name) == ("Clean Water State Revolving Fund", "Drinking Water State Revolving Fund")
    assert all(p.jurisdiction == "FL" and p.agency_code == "FL-DEP" for p in progs.values())
    assert progs["srf#drinking-water"].source_url == "https://floridadep.gov/wra/srf"


def test_dep_the_read_stops_before_materials_lists_and_contacts():
    for slug in fl_dep.PAGES:
        texts = [t for _, t in page(slug)["blocks"]]
        assert texts, slug
        assert not any("Priority List" in t or "Webinar Presentation" in t or "Annual Report" in t for t in texts), slug
        assert not any("@" in t or "Contact us" in t or "Tallahassee" in t for t in texts), slug
    assert not any("dashboard" in t.lower() for _, t in page("water-quality")["blocks"])
    assert not any("SRF Management Program" in t for p in (dep()["srf"], dep()["srf#drinking-water"]) for t in [p.summary + (p.eligibility_text or "")])


def test_dep_status_is_the_pages_own_word():
    progs = dep()
    # "The 2027-2028 FRDAP Application Cycle Closed Oct. 15, 2026"
    frdap = progs["frdap"]
    assert (frdap.status, frdap.closes_at) == ("closed", date(2026, 10, 15)) and "Cycle Closed" in frdap.closes_at_text
    # a window under "Submission Cycle", the year printed once; past, and the page does not call it closed
    lwcf = progs["lwcf"]
    assert (lwcf.status, lwcf.opens_at, lwcf.closes_at) == ("unknown", date(2025, 11, 15), date(2025, 12, 15))
    assert dep(date(2025, 12, 1))["lwcf"].status == "open" and dep(date(2025, 11, 1))["lwcf"].status == "forecasted"
    # "FY2025-2026 RTP Grant Submission Cycle (Closed)" over "April 13, 2026-May 28, 2026"
    rtp = progs["rtp"]
    assert (rtp.status, rtp.opens_at, rtp.closes_at) == ("closed", date(2026, 4, 13), date(2026, 5, 28))
    assert rtp.closes_at_text.startswith("FY2025-2026 RTP Grant Submission Cycle (Closed)")
    assert dep(date(2026, 5, 1))["rtp"].status == "open"
    # "Grant Submission Cycle: TBD"
    fct = progs["fct-parks"]
    assert (fct.status, fct.closes_at, fct.closes_at_text) == ("unknown", None, "2026-27 Grant Submission Cycle and Webinar: TBD")
    # "a Request for Inclusion form, which can be submitted any time during the year"
    for sid in ("srf", "srf#drinking-water"):
        assert (progs[sid].status, progs[sid].rolling, progs[sid].closes_at) == ("open", True, None)
        assert "any time during the year" in progs[sid].closes_at_text
    wq = progs["water-quality"]
    assert (wq.status, wq.closes_at, wq.closes_at_text) == ("unknown", None, None)


def test_dep_a_year_printed_once_crossing_new_year():
    blocks = [("label", "FY2026-2027 Submission Cycle"), ("p", "November 15 - January 15, 2027")]
    assert fl_dep.cycle_window(blocks) == ("November 15 - January 15, 2027", date(2026, 11, 15), date(2027, 1, 15))
    assert fl_dep.cycle_window([("label", "Grant Term"), ("p", "July 1 - June 30, 2027")]) is None


def test_dep_funding_type_source_match_and_applicants():
    progs = dep()
    assert {sid: p.funding_source for sid, p in progs.items()} == {
        "frdap": "direct", "lwcf": "pass_through", "rtp": "pass_through", "fct-parks": "direct", "srf": "pass_through",
        "srf#drinking-water": "pass_through", "water-quality": "direct"}
    assert {sid for sid, p in progs.items() if p.funding_type == "loan"} == {"srf", "srf#drinking-water"}
    assert {sid for sid, p in progs.items() if p.match_required} == {"lwcf", "rtp", "fct-parks"}
    assert tags(progs["frdap"]) == {"municipality", "county", "special_district"}
    assert tags(progs["lwcf"]) == {"municipality", "county"}
    assert {"municipality", "county", "nonprofit", "tribe"} <= tags(progs["rtp"])
    assert {"municipality", "county", "nonprofit"} <= tags(progs["fct-parks"])
    assert {"municipality", "county", "special_district"} <= tags(progs["srf"])
    assert "private utilities" in progs["srf#drinking-water"].eligibility_text
    assert "private utilities" not in progs["srf"].eligibility_text
    # "governmental entities (cities, counties, municipalities, etc.) to address ... not attaining ..." still tags
    assert tags(progs["water-quality"]) == {"municipality", "county"}
    assert all(len(p.applicant_types) == len(tags(p)) for p in progs.values())   # one tag per type
    assert {sid: p.categories[0].value for sid, p in progs.items()} == {
        "frdap": "parks", "lwcf": "parks", "rtp": "parks", "fct-parks": "parks", "srf": "water", "srf#drinking-water": "water",
        "water-quality": "water"}
    assert progs["fct-parks"].summary.startswith("The preservation of green space")   # not "View the Webinar Recording"


def test_dep_fetch_and_fallback(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", slept.append)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in fl_dep.PAGES.items() if url == fl_dep.BASE + p)
        return (FIX / "fl_dep" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = fl_dep.fetch()
    assert [r.source_id for r in records] == ["frdap", "lwcf", "rtp", "fct-parks", "srf", "srf#drinking-water", "water-quality"]
    assert slept == [3.0] * (len(fl_dep.PAGES) - 1)
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(fl_dep.BASE + fl_dep.PAGES["srf"],)))
    again = {r.source_id: r.payload for r in fl_dep.fetch(prior=prior)}
    assert again["srf"] == prior["srf"] and again["srf#drinking-water"] == prior["srf#drinking-water"]
    assert fl_dep.resolve_missing("frdap") == {"status": "unknown"}
