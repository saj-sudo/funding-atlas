"""Missouri's agency connectors (mo_ded, mo_dnr) and their Drupal base, against saved pages."""

from __future__ import annotations

import importlib
import re
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from connectors import missouri_drupal as mo
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 11)
AGENCIES = ["mo_ded", "mo_dnr"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def page(name: str, slug: str) -> dict:
    return mod(name).SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))


def programs(name: str, slug: str, today: date = TODAY) -> dict:
    """Every record a page makes (more than one for a page that holds several programs), by source_id."""
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
                assert p.name and p.jurisdiction == "MO" and p.source_url.startswith(m.BASE), (name, slug)
            assert page(name, slug)["blocks"], (name, slug)


def test_ded_reader_takes_the_program_title_and_stops_at_the_help_section():
    # the first h1 is the department's name, the second the program's
    assert page("mo_ded", "water-wastewater")["title"] == "Community Development Block Grants Water/Wastewater"
    assert page("mo_ded", "emergency")["title"] == "Community Development Block Grants Emergency & Long-Term Recovery"
    for slug in mod("mo_ded").PAGES:
        t = text("mo_ded", slug)
        assert "Need Help?" not in t and "Social toolbar" not in t, slug


def test_ded_statuses_come_from_the_pages_own_alert():
    got = {sid: p.status for slug in mod("mo_ded").PAGES for sid, p in programs("mo_ded", slug).items()}
    assert got == {
        "competitive-cycle": "closed",                      # "FY26 CDBG Competitive Cycle Application is now closed."
        "competitive-cycle#general-infrastructure": "closed",
        "competitive-cycle#demolition": "closed",
        "economic-development": "open",                     # "Currently Accepting Applications!" (open, year-round)
        "economic-development#industrial-infrastructure": "open",
        "emergency": "open",                                # "The Emergency Cycle is currently open."
        "water-wastewater": "open",                         # "... is currently open."
    }


def test_a_page_with_two_tabs_is_one_record_per_program():
    """DED names each program under "Description" and again under "Do I Qualify?": the records join the two."""
    cycle = programs("mo_ded", "competitive-cycle")
    assert list(cycle) == ["competitive-cycle", "competitive-cycle#general-infrastructure", "competitive-cycle#demolition"]
    assert [p.name for p in cycle.values()] == ["CDBG Community Facilities", "CDBG General Infrastructure", "CDBG Demolition"]
    assert all(p.source_url == "https://ded.mo.gov/programs/community/community-development-block-grants-competitive-cycle"
               for p in cycle.values())
    m = mod("mo_ded")
    body = {sid: " ".join(t for _, t in payload["page"]["blocks"])
            for sid, payload in m.SITE.records_for("competitive-cycle", m.PAGES["competitive-cycle"], [page("mo_ded", "competitive-cycle")], 0)}
    # each program carries its own description and its own qualifying text, and not the next program's
    assert "senior centers" in body["competitive-cycle"] and "Current limit is $500,000 or $5,000 per benefitting household" in body["competitive-cycle"]
    assert "Current limit is $200,000 for residential only" in body["competitive-cycle#demolition"]
    assert "Current limit is $200,000" not in body["competitive-cycle"]
    assert "senior centers" not in body["competitive-cycle#demolition"]
    assert "Do I Qualify?" in body["competitive-cycle#demolition"]
    assert [p.summary.split(" ")[0:2] for p in cycle.values()] == [["This", "program"], ["This", "program"], ["These", "grants"]]
    assert cycle["competitive-cycle#demolition"].summary.startswith("These grants help Missouri communities with demolition")


def test_join_tabs_edges():
    splits = [("a", "A", re.compile("^Alpha$")), ("b", "B", re.compile("^Beta$"))]
    blocks = [("p", "alert"), ("label", "Description"), ("label", "Alpha"), ("p", "a desc"), ("label", "Beta"), ("p", "b desc"),
              ("label", "Do I Qualify?"), ("label", "Alpha"), ("li", "a rule"), ("label", "Beta"), ("li", "b rule")]
    out = mo.join_tabs(blocks, splits, ("label",))
    assert [(s, n) for s, n, _ in out] == [("a", "A"), ("b", "B")]
    a = dict((s, b) for s, _, b in out)["a"]
    assert a.index(("p", "a desc")) < a.index(("label", "Do I Qualify?")) < a.index(("li", "a rule"))
    assert ("li", "b rule") not in a
    # no second tab: the same as `split_sections`
    flat = blocks[:6]
    assert mo.join_tabs(flat, splits, ("label",)) == hl.split_sections(flat, splits, ("label",))
    # a program named only in the second tab still gets a record
    only_second = [("p", "x"), ("label", "Do I Qualify?"), ("label", "Beta"), ("li", "b rule")]
    assert [s for s, _, _ in mo.join_tabs(only_second, splits, ("label",))] == ["b"]


def test_ded_applicants_are_only_what_the_page_says():
    # "Eligible applicants include non-entitlement cities and counties." and the emergency tab's recipient line
    assert tags("mo_ded", "economic-development") == {"municipality", "county"}
    assert tags("mo_ded", "emergency") == {"municipality", "county"}
    # these pages name no applicant, so nothing is tagged: the beneficiaries of Industrial Infrastructure are businesses,
    # and the companies are not who applies
    for sid in ("competitive-cycle", "competitive-cycle#general-infrastructure", "competitive-cycle#demolition",
                "economic-development#industrial-infrastructure", "water-wastewater"):
        assert tags("mo_ded", sid) == set(), sid
    assert "Eligible Beneficiary Businesses" not in (program("mo_ded", "economic-development#industrial-infrastructure").eligibility_text or "")


def test_ded_is_hud_money_passed_through_the_state():
    for slug in mod("mo_ded").PAGES:
        assert {p.funding_source for p in programs("mo_ded", slug).values()} == {"pass_through"}, slug
    assert program("mo_ded", "economic-development").match_required is True      # "a match of no less than 20%"
    assert program("mo_ded", "competitive-cycle").category_pairs() == [("infrastructure", "community development")]


def test_dnr_reader_stops_before_the_footer_blocks_and_the_awards_lists():
    for slug in mod("mo_dnr").PAGES:
        t = text("mo_dnr", slug)
        assert "Popular Links" not in t and "Contact Information" not in t, slug
    labels = [t for k, t in page("mo_dnr", "eecbg")["blocks"] if k == "label"]
    assert "Who Can Apply" in labels and "Awards" not in labels      # the list of past awardees is not read


def test_dnr_statuses_come_from_the_application_period_banner():
    got = {slug: program("mo_dnr", slug).status for slug in mod("mo_dnr").PAGES}
    assert got["flood-resiliency"] == "open" and got["section-319"] == "open" and got["well-plugging"] == "open"
    assert got["dwsrf-lead-service-line"] == "open"
    assert got["eecbg"] == "closed" and got["energy-loans"] == "closed" and got["scrap-tire-surface"] == "closed"
    # no banner and no round sentence: the source states none, so `unknown`
    assert got["cwsrf-loan"] == "unknown" and got["dwsrf-loan"] == "unknown" and got["multipurpose-water-resource"] == "unknown"


def test_dnr_applicants_include_the_long_list_items_and_not_the_beneficiaries():
    # a whole sentence of applicants is one list item; "that are not owned by the federal government" is not a negation
    assert {"county", "municipality"} <= tags("mo_dnr", "dwsrf-loan")
    assert {"county", "municipality"} <= tags("mo_dnr", "cwsrf-loan")
    # "Eligible recipients include the following:" keeps its list (EECBG, Energy Loans)
    assert tags("mo_dnr", "eecbg") == {"municipality", "county"}
    assert {"municipality", "county", "school", "higher_ed", "nonprofit", "business"} <= tags("mo_dnr", "energy-loans")
    # a plan "to provide safe drinking water to a group of households" names who the project serves, not who applies
    assert "household" not in tags("mo_dnr", "dwsrf-engineering-report")
    assert "household" in {t.value for t in hl.applicant_tags(["Homeowners may apply."])}
    # "governmental organizations other than state agencies are eligible to submit applications" excludes the state
    assert "state" not in tags("mo_dnr", "scrap-tire-surface")
    assert "school" in tags("mo_dnr", "scrap-tire-surface")
    # no tagger word for these two, so nothing is tagged rather than something wrong
    assert tags("mo_dnr", "section-604b") == set() and tags("mo_dnr", "source-water-protection") == set()


def test_dnr_funding_source_is_what_the_page_names():
    for slug in ("cwsrf-engineering-report", "dwsrf-lead-service-line", "section-319", "eecbg", "well-plugging"):
        assert program("mo_dnr", slug).funding_source == "pass_through", slug
    for slug in ("cwsrf-loan", "dwsrf-loan", "flood-resiliency", "energy-loans"):
        assert program("mo_dnr", slug).funding_source == "direct", slug
    assert program("mo_dnr", "cwsrf-loan").funding_type == "loan" and program("mo_dnr", "eecbg").funding_type == "grant"
    assert program("mo_dnr", "flood-resiliency").category_pairs() == [("public_safety", "emergency mitigation")]
    assert program("mo_dnr", "energy-audit").category_pairs() == [("energy", "energy")]


def test_dnr_leaves_out_what_is_not_for_public_bodies():
    for slug in ("cwsrf-onsite", "operator-training-voucher", "brownfields-assessments", "scrap-tire-cleanup", "swmd-grants",
                 "grid-resilience", "wood-energy-tax-credit"):
        assert slug not in mod("mo_dnr").PAGES


def test_the_shared_phrasings_dnr_added():
    assert hl.AGENCY_OPEN_RE.search("Application Period is Open")
    assert hl.APPLICANT_SENTENCE_RE.search("Eligible recipients include the following:")
    assert hl.APPLICANT_SENTENCE_RE.search("Schools are eligible to submit applications.")
    assert hl.clause_cut("Cities and political subdivisions that are not owned by the federal government") == "Cities and political subdivisions "
    assert hl.NEGATION_RE.search("Cities that are not owned by the federal government")      # the guard it works around
    # an exclusion is a limit on the other names, not a name
    assert "state" not in {t.value for t in hl.applicant_tags([hl.clause_cut("governmental organizations other than state agencies")])}


def test_the_shared_phrasings_missouri_added():
    # "is currently open" is open wording; "Do I Qualify?" heads an eligibility list
    assert hl.AGENCY_OPEN_RE.search("The Emergency Cycle is currently open.")
    assert not hl.AGENCY_OPEN_RE.search("The program is open to counties.")
    assert hl.ELIGIBILITY_LABEL_RE.search("Do I Qualify?") and hl.ELIGIBILITY_LABEL_RE.search("do i qualify")
    assert not hl.ELIGIBILITY_LABEL_RE.search("Do I Qualify for a waiver?")


def test_fetch_and_fallback(monkeypatch):
    m = mod("mo_ded")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "mo_ded" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == ["competitive-cycle", "competitive-cycle#general-infrastructure",
                                              "competitive-cycle#demolition", "economic-development",
                                              "economic-development#industrial-infrastructure", "emergency", "water-wastewater"]
    assert [r.source_id for r in m.fetch(limit=2)] == ["competitive-cycle", "competitive-cycle#general-infrastructure"]
    prior = {r.source_id: r.payload for r in records}
    # a page that cannot be read keeps every stored record of its slug (`slug` and `slug#...`)
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["competitive-cycle"],)))
    again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
    assert all(again[sid] == prior[sid] for sid in prior if sid.startswith("competitive-cycle"))
    assert m.resolve_missing("emergency") == {"status": "unknown"}


def test_dnr_fetch_and_fallback(monkeypatch):
    m = mod("mo_dnr")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "mo_dnr" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == list(m.PAGES)
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["eecbg"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["eecbg"] == prior["eecbg"]
    assert m.resolve_missing("eecbg") == {"status": "unknown"}


def test_base_without_a_body():
    assert mo.parse_page("<html><h1>Gone</h1></html>") == {"title": "Gone", "blocks": []}


@pytest.mark.parametrize("name", AGENCIES)
def test_module_contract(name):
    m = mod(name)
    assert m.CONNECTOR == name and m.AGENCY_CODE.startswith("MO-") and m.CATEGORY_LABEL
    assert callable(m.fetch) and callable(m.normalize) and callable(m.resolve_missing)
