"""The Mississippi Development Authority (ms_mda) against its saved Community Incentives page (12.9)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from connectors import ms_mda as m
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "ms_mda"
TODAY = date(2026, 11, 24)
SLUG = "community-incentives"


def html() -> str:
    return (FIX / f"{SLUG}.html").read_text(encoding="utf-8")


def every(page_html: str | None = None, today: date = TODAY) -> dict:
    page = m.parse_page(page_html or html())
    return {sid: m.normalize(RawRecord(source_connector="ms_mda", source_id=sid, payload=payload), today)
            for sid, payload in m.SITE.records_for(SLUG, m.PAGES[SLUG], [page], 0)}


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def test_eight_records_one_per_card_named_as_printed():
    got = every()
    assert {s: p.name for s, p in got.items()} == {
        SLUG: "Capital Improvements Revolving Loan Program (CAP)",          # the first card keeps the page's id
        f"{SLUG}#cdbg-public-facilities": "Community Development Block Grants (CDBG) for Public Facilities Projects",
        f"{SLUG}#smlpc": "Small Municipal and Limited Population Counties Grant Program",
        f"{SLUG}#airport-loan": "Airport Revitalization Revolving Loan Program",
        f"{SLUG}#freight-rail-loan": "Freight Rail Service Revolving Loan Program",
        f"{SLUG}#port-loan": "Port Revitalization Revolving Loan Program",
        f"{SLUG}#cdbg-economic-development": "Community Development Block Grants (CDBG) Economic Development Program",
        f"{SLUG}#dip": "Development Infrastructure Grant Program (DIP)",
    }
    for p in got.values():
        assert p.jurisdiction == "MS" and p.agency_code == "MS-MDA"
        assert p.source_url == "https://mississippi.org/community-resources/incentives/"


def test_only_the_cards_are_read_and_each_record_holds_its_own_card():
    page = m.parse_page(html())
    assert page["title"] == "Mississippi Community Incentives"
    assert [t for k, t in page["blocks"] if k == "label"][4] == "Mississippi Rail Grant Program"    # read, then left out
    joined = " ".join(t for _, t in page["blocks"])
    assert not any(w in joined for w in ("backbone of Mississippi business", "Newsletter", "Download", "Read More"))
    got = every()
    assert not any("railroads" in (p.summary or "") + (p.eligibility_text or "") for p in got.values())
    for sid, payload in m.SITE.records_for(SLUG, m.PAGES[SLUG], [page], 0):
        assert [k for k, _ in payload["page"]["blocks"]] == ["label", "p"], sid          # nothing shared, nothing borrowed
    assert got[f"{SLUG}#freight-rail-loan"].summary.startswith("Increased rail usage and productivity")
    assert got[f"{SLUG}#dip"].summary.startswith("DIP provides grants to municipalities and counties")   # stray quotes trimmed


def test_a_card_added_later_is_no_record_and_joins_no_other():
    added = html().replace('<h3 class="c-card__title">Freight Rail Service Revolving Loan Program</h3>',
                           '<h3 class="c-card__title">A Program Added Later</h3>')
    got = every(added)
    assert len(got) == 7 and f"{SLUG}#freight-rail-loan" not in got
    assert not any("Increased rail usage" in (p.summary or "") + (p.eligibility_text or "") for p in got.values())


def test_contact_sentences_are_removed_and_the_rest_of_the_paragraph_kept():
    blocks = m.parse_page(html())["blocks"]
    joined = " ".join(t for _, t in blocks)
    assert "601" not in joined and "Financial Resources Division" not in joined
    airport = every()[f"{SLUG}#airport-loan"]
    assert airport.summary == ("County and municipal airport authorities authorized to operate in Mississippi may apply for "
                               "loans for the airport authority or on behalf of a new or expanded industry.")


def test_status_types_and_sources():
    got = every()
    for p in got.values():
        assert (p.status, p.opens_at, p.closes_at, p.closes_at_text) == ("unknown", None, None, None)
    loans = {SLUG, f"{SLUG}#airport-loan", f"{SLUG}#freight-rail-loan", f"{SLUG}#port-loan"}
    assert {s for s, p in got.items() if p.funding_type == "loan"} == loans
    assert all(p.funding_type == "grant" for s, p in got.items() if s not in loans)
    federal = {f"{SLUG}#cdbg-public-facilities", f"{SLUG}#cdbg-economic-development"}
    assert {s for s, p in got.items() if p.funding_source == "pass_through"} == federal
    assert [c.value for c in got[SLUG].categories] == ["infrastructure"]
    assert [c.value for c in got[f"{SLUG}#freight-rail-loan"].categories] == ["transportation"]


def test_applicants_towns_and_counties_never_the_business_a_project_serves():
    got = every()
    for sid, p in got.items():
        assert {"municipality", "county"} <= tags(p), sid
        assert "business" not in tags(p), sid
    assert tags(got[f"{SLUG}#port-loan"]) == {"municipality", "county", "state"}
    assert got[SLUG].eligibility_text.startswith("CAP provides loans to municipalities and counties")
    assert "can be used by municipalities and counties" in got[f"{SLUG}#cdbg-economic-development"].eligibility_text
    assert "small municipalities (populations under 10,000)" in got[f"{SLUG}#smlpc"].eligibility_text


def test_fetch_and_fallback(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    calls: list[str] = []

    def site(client, url):
        calls.append(url)
        return html()

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert calls == ["https://mississippi.org/community-resources/incentives/"]          # one GET, never the pager's POST
    assert len(records) == 8 and records[0].source_id == SLUG
    prior = {r.source_id: r.payload for r in records}

    def down(client, url):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(hl, "get", down)
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)} == prior              # every stored card of the page
    assert m.fetch() == []
