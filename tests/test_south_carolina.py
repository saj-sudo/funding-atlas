"""South Carolina's agency connectors (sc_commerce, sc_ria) against saved pages (12.9)."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 24)
AGENCIES = ["sc_commerce", "sc_ria"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def fixture(name: str, slug: str, n: int = 0) -> str:
    return (FIX / name / (f"{slug}.html" if n == 0 else f"{slug}.{n + 1}.html")).read_text(encoding="utf-8")


def pages(name: str, slug: str) -> list[dict]:
    m = mod(name)
    return [m.SITE.parse_page(fixture(name, slug, n)) for n, _ in enumerate(m.SITE.urls_for(slug, m.PAGES[slug]))]


def every(name: str, today: date = TODAY) -> dict:
    m = mod(name)
    out: dict = {}
    for slug, spec in m.PAGES.items():
        for sid, payload in m.SITE.records_for(slug, spec, pages(name, slug), 0):
            out[sid] = m.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def texts(name: str, slug: str, n: int = 0) -> list[str]:
    return [t for _, t in pages(name, slug)[n]["blocks"]]


def test_commerce_nine_records_named_from_the_pages():
    progs = every("sc_commerce")
    assert list(progs) == ["cdbg", "cdbg#community-enrichment", "cdbg#local-priorities", "cdbg#business-development",
                           "cdbg#ready-to-go", "arc", "arc#local-access-road", "scrc", "rdi"]
    assert progs["cdbg"].name == "Community Development Block Grant (CDBG): Community Infrastructure"
    assert progs["cdbg#ready-to-go"].name == "Community Development Block Grant (CDBG): Ready to Go"
    assert progs["scrc"].name == "Southeast Crescent Regional Commission (SCRC)"   # the h1's <strong>, not its tagline
    assert progs["rdi"].name == "Rural Development Initiative (RDI)"
    assert progs["arc#local-access-road"].name.endswith("Local Access Road Program (LAR)")
    for sid, p in progs.items():
        assert p.jurisdiction == "SC" and p.agency_code == "SC-COMMERCE", sid
    # every CDBG record points at the program page, not the how-to-apply page
    assert progs["cdbg#local-priorities"].source_url.endswith("/community-development-block-grant-cdbg")
    assert progs["arc#local-access-road"].source_url.endswith("/appalachian-regional-commission-arc")


def test_commerce_where_the_read_stops_and_what_is_dropped():
    cdbg = texts("sc_commerce", "cdbg")
    assert any(t.startswith("Only units of general local government") for t in cdbg)
    assert not any("National objectives" in t or "public hearing" in t.lower() or "Office of Resilience" in t for t in cdbg)
    assert "Breadcrumb" not in cdbg and "Home" not in cdbg
    apply = texts("sc_commerce", "cdbg", 1)
    assert "Rolling applications" in apply
    assert not any("Why is an application request" in t or "Housing Finance" in t for t in apply)
    for slug in mod("sc_commerce").PAGES:
        for n in range(len(pages("sc_commerce", slug))):
            assert not any("@" in t or "protected]" in t or "(803)" in t or "803-" in t for t in texts("sc_commerce", slug, n))
    assert not any("Questions about" in t for t in texts("sc_commerce", "rdi"))
    assert not any("Find incentives" in t or "ARC forms" in t for t in texts("sc_commerce", "arc"))


def test_commerce_cdbg_each_category_takes_its_own_round():
    progs = every("sc_commerce")
    # The application request is required before the application, so its deadline governs; both 2026 rounds are past.
    ci = progs["cdbg"]
    assert (ci.status, ci.closes_at) == ("unknown", date(2026, 3, 20))
    assert ci.closes_at_text.startswith("Application request deadline: March 20, 2026")
    for sid in ("cdbg#community-enrichment", "cdbg#local-priorities"):
        assert (progs[sid].status, progs[sid].closes_at) == ("unknown", date(2026, 8, 21)), sid
    for sid in ("cdbg#business-development", "cdbg#ready-to-go"):
        p = progs[sid]
        assert (p.status, p.rolling, p.closes_at) == ("open", True, None), sid
        assert "may be submitted at any time" in p.closes_at_text
    # the same pages read before the spring round's request deadline
    early = every("sc_commerce", date(2026, 3, 1))
    assert early["cdbg"].status == "open" and early["cdbg#community-enrichment"].status == "open"
    # a category's record does not carry another round's lines
    blocks = [t for _, t in mod("sc_commerce").SITE.records_for("cdbg", mod("sc_commerce").PAGES["cdbg"],
                                                                pages("sc_commerce", "cdbg"), 0)[0][1]["page"]["blocks"]]
    assert not any("August 21, 2026" in t or "at any time" in t for t in blocks)


def test_commerce_status_of_the_other_pages():
    progs = every("sc_commerce")
    arc = progs["arc"]
    assert (arc.status, arc.closes_at, arc.closes_at_text) == ("unknown", None, "Application timelines and deadlines vary by funding cycle.")
    lar = progs["arc#local-access-road"]
    assert (lar.status, lar.rolling) == ("open", True) and "anytime throughout the year" in lar.closes_at_text
    scrc = progs["scrc"]
    assert (scrc.status, scrc.closes_at_text) == ("closed", "There is no open SCRC funding opportunity at this time.")
    # RDI's heading still says "Applications are now open"; its dated deadline has passed and outranks it.
    rdi = progs["rdi"]
    assert (rdi.status, rdi.closes_at) == ("unknown", date(2026, 10, 30))
    assert rdi.closes_at_text == "Application deadline: 5 pm Oct. 30, 2026"
    assert every("sc_commerce", date(2026, 10, 1))["rdi"].status == "open"


def test_commerce_funding_source_match_and_applicants():
    progs = every("sc_commerce")
    assert {sid: p.funding_source for sid, p in progs.items() if "#" not in sid} == {
        "cdbg": "pass_through", "arc": "pass_through", "scrc": "pass_through", "rdi": "direct"}
    assert progs["rdi"].match_required is True and progs["arc"].match_required is True
    for sid in ("cdbg", "cdbg#business-development", "rdi"):
        assert tags(progs[sid]) == {"municipality", "county"}, sid
    assert "fewer than 20,000 residents" in progs["rdi"].eligibility_text   # kept in the text, not tagged as households
    assert tags(progs["scrc"]) == {"municipality", "county", "state", "tribe", "nonprofit"}
    # ARC's lists name "Government entities" and "governmental entities": the shared tagger has no rule for them.
    assert "Local governing boards" in progs["arc"].eligibility_text and tags(progs["arc"]) == {"nonprofit"}
    assert progs["arc#local-access-road"].eligibility_text == "Applicants are limited to governmental entities"
    assert all(p.categories[0].value == "infrastructure" for p in progs.values())


def test_ria_six_records():
    progs = every("sc_ria")
    assert list(progs) == ["grants", "grants#economic-infrastructure", "grants#emergencies", "grants#regional-planning", "loans", "vip"]
    assert progs["grants"].name == "RIA State Grants: Basic Infrastructure"
    assert progs["loans"].name == "State Revolving Fund (SRF) Loans" and progs["loans"].funding_type == "loan"
    assert progs["vip"].name == "Viability Improvement Program"
    for sid, p in progs.items():
        assert p.jurisdiction == "SC" and p.agency_code == "SC-RIA" and p.source_url.startswith("https://ria.sc.gov/"), sid
        assert p.categories[0].value == "water", sid
    assert progs["grants#regional-planning"].source_url == "https://ria.sc.gov/grants/"
    assert progs["grants"].summary.startswith("The Basic Infrastructure program is designed")


def test_ria_where_the_read_stops_and_what_is_dropped():
    grants = texts("sc_ria", "grants")
    assert "Regional Planning" in grants and "Program Strategy" not in grants and "City of Camden" not in grants
    apply = texts("sc_ria", "grants", 1)
    # the deadline paragraph and the dates under it are one line
    assert "The application deadlines for RIA grants in FY27 are: September 14, 2026 and March 22, 2027." in apply
    assert not any("Application Process" in t or "10 weeks" in t for t in apply)
    vip = texts("sc_ria", "vip")
    assert not any("@" in t or "(803)" in t or "please contact" in t.lower() for t in vip)
    assert "Program Description" not in vip
    assert "Interest Rates" not in texts("sc_ria", "loans")


def test_ria_status_the_cycle_ahead_and_the_rolling_programs():
    progs = every("sc_ria")
    for sid in ("grants", "grants#economic-infrastructure", "grants#regional-planning"):
        assert (progs[sid].status, progs[sid].closes_at) == ("open", date(2027, 3, 22)), sid
    assert every("sc_ria", date(2026, 9, 1))["grants"].closes_at == date(2026, 9, 14)
    late = every("sc_ria", date(2027, 4, 1))["grants"]
    assert (late.status, late.closes_at) == ("unknown", date(2027, 3, 22))
    # Emergencies "may be submitted at any time": it does not take the two deadlines
    em = progs["grants#emergencies"]
    assert (em.status, em.rolling, em.closes_at) == ("open", True, None)
    assert "may be submitted at any time for Tier 3 & 4 counties" in em.closes_at_text
    loans = progs["loans"]
    assert (loans.status, loans.rolling, loans.closes_at) == ("open", True, None)
    assert loans.closes_at_text.startswith("Project requests may be submitted at any time")
    assert (progs["vip"].status, progs["vip"].closes_at_text) == ("unknown", None)


def test_ria_each_program_keeps_only_its_own_lines():
    m = mod("sc_ria")
    records = dict(m.SITE.records_for("grants", m.PAGES["grants"], pages("sc_ria", "grants"), 0))

    def lines(sid: str) -> list[str]:
        return [t for _, t in records[sid]["page"]["blocks"]]

    assert any(t.startswith("Regional Planning Grant : No match required") for t in lines("grants#regional-planning"))
    assert not any(t.startswith("Regional Planning Grant") for t in lines("grants"))
    assert not any(t.startswith("Basic & Economic Infrastructure") for t in lines("grants#regional-planning"))
    assert not any(t.startswith("Basic & Economic") or "deadlines" in t for t in lines("grants#emergencies"))
    progs = every("sc_ria")
    assert progs["grants"].match_required is True and progs["grants#economic-infrastructure"].match_required is True
    assert progs["grants#regional-planning"].match_required is None and progs["grants#emergencies"].match_required is None


def test_ria_funding_source_and_applicants():
    progs = every("sc_ria")
    assert {sid: p.funding_source for sid, p in progs.items() if "#" not in sid} == {
        "grants": "direct", "loans": "pass_through", "vip": "direct"}
    for sid in ("grants", "grants#emergencies", "vip"):
        assert tags(progs[sid]) == {"municipality", "county"}, sid
    assert progs["grants"].eligibility_text.startswith("Local governments, special purpose and public service districts")
    assert "Public water and wastewater utilities are eligible to apply." in progs["grants#regional-planning"].eligibility_text
    # the SRF sentence the shared reader does not know; the "Federal requirements ... may apply" line is not an applicant
    assert tags(progs["loans"]) == {"municipality", "county", "special_district"}
    assert progs["loans"].eligibility_text.startswith("Low-interest loans are made available to municipalities")
    assert "Federal requirements" not in progs["loans"].eligibility_text
    assert "not eligible for this pilot program" in progs["vip"].eligibility_text


def test_fetch_and_fallback(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    for name in AGENCIES:
        m = mod(name)
        urls = {url: (slug, n) for slug, spec in m.PAGES.items() for n, url in enumerate(m.SITE.urls_for(slug, spec))}

        def site(client, url, broken=(), name=name, urls=urls):
            if url in broken:
                raise httpx.ConnectError("down")
            return fixture(name, *urls[url])

        monkeypatch.setattr(hl, "get", site)
        records = m.fetch()
        assert [r.source_id for r in records] == list(every(name)), name
        assert len(m.fetch(limit=2)) == 2
        prior = {r.source_id: r.payload for r in records}
        # the second page of the first slug is down: every record of that slug comes from the stored copy
        first = next(iter(m.PAGES))
        down = m.SITE.urls_for(first, m.PAGES[first])[-1]
        monkeypatch.setattr(hl, "get", lambda c, u, down=down, site=site: site(c, u, broken=(down,)))
        again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
        assert again == prior, name
        assert [r.source_id for r in m.fetch()] == [sid for sid in prior if sid != first and not sid.startswith(first + "#")]
