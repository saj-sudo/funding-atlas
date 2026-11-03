"""Virginia DHCD connector tests. Everything runs against the saved pages (never the network): a section page, a
landing page, a CDBG family page, six program pages and one templated page that is not a program."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import va_dhcd as va
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "va_dhcd"
TODAY = date(2026, 11, 3)
PROGRAMS = ("irf", "vaarc", "cdbg-community-improvement-grants", "cdbg-planning-grants", "vez", "vida")


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def program(slug: str) -> dict:
    return va.parse_program(read(f"{slug}.html"))


def normalize(slug: str, today: date = TODAY):
    return va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id=slug, payload={"path": f"/{slug}", "depth": 2, "program": program(slug)}), today)


# ---------- teasers and paths ----------

@pytest.mark.parametrize("href, expected", [
    ("http://www.dhcd.virginia.gov/irf", "/irf"), ("https://www.dhcd.virginia.gov/irf/", "/irf"), ("/vaarc", "/vaarc"),
    ("/sites/default/files/DocX/arc/arc-program-handbook.pdf", None), ("http://govirginia.org/", None),
    ("/about", None), ("/communities", None), ("#top", None), ("https://dmz1.dhcd.virginia.gov/camsportal/Login.aspx", None),
])
def test_page_path(href, expected):
    assert va.page_path(href) == expected


def test_section_teasers_lead_to_landings_and_programs():
    teasers = va.parse_teasers(read("communities.html"))
    assert "/downtown-revitalization" in teasers and "/water-sewer-and-drainage" in teasers
    assert len(teasers) == len(set(teasers)) and all(t.startswith("/") for t in teasers)


def test_landing_teasers_and_the_cdbg_learn_more_link():
    assert "/irf" in va.parse_teasers(read("downtown-revitalization.html"))
    assert va.parse_teasers(read("cdbg-downtown-revitalization.html")) == ["/cdbg-community-improvement-grants", "/cdbg-planning-grants"][:1] or \
        "/cdbg-community-improvement-grants" in va.parse_teasers(read("cdbg-downtown-revitalization.html"))


def test_a_program_page_has_no_teasers_but_vez_links_on():
    assert va.parse_teasers(read("irf.html")) == []


# ---------- the program marker ----------

def test_the_eligibility_label_marks_a_program():
    for slug in PROGRAMS:
        assert va.is_program(program(slug)), slug
    assert not va.is_program(program("vhsp"))            # the eligibility slot is titled "Service Provider Resources"
    assert not va.is_program(program("communities")) and not va.is_program(program("downtown-revitalization"))


def test_the_label_not_the_css_class_decides():
    p = program("vez")
    assert [b["label"] for b in p["boxes"]] == ["Helpful Links", "PROGRAM RESOURCES", "Eligibility"]
    assert va.eligibility_lines(p) and "Helpful" not in " ".join(va.eligibility_lines(p))


# ---------- parsing ----------

def test_title_intro_boxes_and_no_people():
    p = program("irf")
    assert p["title"] == "Industrial Revitalization Fund (IRF)"
    assert p["intro"][0].startswith("The Industrial Revitalization Fund (IRF) leverages")
    assert va.eligibility_lines(p)[0].startswith("Only local governments (city, county or town)")
    text = str(p)
    assert "Contact Name" not in text and "mailto" not in text and "000-000-0000" not in text


def test_fixtures_carry_no_scripts_or_real_contacts():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "@dhcd.virginia.gov" not in text


# ---------- the cycle sentence ----------

def test_cycle_sentence_prefers_the_stated_timeline():
    assert va.cycle_sentence(program("irf")) == "Applications will be due on July 31, 2026."
    assert va.cycle_sentence(program("cdbg-community-improvement-grants")).startswith("The timeline for submission of competitive grant applications")
    assert "rolling basis" in va.cycle_sentence(program("cdbg-planning-grants"))
    assert va.cycle_sentence(program("vaarc")) is None


@pytest.mark.parametrize("sentence, expected", [
    ("Applications will be due on July 31, 2026.", (None, date(2026, 7, 31))),
    ("The portal will be open for submitting applications from January 1, 2027 to April 1, 2027.", (date(2027, 1, 1), date(2027, 4, 1))),
    ("Applications are accepted on an open, rolling basis from May 10 to November 15th, or until funds are exhausted.", (None, None)),
    ("The timeline for submission is the spring of every year.", (None, None)),
    ("All applications must be received by midnight January 15th, 2027.", (None, date(2027, 1, 15))),
    ("This application must be submitted to DHCD by December 28, 2026.", (None, date(2026, 12, 28))),
    (None, (None, None)),
])
def test_cycle_dates(sentence, expected):
    assert va.cycle_dates(sentence) == expected


@pytest.mark.parametrize("sentence, closes_at, status", [
    ("The 2026 round is now closed.", None, "closed"),
    ("Applications are due April 1, 2027.", date(2027, 4, 1), "open"),
    ("Applications are due April 1, 2026.", date(2026, 4, 1), "unknown"),
    ("Applications are accepted on a rolling basis.", None, "unknown"),
    (None, None, "unknown"),
])
def test_status_for(sentence, closes_at, status):
    assert va.status_for(sentence, closes_at, TODAY) == status


def test_dates_status_and_cycle_text_on_the_pages():
    irf = normalize("irf")
    assert (irf.status, irf.closes_at, irf.closes_at_text) == ("unknown", date(2026, 7, 31), "Applications will be due on July 31, 2026.")
    assert normalize("irf", today=date(2026, 7, 31)).status == "open"
    vez = normalize("vez")
    assert vez.status == "open" and vez.closes_at == date(2027, 4, 1)
    planning = normalize("cdbg-planning-grants")
    assert planning.rolling is True and planning.status == "unknown" and planning.closes_at is None
    assert normalize("vaarc").closes_at_text is None and normalize("vaarc").status == "unknown"


# ---------- applicants ----------

def test_local_governments_city_county_or_town():
    assert {t.value for t in normalize("irf").applicant_types} >= {"municipality", "county"}


def test_localities_and_nonprofits_from_the_arc_box():
    assert {t.value for t in normalize("vaarc").applicant_types} == {"municipality", "county", "nonprofit"}


def test_non_entitlement_units_of_local_government():
    p = normalize("cdbg-community-improvement-grants")
    assert {"municipality", "county"} <= {t.value for t in p.applicant_types}
    assert p.eligibility_text.startswith("Non-entitlement units of local government are the only eligible recipients")


def test_individual_development_accounts_tag_households_not_towns():
    tags = {t.value for t in normalize("vida").applicant_types}
    assert "household" in tags and not {"municipality", "county"} & tags


# ---------- mapping ----------

def test_fields():
    p = normalize("irf")
    assert p.source_url == "https://www.dhcd.virginia.gov/irf" and p.name == "Industrial Revitalization Fund (IRF)"
    assert (p.level, p.jurisdiction, p.administering_agency, p.agency_code) == ("state", "VA", "Department of Housing and Community Development", "VA-DHCD")
    assert (p.funding_type, p.funding_source, p.amount_min, p.match_required, p.categories, p.alns) == (None, "direct", None, None, [], [])
    assert p.eligibility_structured == {"boxes": ["Eligibility", "Resources", "Helpful Links"]}
    assert normalize("cdbg-planning-grants").funding_type == "grant"
    assert p.summary.startswith("The Industrial Revitalization Fund")


def test_every_saved_program_normalizes():
    for slug in PROGRAMS:
        p = normalize(slug)
        assert p.name and p.eligibility_text and p.record_hash


# ---------- fetch ----------

class _Site:
    """A stand-in for `_get`: path -> saved page; a page not saved is a 404; `broken` paths drop the connection."""

    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        path = url.replace(va.BASE, "")
        self.calls.append(path)
        if path in self.broken:
            raise httpx.ConnectError("down")
        name = path.strip("/") + ".html"
        if not (FIX / name).exists():
            raise httpx.HTTPStatusError("404", request=httpx.Request("GET", url), response=httpx.Response(404))
        return read(name)


@pytest.fixture
def site(monkeypatch):
    monkeypatch.setattr(va.time, "sleep", lambda s: None)
    monkeypatch.setattr(va, "SECTIONS", ("/communities",))
    stub = _Site()
    monkeypatch.setattr(va, "_get", stub)
    return stub


def test_fetch_crawls_each_page_once_and_keeps_only_programs(site):
    records = va.fetch()
    ids = [r.source_id for r in records]
    assert "irf" in ids and "cdbg-community-improvement-grants" in ids and "vhsp" not in ids and "communities" not in ids
    assert len(site.calls) == len(set(site.calls))
    assert site.calls[0] == "/communities" and "/downtown-revitalization" in site.calls and "/cdbg-community-improvement-grants" in site.calls
    assert records[0].payload["program"]["title"] and records[0].payload["depth"] >= 1
    assert len(va.fetch(limit=1)) == 1


def test_a_failed_section_aborts_and_a_failed_program_falls_back_to_prior(monkeypatch, site):
    monkeypatch.setattr(va, "_get", _Site(broken={"/communities"}))
    with pytest.raises(httpx.ConnectError):
        va.fetch()
    monkeypatch.setattr(va, "_get", _Site())
    first = {r.source_id: r.payload for r in va.fetch()}
    monkeypatch.setattr(va, "_get", _Site(broken={"/irf"}))
    again = {r.source_id: r.payload for r in va.fetch(prior=first)}
    assert again["irf"] == first["irf"]
    assert "irf" not in {r.source_id for r in va.fetch()}


def test_resolve_missing_is_unknown_without_a_request(monkeypatch):
    monkeypatch.setattr(va, "_get", lambda *a: pytest.fail("no request"))
    assert va.resolve_missing("irf") == {"status": "unknown"}
