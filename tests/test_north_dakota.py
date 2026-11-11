"""North Dakota's four agency connectors (nd_commerce, nd_dot, nd_des, nd_parks) and their base, against saved pages."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from connectors import north_dakota_drupal as nd
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 11)
AGENCIES = ["nd_commerce", "nd_dot", "nd_des", "nd_parks"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def page(name: str, slug: str) -> dict:
    return mod(name).SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))


def program(name: str, slug: str, today: date = TODAY):
    m = mod(name)
    raw = RawRecord(source_connector=name, source_id=slug, payload={"path": m.PAGES[slug], "page": page(name, slug)})
    return m.normalize(raw, today)


def tags(name: str, slug: str) -> set[str]:
    return {t.value for t in program(name, slug).applicant_types}


def text(name: str, slug: str) -> str:
    return " ".join(t for _, t in page(name, slug)["blocks"])


def test_every_page_reads():
    for name in AGENCIES:
        m = mod(name)
        for slug in m.PAGES:
            p = program(name, slug)
            assert p.name and p.jurisdiction == "ND" and p.source_url.startswith(m.BASE), (name, slug)
            assert page(name, slug)["blocks"], (name, slug)


def test_reader_drops_contacts_and_stops_at_past_awards():
    ta = text("nd_dot", "transportation-alternatives")
    assert "Eligible Project Applicants" in ta and "Phone:" not in ta
    assert "Lake Metigoshe" not in ta                                     # 2026's awarded projects, after "Prior Year Projects"
    assert "Beaver Lake Road" not in text("nd_dot", "special-road-fund")  # "2026 Awarded Projects"
    assert "701.328.8100" not in text("nd_des", "public-assistance")       # DES's address block
    assert "Copy Link" not in text("nd_parks", "lwcf")
    # "<li><strong>Eligible Entities</strong> – City, ...": the bold label stays with its item.
    assert ("li", "Eligible Entities – City, County, Economic Development organization (JDA, regional Councils, EDC, "
            "CVB) and local tribal entities") in page("nd_commerce", "workforce-housing")["blocks"]
    # A short paragraph ending in a colon labels the list after it.
    assert ("label", "The following entities are eligible to apply:") in page("nd_parks", "lwcf")["blocks"]


def test_status():
    cases = {
        ("nd_commerce", "vibrancy"): ("closed", None),
        ("nd_commerce", "rural-catalyst"): ("closed", None),
        ("nd_commerce", "rural-grocery"): ("closed", None),      # its dates carry no year and are not read
        ("nd_commerce", "partners-in-planning"): ("unknown", None),
        ("nd_dot", "flex-fund"): ("unknown", date(2025, 9, 19)),
        ("nd_dot", "transportation-alternatives"): ("unknown", None),
        ("nd_dot", "urban-grant"): ("open", date(2026, 12, 31)),
        ("nd_dot", "special-road-fund"): ("unknown", None),
        ("nd_des", "public-assistance"): ("unknown", None),
        ("nd_des", "hazard-mitigation"): ("unknown", None),
        ("nd_parks", "lwcf"): ("unknown", None),                 # "Next grant round opens: TBD"
        ("nd_parks", "rtp"): ("unknown", None),
    }
    for (name, slug), want in cases.items():
        p = program(name, slug)
        assert (p.status, p.closes_at) == want, (name, slug)
    assert program("nd_dot", "urban-grant", date(2027, 1, 4)).status == "unknown"
    assert program("nd_dot", "flex-fund", date(2025, 9, 1)).status == "open"


def test_submitted_by_needs_an_application():
    # TA's construction milestone is not a deadline; Connecticut DEEP's application sentence still is.
    assert hl.deadline(["Therefore, final plans, permits, certifications, etc., need to be completed and submitted by "
                        "January 1, 2028, and will be scheduled to be bid in the spring of 2028."]) == (None, None)
    assert hl.deadline(["Applications must be submitted by November 6, 2026"])[1] == date(2026, 11, 6)


def test_applicants():
    for slug in ("slum-blight", "workforce-housing", "facility-planning", "rural-catalyst", "rural-grocery"):
        assert tags("nd_commerce", slug) == {"municipality", "county", "tribe"}, slug
    assert tags("nd_commerce", "vibrancy") == {"nonprofit"}             # "local political entities" tags nothing
    assert tags("nd_commerce", "artists-on-main-street") == set()       # applicants only in its guidelines PDF
    assert tags("nd_dot", "flex-fund") == {"municipality", "county"}     # townships tag as municipality
    assert tags("nd_dot", "transportation-alternatives") == {"municipality", "county", "school", "tribe"}
    assert tags("nd_dot", "urban-grant") == {"municipality"}
    assert tags("nd_dot", "special-road-fund") == {"municipality", "county", "tribe", "state"}
    assert tags("nd_des", "public-assistance") == {"tribe"}
    assert tags("nd_des", "hazard-mitigation") == set()
    assert tags("nd_parks", "lwcf") == {"municipality", "county", "school", "state", "tribe"}
    assert tags("nd_parks", "rtp") == {"municipality", "county", "nonprofit", "tribe"}


def test_categories_funding_source_and_match():
    assert program("nd_commerce", "rural-catalyst").category_pairs() == [("infrastructure", "community development")]
    assert program("nd_dot", "urban-grant").category_pairs() == [("transportation", "transportation")]
    assert program("nd_des", "hazard-mitigation").category_pairs() == [("public_safety", "emergency management")]
    assert program("nd_parks", "rtp").category_pairs() == [("parks", "parks and recreation")]
    for name, slug in [("nd_dot", "transportation-alternatives"), ("nd_dot", "urban-grant"), ("nd_des", "public-assistance"),
                       ("nd_parks", "lwcf"), ("nd_parks", "rtp")]:
        assert program(name, slug).funding_source == "pass_through", slug
    for name, slug in [("nd_dot", "flex-fund"), ("nd_dot", "special-road-fund"), ("nd_commerce", "rural-catalyst")]:
        assert program(name, slug).funding_source == "direct", slug
    assert program("nd_commerce", "rural-catalyst").match_required is True
    assert program("nd_commerce", "facility-planning").match_required is None   # "Minimum of a 10% match" says no "required"


def test_fetch_and_fallback(monkeypatch):
    m = mod("nd_parks")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / "nd_parks" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == ["lwcf", "rtp"]
    assert [r.source_id for r in m.fetch(limit=1)] == ["lwcf"]
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["lwcf"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["lwcf"] == prior["lwcf"]
    assert m.resolve_missing("lwcf") == {"status": "unknown"}


def test_base_without_a_body():
    assert nd.parse_page("<html><h1>Gone</h1></html>") == {"title": "Gone", "blocks": []}


@pytest.mark.parametrize("name", AGENCIES)
def test_module_contract(name):
    m = mod(name)
    assert m.CONNECTOR == name and m.AGENCY_CODE.startswith("ND-") and m.CATEGORY_LABEL
    assert callable(m.fetch) and callable(m.normalize) and callable(m.resolve_missing)
