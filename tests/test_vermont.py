"""Vermont's four agency connectors (vt_accd, vt_vtrans, vt_fpr, vt_vem) and their base, against saved pages."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from connectors import vermont_drupal as vd
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 4)
AGENCIES = ["vt_accd", "vt_vtrans", "vt_fpr", "vt_vem"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def program(name: str, slug: str, today: date = TODAY):
    m = mod(name)
    page = m.SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))
    return m.normalize(RawRecord(source_connector=name, source_id=slug, payload={"path": m.PAGES[slug], "page": page}), today)


def tags(name: str, slug: str) -> set[str]:
    return {t.value for t in program(name, slug).applicant_types}


def test_every_page_has_a_fixture_and_a_title():
    for name in AGENCIES:
        for slug in mod(name).PAGES:
            p = program(name, slug)
            assert p.name and p.jurisdiction == "VT" and p.source_url.startswith(mod(name).BASE), (name, slug)


def test_body_is_the_main_blocks_field_not_a_sidebar_one():
    page = vd.parse_page((FIX / "vt_vtrans" / "transport-alt.html").read_text(encoding="utf-8"))
    texts = [t for _, t in page["blocks"]]
    assert page["title"] == "Transportation Alternatives Program"
    assert any("Applications due December 4th, 2026" in t for t in texts)
    assert not any("committed to ensuring accessibility" in t or "@vermont.gov" in t for t in texts)


def test_status_table():
    rows = {(n, s): (program(n, s).status, program(n, s).opens_at, program(n, s).closes_at) for n, s in [
        ("vt_fpr", "rtp"), ("vt_fpr", "vorec"), ("vt_accd", "municipal-planning-grant"), ("vt_vtrans", "transport-alt"),
        ("vt_vtrans", "better-roads"), ("vt_accd", "vcdp"), ("vt_accd", "downtown-transportation-fund"),
        ("vt_vtrans", "grants-in-aid"), ("vt_vem", "mitigation"), ("vt_vem", "empg")]}
    assert rows[("vt_fpr", "rtp")] == ("open", date(2026, 9, 29), date(2026, 11, 20))          # pre-application deadline
    assert rows[("vt_fpr", "vorec")] == ("open", date(2026, 10, 6), date(2026, 12, 13))
    assert rows[("vt_accd", "municipal-planning-grant")] == ("open", date(2026, 10, 1), date(2026, 12, 2))
    assert rows[("vt_vtrans", "transport-alt")] == ("open", None, date(2026, 12, 4))           # ordinal date in a link
    assert rows[("vt_vtrans", "better-roads")] == ("open", None, date(2026, 11, 20))           # the numeric date
    assert rows[("vt_accd", "vcdp")] == ("open", None, None)                                   # "now open", no date
    assert rows[("vt_accd", "downtown-transportation-fund")][0] == "closed"
    assert rows[("vt_vtrans", "grants-in-aid")] == ("closed", None, date(2026, 5, 1))
    assert rows[("vt_vem", "mitigation")] == ("unknown", None, date(2026, 5, 15))             # past, nothing else said
    assert rows[("vt_vem", "empg")][0] == "unknown"
    assert program("vt_vem", "mitigation").closes_at_text == "State application deadline: May 15, 2026."


def test_status_moves_with_the_run_date():
    assert program("vt_accd", "municipal-planning-grant", date(2026, 9, 1)).status == "forecasted"
    assert program("vt_fpr", "rtp", date(2026, 11, 21)).status == "unknown"
    assert program("vt_vtrans", "better-roads", date(2026, 11, 21)).status == "unknown"        # past date beats "now open"


def test_deadline_date_must_sit_by_its_word():
    sents = ["July 23, 2024: See the Amended Notice of Funding Opportunity for Vermont DR-4720 for more information, "
             "including changes to the deadline.", "State application deadline: May 15, 2026."]
    assert vd.deadline(sents)[1] == date(2026, 5, 15)
    assert vd.deadline(["January 31, 2029 - Grant Closeout Due"]) == (None, None)


def test_applicants():
    assert tags("vt_accd", "vcdp") >= {"municipality"}                     # "(except Burlington)" is not a negation
    assert "business" not in tags("vt_accd", "vcdp") and "nonprofit" not in tags("vt_accd", "vcdp")
    assert tags("vt_fpr", "vorec") == {"municipality", "nonprofit"}       # example projects are not applicants
    assert {"municipality", "tribe", "state"} <= tags("vt_fpr", "lwcf")
    assert tags("vt_vtrans", "better-roads") == {"municipality"}          # the bold intro sentence
    assert tags("vt_accd", "municipal-planning-grant") == {"municipality"}
    # the pages name no applicant; the joint guidebook's "Eligible Applicants:" list is quoted by hand, dated
    assert {"municipality", "county", "school", "tribe", "nonprofit"} <= tags("vt_vtrans", "transport-alt")
    assert tags("vt_vtrans", "mhsmp") == tags("vt_vtrans", "transport-alt")
    assert program("vt_vtrans", "mhsmp").eligibility_text.startswith(
        "VTrans TAP and MHSMP Grant Guidebook, October 2026 (PDF), Eligible Applicants, read 2026-11-04: A local government.")
    assert tags("vt_vem", "empg") == set()                                # subgrants go to the RPCs


def test_funding_source_and_match():
    assert program("vt_fpr", "vorec").funding_source == "direct"          # "Funding source: One-time State General Funds"
    assert program("vt_fpr", "rtp").funding_source == "pass_through"
    assert program("vt_accd", "vcdp").funding_source == "pass_through"    # HUD
    assert program("vt_vem", "empg").funding_source == "pass_through"     # "The Federal Emergency Management Agency provides"
    assert program("vt_accd", "municipal-planning-grant").funding_source == "direct"
    assert program("vt_fpr", "rtp").match_required is True


def test_categories_by_agency():
    assert program("vt_accd", "vcdp").category_pairs() == [("infrastructure", "community development")]
    assert program("vt_vtrans", "mhsmp").category_pairs() == [("transportation", "transportation")]
    assert program("vt_fpr", "lwcf").category_pairs() == [("parks", "recreation and conservation")]
    assert program("vt_vem", "pa").category_pairs() == [("public_safety", "emergency management")]


def test_fetch_walks_the_pages_and_falls_back_to_prior(monkeypatch):
    m = mod("vt_fpr")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    calls: list[str] = []

    def site(client, url, broken=()):
        calls.append(url)
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "vt_fpr" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == ["vorec", "rtp", "lwcf"] and len(calls) == 3
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["rtp"],)))
    again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
    assert again["rtp"] == prior["rtp"]
    monkeypatch.setattr(hl, "get", site)
    assert [r.source_id for r in m.fetch(limit=2)] == ["vorec", "rtp"]
    assert m.resolve_missing("rtp") == {"status": "unknown"}


@pytest.mark.parametrize("name", AGENCIES)
def test_module_contract(name):
    m = mod(name)
    assert m.CONNECTOR == name and callable(m.fetch) and callable(m.normalize) and callable(m.resolve_missing)
    assert m.AGENCY_CODE.startswith("VT-") and m.CATEGORY_LABEL


def test_parenthetical_exclusion_is_not_a_negation():
    from connectors.maryland_drupal import NEGATION_RE
    assert not NEGATION_RE.search("Any Vermont town, city (except Burlington), incorporated village ... is eligible")
    assert not NEGATION_RE.search("Municipalities (excluding schools) may apply")
    assert NEGATION_RE.search("All towns except Burlington may apply")
    assert NEGATION_RE.search("Nonprofits (except those that are not 501c3) may apply")      # "not" still negates
    assert NEGATION_RE.search("Applicants are not eligible") and not NEGATION_RE.search("not-for-profit groups")
