"""Arkansas's agency connectors (ar_anrd, ar_adem, ar_ooo, ar_aedc) against saved pages, and the shared rules Arkansas added."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 14)
AGENCIES = ["ar_anrd", "ar_adem", "ar_ooo", "ar_aedc"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def page(name: str, slug: str) -> dict:
    return mod(name).SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))


def programs(name: str, slug: str, today: date = TODAY) -> dict:
    m = mod(name)
    records = m.SITE.records_for(slug, m.PAGES[slug], [page(name, slug)], 0)
    return {sid: m.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today) for sid, payload in records}


def program(name: str, sid: str, today: date = TODAY):
    return programs(name, sid.split("#")[0], today)[sid]


def every(name: str, today: date = TODAY) -> dict:
    out: dict = {}
    for slug in mod(name).PAGES:
        out.update(programs(name, slug, today))
    return out


def tags(name: str, sid: str) -> set[str]:
    return {t.value for t in program(name, sid).applicant_types}


def text(name: str, slug: str) -> str:
    return " ".join(t for _, t in page(name, slug)["blocks"])


def test_every_page_reads_into_fifteen_records():
    total = 0
    for name in AGENCIES:
        m = mod(name)
        for slug in m.PAGES:
            assert page(name, slug)["blocks"], (name, slug)
        got = every(name)
        for sid, p in got.items():
            assert p.name and p.jurisdiction == "AR" and p.source_url.startswith(m.BASE), (name, sid)
            assert p.summary is None or "[email" not in p.summary
        total += len(got)
    assert total == 15


def test_wordpress_titles_come_from_the_title_tag():
    # the `h1` on Agriculture's pages is the division ("Natural Resources"); ADEM's pages have none
    assert page("ar_anrd", "water-wastewater")["title"] == "Water and Wastewater Funding"
    assert page("ar_anrd", "hhpd")["title"] == "High Hazard Potential Dam Grant Program"
    assert page("ar_adem", "hmgp")["title"] == "Hazard Mitigation Grant Program"
    assert page("ar_ooo", "matching")["title"] == "Matching Grants"
    assert program("ar_ooo", "matching").name == "Outdoor Recreation Matching Grants"


def test_wordpress_reader_drops_contacts_and_stops_at_the_forms():
    t = text("ar_anrd", "water-wastewater")
    assert "Applications for Arkansas Department of Agriculture funding are currently closed." in t   # after "Contact Information"
    assert "Terri Woodard" not in t and "email protected" not in t
    assert "Clean Water Benefits Report" not in t                                                   # "Forms and Resources"
    assert "EXPENDITURE REPORT" not in text("ar_ooo", "fun-park")                                   # "PROJECT MANAGEMENT"
    # the window line Outdoor Recreation prints twice is read once
    assert [t for _, t in page("ar_ooo", "matching")["blocks"] if t.startswith("Opens:")] == ["Opens: May 1, 2026 Due: August 28, 2026"]


def test_agriculture_records():
    got = every("ar_anrd")
    assert list(got) == ["water-wastewater", "hhpd", "section-319"]
    assert {s: p.status for s, p in got.items()} == {"water-wastewater": "closed", "hhpd": "unknown", "section-319": "unknown"}
    assert got["water-wastewater"].closes_at is None                    # the priority list's table dates are not read
    assert got["water-wastewater"].funding_type == "loan" and got["water-wastewater"].funding_source == "direct"
    assert {s: p.funding_source for s, p in got.items() if s != "water-wastewater"} == {"hhpd": "pass_through", "section-319": "pass_through"}
    assert tags("ar_anrd", "water-wastewater") == {"municipality", "county", "special_district"}
    # a paragraph under "Eligible Applicants" is read sentence by sentence; "Private dam owners cannot apply" is negated
    assert tags("ar_anrd", "hhpd") == {"state", "county", "municipality", "special_district", "nonprofit"}
    assert tags("ar_anrd", "section-319") == {"municipality", "county", "nonprofit"}
    assert got["section-319"].summary.startswith("The Section 319(h) grant program")      # its own section, not the intro
    assert got["section-319"].match_required is True
    assert "Bayou Bartholomew" not in text("ar_anrd", "section-319") or "Bayou Bartholomew" not in " ".join(
        t for _, t in hl.split_sections(page("ar_anrd", "section-319")["blocks"], mod("ar_anrd").SPLITS["section-319"])[0][2])


def test_adem_records_and_the_hazard_mitigation_split():
    got = every("ar_adem")
    assert list(got) == ["hmgp", "hazard-mitigation#bric", "hazard-mitigation", "hsgp"]           # page order
    assert got["hazard-mitigation"].name == "State of Arkansas Hazard Mitigation Grant Program"
    state = got["hazard-mitigation"]
    # "will begin accepting Notices of Intent (NOI's) May 26, 2026 through June 15, 2026": the window, now past
    assert (state.status, state.opens_at, state.closes_at) == ("unknown", date(2026, 5, 26), date(2026, 6, 15))
    assert state.funding_source == "direct" and tags("ar_adem", "hazard-mitigation") == {"municipality", "county", "nonprofit"}
    assert program("ar_adem", "hazard-mitigation", date(2026, 6, 1)).status == "open"
    assert got["hsgp"].status == "closed"                    # "not accepting additional applications"
    assert {p.funding_source for s, p in got.items() if s != "hazard-mitigation"} == {"pass_through"}
    assert tags("ar_adem", "hmgp") == {"municipality", "county"}
    # the Shelter Rebate and federal HMGP sections belong to no record
    for p in got.values():
        assert "Shelter Rebate Program ended in 2016" not in (p.summary or "")


def test_adem_obeys_the_crawl_delay():
    assert mod("ar_adem").SITE.DELAY_S == 10 and mod("ar_ooo").SITE.DELAY_S == 10
    assert mod("ar_anrd").SITE.DELAY_S == hl.DELAY_S


def test_outdoor_recreation_windows_and_applicants():
    got = every("ar_ooo")
    assert {s: (p.status, p.opens_at, p.closes_at) for s, p in got.items()} == {
        "matching": ("unknown", date(2026, 5, 1), date(2026, 8, 28)),
        "fun-park": ("unknown", date(2026, 5, 1), date(2026, 8, 28)),
        "trails": ("unknown", date(2026, 3, 9), date(2026, 6, 30)),
    }
    assert program("ar_ooo", "matching", date(2026, 6, 1)).status == "open"
    assert program("ar_ooo", "matching", date(2026, 4, 1)).status == "forecasted"
    for slug in got:
        assert tags("ar_ooo", slug) == {"municipality", "county"}, slug     # the bold "Eligible applicants:" item is kept
    assert got["fun-park"].match_required is None                            # "(no match required)": the shared rule stores no answer
    assert {c.value for p in got.values() for c in p.categories} == {"parks"}


def test_aedc_reader():
    assert page("ar_aedc", "site-development")["title"] == "Arkansas Site Development Program"
    t = text("ar_aedc", "rural-community")
    assert "About Us" not in t and "Wildlife Education Grant" not in t     # the side menu, a list of links
    assert "Answer 5 questions" not in text("ar_aedc", "cdbg")
    assert "Greenfield industrial sites" in text("ar_aedc", "site-development")   # a bare `div` read as a paragraph
    cdbg = text("ar_aedc", "cdbg")
    assert "CAPER" not in cdbg and "Quarterly Performance Reports" not in cdbg and "Ike" not in cdbg


def test_aedc_records():
    got = every("ar_aedc")
    assert list(got) == ["cdbg", "site-development", "rural-community", "rural-block-grant", "wildlife-education"]
    assert {s: p.status for s, p in got.items()} == {
        "cdbg": "unknown", "site-development": "unknown", "rural-community": "open", "rural-block-grant": "unknown",
        "wildlife-education": "unknown"}
    assert got["rural-community"].closes_at == date(2027, 3, 11)                # Cycle II; Cycle I (Aug 13) has passed
    assert program("ar_aedc", "rural-community", date(2026, 8, 1)).closes_at == date(2026, 8, 13)
    assert got["site-development"].closes_at == date(2026, 11, 6) and got["site-development"].opens_at == date(2026, 8, 25)
    assert got["rural-block-grant"].closes_at == date(2026, 10, 16)
    assert got["wildlife-education"].closes_at == date(2026, 11, 12)
    assert got["cdbg"].funding_source == "pass_through"
    assert {got[s].funding_source for s in got if s != "cdbg"} == {"direct"}
    # "cities and counties may apply for projects that will benefit non-profit groups, for-profit companies": beneficiaries
    assert tags("ar_aedc", "cdbg") == {"municipality", "county"}
    assert tags("ar_aedc", "rural-community") == {"municipality"}
    assert tags("ar_aedc", "rural-block-grant") == {"municipality"}
    assert tags("ar_aedc", "wildlife-education") == {"school"}
    assert {"municipality", "county"} <= tags("ar_aedc", "site-development")


def test_fetch_and_fallback(monkeypatch):
    m = mod("ar_ooo")
    slept: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", slept.append)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "ar_ooo" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == list(m.PAGES)
    assert slept == [10.0, 10.0]
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["trails"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["trails"] == prior["trails"]
    assert m.resolve_missing("trails") == {"status": "unknown"}


def test_the_shared_rules_arkansas_added():
    # "Opens:" as an opening label, the date between it and the deadline word
    assert hl.opening(["Opens: May 1, 2026 Due: August 28, 2026"]) == date(2026, 5, 1)
    assert hl.AGENCY_CLOSED_RE.search("At this time, the AR HSGP is not accepting additional applications.")
    assert hl.AGENCY_CLOSED_RE.search("We are not accepting new applications.")
    # a Notice of Intent window is an application window
    s = "The program will begin accepting Notices of Intent (NOI's) May 26, 2026 through June 15, 2026, for FY2027."
    assert hl.deadline([s]) == (s, date(2026, 6, 15))
    assert not hl.application_range(["The program year runs July 1, 2025 through June 30, 2026."])
    # cycles under a plural "Deadlines": the one still ahead, else the last
    c = "Fiscal Year 2027 Deadlines are: Cycle I - August 13, 2026 Cycle II - March 11, 2027"
    assert hl.deadline([c], date(2026, 11, 14)) == (c, date(2027, 3, 11))
    assert hl.deadline([c], date(2027, 4, 1)) == (c, date(2027, 3, 11))
    assert hl.deadline([c]) == (None, None)        # no run date, no cycle rule ("Deadlines" is not the singular word)
    # applicant sentences and the beneficiary cut
    assert hl.APPLICANT_SENTENCE_RE.search("All NOI's must be submitted by local governments or non-profit organizations.")
    assert hl.APPLICANT_SENTENCE_RE.search("Applicants from incorporated towns of less than 3,000 in population are eligible.")
    assert not hl.APPLICANT_SENTENCE_RE.search("Applicants from previous rounds must reapply.")
    assert hl.clause_cut("cities and counties may apply for projects that will benefit non-profit groups.") == "cities and counties may apply for ."
