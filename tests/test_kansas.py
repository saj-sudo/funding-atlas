"""Kansas Department of Commerce (ks_commerce) against saved pages (12.9)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from connectors import ks_commerce as m
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "ks_commerce"
TODAY = date(2026, 11, 24)


def html(slug: str) -> str:
    return (FIX / f"{slug}.html").read_text(encoding="utf-8")


def page(slug: str) -> dict:
    return m.parse_page(html(slug))


def program(slug: str, page_html: str | None = None, today: date = TODAY):
    payload = {"path": m.PAGES[slug], "page": m.parse_page(page_html or html(slug))}
    return m.normalize(RawRecord(source_connector="ks_commerce", source_id=slug, payload=payload), today)


def every(today: date = TODAY) -> dict:
    return {slug: program(slug, today=today) for slug in m.PAGES}


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def test_ten_records_named_from_the_hero_headline():
    progs = every()
    assert {sid: p.name for sid, p in progs.items()} == {
        "large-grants": "CDBG Community Facilities: Large Grants",
        "small-grants": "CDBG Community Facilities: Small Grants",
        "water-sewer": "CDBG Water & Sewer Infrastructure",
        "commercial-rehab": "CDBG Commercial Rehabilitation",              # "COMMERCIAL REHABILITATION" on the page
        "blueprint-to-build": "CDBG Blueprint to Build",
        "housing": "CDBG Housing Rehabilitation & Demolition",
        "youth-job-training": "CDBG Youth Job Training",
        "economic-development": "CDBG Economic Development",
        "regional-water": "CDBG Regional Water Implementation",
        "urgent-need": "CDBG Urgent Need for Disasters",
    }
    assert all(p.jurisdiction == "KS" and p.agency_code == "KS-COMMERCE" for p in progs.values())
    assert progs["water-sewer"].source_url == "https://www.kansascommerce.gov/cdbg/water-sewer/"
    assert progs["water-sewer"].summary.startswith("This program supports efforts to ensure reliable, safe, and sustainable water")


def test_the_strip_reads_as_lines_and_the_read_stops_before_the_faqs():
    texts = [t for _, t in page("water-sewer")["blocks"]]
    assert "MAX AWARD: Up to $2,000 per beneficiary with a maximum of $800,000" in texts
    assert "MATCH: 25% of the CDBG grant request" in texts and "APPLICATIONS CLOSED: Closed for 2026" in texts
    assert ("label", "Qualify") in page("water-sewer")["blocks"] and "Approved Pre-Application" in texts
    assert "CDBG Interior Page" not in texts and "Program Overview" not in texts
    # two pages leave a tag open, so their overview section holds the FAQs and "How to Apply" in the markup
    for slug in m.PAGES:
        text = " ".join(t for _, t in page(slug)["blocks"])
        for gone in ("Citizen participation", "Community Showcase", "Find Assistance", "Have Questions", "LMI help",
                     "Get notifications", "Blueprint to Build FAQ", "Small Design"):
            assert gone not in text, (slug, gone)
        assert ("label", "Matching Funds") in page(slug)["blocks"], slug
        assert "@" not in text and "785-" not in text, slug


def test_every_round_is_closed_today():
    for sid, p in every().items():
        assert (p.status, p.opens_at, p.closes_at) == ("closed", None, None), sid
        assert p.closes_at_text == "Applications for 2026 are closed.", sid


def test_a_dated_deadline_cell_would_read_as_a_round():
    # Not seen live: the shape the strip's third cell would take when a round is on (a commented-out date sits there today).
    changed = (html("water-sewer").replace("APPLICATIONS CLOSED", "APPLICATION DEADLINE").replace("Closed for 2026", "May 1, 2027")
               .replace("Applications for 2026 are closed.", "Applications for 2027 are being accepted."))
    p = program("water-sewer", changed)
    assert (p.status, p.closes_at) == ("open", date(2027, 5, 1))
    assert p.closes_at_text == "APPLICATION DEADLINE: May 1, 2027"
    assert program("water-sewer", changed, today=date(2027, 6, 1)).status == "unknown"


def test_funding_match_and_categories():
    progs = every()
    assert all(p.funding_source == "pass_through" for p in progs.values())
    assert {sid: p.funding_type for sid, p in progs.items() if p.funding_type != "grant"} == {"economic-development": "loan"}
    # Urgent Need's match is "Cost of the environmental review": neither rule speaks, so null
    assert {sid: p.match_required for sid, p in progs.items() if p.match_required is not True} == {"urgent-need": None}
    cats = {sid: [c.value for c in p.categories] for sid, p in progs.items()}
    assert cats["water-sewer"] == ["water"] and cats["regional-water"] == ["water"] and cats["housing"] == ["housing"]
    assert cats["youth-job-training"] == ["workforce"] and cats["large-grants"] == ["infrastructure"]


def test_applicants():
    progs = every()
    for sid in ("large-grants", "small-grants", "water-sewer", "regional-water", "urgent-need"):
        assert tags(progs[sid]) == {"municipality", "county"}, sid
        assert progs[sid].eligibility_text.startswith("Only cities and counties (units of local government) can apply")
        assert "NOT eligible to apply for the state CDBG program: Kansas City" in progs[sid].eligibility_text
    # "Only cities (not counties) can apply for the Housing Rehabilitation and Demolition Grant."
    assert tags(progs["housing"]) == {"municipality"}
    # the second paragraph under the label is about the building or the business assisted: not an applicant
    for sid in ("commercial-rehab", "economic-development"):
        assert tags(progs[sid]) == {"municipality", "county"}, sid
        assert "Eligible Properties" not in progs[sid].eligibility_text and "Eligible Businesses" not in progs[sid].eligibility_text
    # two pages have no "Eligible Applicants" section: the hub's sentence, dated and attributed
    for sid in ("blueprint-to-build", "youth-job-training"):
        assert tags(progs[sid]) == {"municipality", "county"}, sid
        assert progs[sid].eligibility_text.startswith("Kansas Commerce CDBG page (www.kansascommerce.gov/cdbg/), read 2026-11-24: ")
        assert "excluding the federal entitlement areas" in progs[sid].eligibility_text


def test_fetch_waits_ten_seconds_and_falls_back(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", slept.append)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return html(slug)

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == list(m.PAGES)
    assert slept == [10.0] * 9                                   # the site's Crawl-delay
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["housing"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["housing"] == prior["housing"]
    assert "housing" not in [r.source_id for r in m.fetch(prior={})]
