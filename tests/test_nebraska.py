"""Nebraska's agency connectors (ne_ded, ne_dwee, ne_dot) against saved pages, and the shared rules Nebraska added."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 14)
AGENCIES = ["ne_ded", "ne_dwee", "ne_dot"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def page(name: str, slug: str) -> dict:
    return mod(name).SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))


def programs(name: str, slug: str, today: date = TODAY) -> dict:
    """Every record a page makes (six for the CDBG page), by source_id."""
    m = mod(name)
    records = m.SITE.records_for(slug, m.PAGES[slug], [page(name, slug)], 0)
    return {sid: m.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today) for sid, payload in records}


def program(name: str, sid: str, today: date = TODAY):
    return programs(name, sid.split("#")[0], today)[sid]


def tags(name: str, sid: str) -> set[str]:
    return {t.value for t in program(name, sid).applicant_types}


def text(name: str, slug: str) -> str:
    return " ".join(t for _, t in page(name, slug)["blocks"])


def test_every_page_reads():
    for name in AGENCIES:
        m = mod(name)
        for slug in m.PAGES:
            for p in programs(name, slug).values():
                assert p.name and p.jurisdiction == "NE" and p.source_url.startswith(m.BASE), (name, slug)
            assert page(name, slug)["blocks"], (name, slug)


def test_ded_reader_takes_the_programs_own_title_and_drops_the_breadcrumb():
    assert page("ne_ded", "cccff")["title"] == "Civic and Community Center Financing Fund (CCCFF)"   # not a photo caption's `h1`
    assert page("ne_ded", "cdbg")["title"] == "Community Development Block Grant (CDBG)"
    for slug in mod("ne_ded").PAGES:
        assert not text("ne_ded", slug).startswith("Home /"), slug


def test_ded_reader_stops_before_the_resources_news_and_contacts():
    # CCCFF's press-release dates ("Apr 6, 2026") would read as rounds
    t = text("ne_ded", "cccff")
    assert "Apr 6, 2026" not in t and "Press Releases" not in t and "tia.loftin" not in t
    assert "Grant Management Resources" not in text("ne_ded", "cdbg")


def test_cdbg_is_one_record_per_funding_opportunity():
    got = programs("ne_ded", "cdbg")
    assert list(got) == ["cdbg", "cdbg#public-works-infrastructure", "cdbg#planning", "cdbg#tourism-development",
                         "cdbg#public-works-facilities", "cdbg#downtown-revitalization"]
    assert got["cdbg"].name == "CDBG Economic Development"
    assert got["cdbg#public-works-facilities"].name == "CDBG Public Works - Facilities"


def test_cdbg_statuses_a_window_is_open_and_a_deadline_with_no_year_is_not_a_date():
    got = programs("ne_ded", "cdbg")
    assert {sid: p.status for sid, p in got.items()} == {
        "cdbg": "open",                             # "Application Period: July 1, 2026 to June 30, 2027"
        "cdbg#tourism-development": "open",
        "cdbg#public-works-infrastructure": "unknown",   # "Application Deadline: Sept. 15", no year: not guessed
        "cdbg#planning": "unknown",
        "cdbg#public-works-facilities": "unknown",
        "cdbg#downtown-revitalization": "unknown",
    }
    assert got["cdbg"].opens_at == date(2026, 7, 1) and got["cdbg"].closes_at == date(2027, 6, 30)
    for sid in ("cdbg#planning", "cdbg#downtown-revitalization"):
        assert got[sid].closes_at is None
        assert got[sid].closes_at_text == "Application Deadline: Sept. 15"      # kept for the reader, not turned into a date


def test_cdbg_window_closes_when_it_has_passed():
    assert program("ne_ded", "cdbg", date(2027, 7, 1)).status == "unknown"


def test_cdbg_applicants_are_counties_and_municipalities_not_the_entitlement_cities():
    for p in programs("ne_ded", "cdbg").values():
        assert {t.value for t in p.applicant_types} == {"municipality", "county"}
        assert "not designated as a CDBG Entitlement Community" in p.eligibility_text    # the stored text keeps the carve-out


def test_cdbg_is_hud_money_passed_through_the_state():
    assert {p.funding_source for p in programs("ne_ded", "cdbg").values()} == {"pass_through"}
    # RCRP is ARPA money (its page says so); the Trust Fund, CCCFF and SBDF are state money
    assert {s: program("ne_ded", s).funding_source for s in ("rcrp", "nahtf", "cccff", "sbdf")} == {
        "rcrp": "pass_through", "nahtf": "direct", "cccff": "direct", "sbdf": "direct"}


def test_cccff_schedule_is_read_from_its_opens_and_closes_lines():
    p = program("ne_ded", "cccff")
    # "Pre-Application Period Opens: 1/1/2027 8:00 AM (CST) Pre-Application Period Closes: 1/15/2027 6:00 PM (CST)"
    assert (p.status, p.opens_at, p.closes_at) == ("forecasted", date(2027, 1, 1), date(2027, 1, 15))
    assert program("ne_ded", "cccff", date(2027, 1, 5)).status == "open"
    assert program("ne_ded", "cccff", date(2027, 1, 16)).status == "unknown"
    assert tags("ne_ded", "cccff") == {"municipality", "tribe"}
    assert p.funding_source == "direct"


def test_nahtf_takes_its_applicants_from_the_list_under_a_paragraph_label():
    assert tags("ne_ded", "nahtf") == {"municipality", "county", "housing_authority"}
    p = program("ne_ded", "nahtf")
    assert "Local and Governmental Subdivisions" in p.eligibility_text
    # the application dates sit in AmpliFund buttons, not in the page's text
    assert p.status == "unknown" and p.closes_at is None


def test_rcrp_and_sbdf_applicants():
    assert tags("ne_ded", "rcrp") == {"municipality", "county"}
    assert tags("ne_ded", "sbdf") == {"municipality", "county", "nonprofit"}
    assert program("ne_ded", "sbdf").status == "unknown"       # "Deadlines depend on funding availability"


def test_ded_waits_the_crawl_delay_its_robots_ask_for(monkeypatch):
    m = mod("ne_ded")
    assert m.SITE.DELAY_S == 3.0 and hl.HandListConnector.DELAY_S == hl.DELAY_S
    naps: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", naps.append)
    monkeypatch.setattr(hl, "get", lambda c, u: (FIX / "ne_ded" / f"{next(s for s, p in m.PAGES.items() if u == m.BASE + p)}.html").read_text(encoding="utf-8"))
    m.fetch()
    assert naps == [3.0] * (len(m.PAGES) - 1)
    # no URL it reads carries a query string (the robots file disallows `/*?`)
    assert not any("?" in p for p in m.PAGES.values())


def test_ded_fetch_and_fallback(monkeypatch):
    m = mod("ne_ded")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "ne_ded" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == ["cdbg", "cdbg#public-works-infrastructure", "cdbg#planning", "cdbg#tourism-development",
                                              "cdbg#public-works-facilities", "cdbg#downtown-revitalization",
                                              "cccff", "nahtf", "rcrp", "sbdf"]
    assert [r.source_id for r in m.fetch(limit=2)] == ["cdbg", "cdbg#public-works-infrastructure"]
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["cdbg"],)))
    again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
    assert all(again[sid] == prior[sid] for sid in prior if sid.startswith("cdbg"))
    assert m.resolve_missing("cccff") == {"status": "unknown"}


def test_the_shared_phrasings_nebraska_ded_added():
    # "not designated as ..." defines the applicants; its "not" must not drop the line, and the clause is cut before tagging
    line = "Every Nebraska county or incorporated municipality not designated as a CDBG Entitlement Community is eligible to apply."
    assert hl.NEGATION_RE.search(line)
    assert " ".join(hl.clause_cut(line).split()) == "Every Nebraska county or incorporated municipality is eligible to apply."
    assert {t.value for t in hl.applicant_tags([hl.clause_cut(line)])} == {"municipality", "county"}
    # a local government that "are eligible", at the end of the sentence
    assert hl.APPLICANT_SENTENCE_RE.search("Local governments and Nebraska nonprofits are eligible.")
    assert not hl.APPLICANT_SENTENCE_RE.search("Projects in rural areas are eligible.")
    # opens and closes in one line
    assert hl.OPENS_RE.search("Pre-Application Period Opens: 1/1/2027") and hl.OPENS_RE.search("Open Date: 10/27/2025")
    assert hl.DUE_RE.search("Pre-Application Period Closes: 1/15/2027") and hl.DUE_RE.search("Close Date: 6/1/2026")
    assert not hl.DUE_RE.search("The window closes soon")


def test_dates_after_the_deadline_word_win_over_the_opening_date():
    s = ["Pre-Application Period Opens: 1/1/2027 8:00 AM (CST) Pre-Application Period Closes: 1/15/2027 6:00 PM (CST)"]
    assert hl.deadline(s)[1] == date(2027, 1, 15) and hl.opening(s) == date(2027, 1, 1)
    # a deadline word with its date before it still reads ("June 1, 2027 is the deadline")
    assert hl.deadline(["June 1, 2027 is the deadline."])[1] == date(2027, 6, 1)
    # a sentence with an opening word only is unchanged
    assert hl.opening(["Applications open on March 1, 2027."]) == date(2027, 3, 1)


def test_tagger_reads_local_and_governmental_subdivisions():
    assert {t.value for t in hl.applicant_tags(["Local and Governmental Subdivisions"])} == {"municipality", "county"}



# ---------- Water, Energy, and Environment ----------


def test_dwee_reader_takes_the_larger_body_field_and_leaves_out_contacts_and_the_footer():
    for slug in mod("ne_dwee").PAGES:
        t = text("ne_dwee", slug)
        assert len(t) > 400, slug                                  # the menus' small copies of the body field are not it
        assert "@nebraska.gov" not in t and "Official Nebraska Government Website" not in t, slug
    # the waste pages keep their text in the other body field
    assert "Cities of the first class" in text("ne_dwee", "deconstruction")
    assert page("ne_dwee", "illegal-dumpsite")["title"] == "Illegal Dumpsite Cleanup Program"


def test_dwee_statuses_the_pages_state_no_round_except_the_school_loans():
    got = {slug: program("ne_dwee", slug) for slug in mod("ne_dwee").PAGES}
    assert {s: p.status for s, p in got.items()} == {
        "cwsrf": "unknown", "dwsrf": "unknown", "dw-planning": "unknown", "section-319": "unknown", "deconstruction": "unknown",
        "illegal-dumpsite": "unknown", "scrap-tire": "unknown",
        "eecbg": "unknown",        # "The second-round application period is open through April 15, 2026": past on 2026-11-14
        "eerlf": "open",           # "Status: Program open."
    }
    # a deadline the page states and that has passed is kept as the page's sentence
    assert got["eecbg"].closes_at_text.startswith("Application deadline for the formula award was July 31, 2023")


def test_dwee_applicants_are_what_each_page_says():
    assert tags("ne_dwee", "cwsrf") == {"municipality"}
    assert tags("ne_dwee", "dw-planning") == {"municipality"}                       # "Any city, town, village, ... may be eligible."
    assert tags("ne_dwee", "section-319") == {"municipality", "county", "nonprofit"}  # "Funding is distributed to local governments, ..."
    assert tags("ne_dwee", "deconstruction") == {"municipality", "county"}          # under "Who\u2019s Eligible"
    assert tags("ne_dwee", "illegal-dumpsite") == {"municipality", "county"}        # "Political subdivisions. This can include ..."
    assert tags("ne_dwee", "scrap-tire") == {"municipality", "county", "nonprofit"}
    assert tags("ne_dwee", "eecbg") == {"municipality", "county"}
    assert tags("ne_dwee", "eerlf") == {"school"}                                    # "K-12 public schools can now apply"
    assert tags("ne_dwee", "dwsrf") == set()        # "owners of public drinking water systems": no tag says who


def test_dwee_privately_owned_systems_are_not_applicants():
    p = program("ne_dwee", "dw-planning")
    assert "Privately-owned water supply systems are not eligible for assistance." in p.eligibility_text
    assert {t.value for t in p.applicant_types} == {"municipality"}


def test_dwee_funding_source_type_and_category():
    got = {slug: program("ne_dwee", slug) for slug in mod("ne_dwee").PAGES}
    assert {s: p.funding_source for s, p in got.items()} == {
        "cwsrf": "direct", "dwsrf": "pass_through", "dw-planning": "direct", "section-319": "pass_through", "deconstruction": "direct",
        "illegal-dumpsite": "direct", "scrap-tire": "direct", "eecbg": "pass_through", "eerlf": "direct"}
    assert got["eerlf"].funding_type == "loan" and got["cwsrf"].funding_type == "loan" and got["deconstruction"].funding_type == "grant"
    assert [c.value for c in got["cwsrf"].categories] == ["water"] and [c.value for c in got["eecbg"].categories] == ["energy"]
    assert [c.value for c in got["deconstruction"].categories] == ["other"]       # waste is not a label the shared table knows


def test_dwee_fetch_and_fallback(monkeypatch):
    m = mod("ne_dwee")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "ne_dwee" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == list(m.PAGES)
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["eecbg"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["eecbg"] == prior["eecbg"]
    assert m.resolve_missing("eecbg") == {"status": "unknown"}


def test_the_shared_phrasings_nebraska_dwee_added():
    assert hl.AGENCY_OPEN_RE.search("Status: Program open.") and hl.AGENCY_OPEN_RE.search("status: open")
    assert not hl.AGENCY_OPEN_RE.search("The program is open to counties.")
    for label in ("Who\u2019s Eligible", "Who's Eligible?", "What communities are considered for these grants?"):
        assert hl.ELIGIBILITY_LABEL_RE.search(label), label
    assert hl.APPLICANT_SENTENCE_RE.search("Funding is distributed to local governments, educational institutions, and nonprofit organizations.")
    assert hl.APPLICANT_SENTENCE_RE.search("Nebraska K-12 public schools can now apply for low-interest loans through the program.")
    # an amount limit is not an eligibility statement (Missouri DED, Kentucky CMAQ: "the amount any applicant can apply for")
    assert not hl.APPLICANT_SENTENCE_RE.search("The maximum amount any applicant can apply for is $500,000 or $5,000 per household.")


# ---------- Transportation ----------


def test_dot_reader_takes_the_title_from_the_title_tag_and_both_templates_body():
    assert page("ne_dot", "ta")["title"] == "Transportation Alternatives"                 # no `h1` on these pages; " - NDOT" is cut
    assert page("ne_dot", "county-bridge-match")["title"] == "County Bridge Match Program"
    for slug in mod("ne_dot").PAGES:                         # `div.mainContent` (TA, HSIP) and `div#main` (the rest) both read
        t = text("ne_dot", slug)
        assert len(t) > 150, slug
        assert "CONTACT NDOT HEADQUARTERS" not in t and "1500 Nebraska Parkway" not in t, slug


def test_dot_transit_is_one_record_per_program():
    got = programs("ne_dot", "transit")
    assert list(got) == ["transit", "transit#5311f", "transit#5310", "transit#5339"]
    assert got["transit#5310"].name.startswith("Section 5310 Enhanced Mobility")
    assert {p.funding_source for p in got.values()} == {"pass_through"}                 # "Provides federal funding ..."


def test_dot_statuses_a_closed_round_says_so_and_a_yearless_window_is_not_a_date():
    assert program("ne_dot", "county-bridge-match").status == "closed"                  # "Applications for the 2025 funding round are closed ."
    assert {p.status for sid in ("ta", "hsip", "economic-opportunity") for p in programs("ne_dot", sid).values()} == {"unknown"}
    p = program("ne_dot", "transit#5310")
    assert p.status == "unknown" and p.closes_at is None
    assert p.closes_at_text == "Applications accepted Oct. 31 to Nov. 30"                 # kept for the reader, not guessed into a year
    assert program("ne_dot", "hsip").closes_at_text.startswith("HSIP applications received by January 31 st each year")
    assert program("ne_dot", "transit").closes_at_text is None                            # a page-wide sentence of another program does not leak


def test_dot_applicants_are_only_what_the_page_says():
    assert tags("ne_dot", "county-bridge-match") == {"county"}
    # TA, HSIP ("local public agencies"), the Economic Opportunity Program and the transit pages name no applicant the shared
    # tagger reads; "local public agencies" is a candidate rule left to Saj (it moved 34 California records), so none is tagged
    for sid in ("ta", "hsip", "economic-opportunity", "transit", "transit#5311f", "transit#5310", "transit#5339"):
        assert tags("ne_dot", sid) == set(), sid


def test_dot_funding_source_and_category():
    assert program("ne_dot", "county-bridge-match").funding_source == "direct"          # a state program (TIA): no federal source named
    assert program("ne_dot", "economic-opportunity").funding_source == "direct"
    assert {program("ne_dot", s).funding_source for s in ("ta", "hsip")} == {"pass_through"}
    assert all([c.value for c in p.categories] == ["transportation"] for slug in mod("ne_dot").PAGES for p in programs("ne_dot", slug).values())


def test_dot_fetch_and_fallback(monkeypatch):
    m = mod("ne_dot")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "ne_dot" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == ["ta", "hsip", "county-bridge-match", "economic-opportunity",
                                              "transit", "transit#5311f", "transit#5310", "transit#5339"]
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["transit"],)))
    again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
    assert all(again[sid] == prior[sid] for sid in prior if sid.startswith("transit"))      # `transit` and `transit#...` all kept
    assert m.resolve_missing("hsip") == {"status": "unknown"}

@pytest.mark.parametrize("name", AGENCIES)
def test_module_contract(name):
    m = mod(name)
    assert m.CONNECTOR == name and m.AGENCY_CODE.startswith("NE-") and m.CATEGORY_LABEL
    assert callable(m.fetch) and callable(m.normalize) and callable(m.resolve_missing)


def test_a_page_without_a_body_reads_as_no_blocks():
    m = mod("ne_ded")
    assert m.parse_page("<html><h1>Gone</h1></html>") == {"title": "Gone", "blocks": []}
