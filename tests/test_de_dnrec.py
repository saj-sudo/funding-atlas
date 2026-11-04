"""Delaware DNREC Environmental Finance connector tests, against the twelve saved pages (never the network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import de_dnrec as de
from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "de_dnrec"
TODAY = date(2026, 11, 3)


def read(slug: str) -> str:
    return (FIX / f"{slug}.html").read_text(encoding="utf-8")


def normalize(slug: str, today: date = TODAY):
    return de.normalize(RawRecord(source_connector=de.CONNECTOR, source_id=slug, payload={"page": de.parse_page(read(slug))}), today)


def test_fixtures_carry_no_scripts_or_contacts():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "@delaware.gov" not in text.replace("example.delaware.gov", "")


def test_title_blocks_and_tags():
    page = de.parse_page(read("planning-advances"))
    assert page["title"] == "Project Planning Advances"
    assert ("label", "Eligible Applicants") in page["blocks"] and ("p", "Municipal governments") in page["blocks"]
    assert "clean water" in page["tags"] and not any("Related Topics" in t for _, t in page["blocks"])
    assert not any("000-000-0000" in t or "contact@" in t for _, t in page["blocks"])


def test_labelled_passage_and_applicant_sentences():
    p = normalize("planning-advances")
    assert "Municipal governments" in p.eligibility_text.split("\n")
    assert {t.value for t in p.applicant_types} == {"municipality"}
    p = normalize("wastewater-planning-grants")
    assert "Grant eligibility is limited to municipal and county government wastewater projects." in p.eligibility_text
    assert {"municipality", "county"} <= {t.value for t in p.applicant_types}


@pytest.mark.parametrize("slug, status, rolling", [
    ("community-water-quality-improvement", "open", None),      # "Now Accepting Project Proposals"
    ("asset-management", "open", True),                         # "submitted at any time ... first come, first served"
    ("planning-advances", "unknown", None),                     # "one application per state fiscal year"
    ("land-conservation", "unknown", None),                     # nothing
])
def test_status_and_rolling(slug, status, rolling):
    p = normalize(slug)
    assert (p.status, p.rolling) == (status, rolling)


def test_cycle_sentences():
    assert normalize("community-water-quality-improvement").closes_at_text == "Now Accepting Project Proposals"
    assert normalize("asset-management").closes_at_text.startswith("Applications can be submitted at any time")
    assert "one application per state fiscal year" in normalize("planning-advances").closes_at_text
    assert normalize("land-conservation").closes_at_text is None and normalize("land-conservation").closes_at is None


@pytest.mark.parametrize("sentence, closes_at, today, status", [
    ("Now Accepting Project Proposals", None, TODAY, "open"),
    ("Applications are due by March 1, 2027.", date(2027, 3, 1), TODAY, "open"),
    ("Applications are due by March 1, 2026.", date(2026, 3, 1), TODAY, "unknown"),
    ("The grant round is now closed.", None, TODAY, "closed"),
    (None, None, TODAY, "unknown"),
])
def test_status_for(sentence, closes_at, today, status):
    assert de.status_for(sentence, closes_at, today) == status


def test_kind_comes_from_the_index_section():
    assert normalize("asset-management").funding_type == "grant"
    assert normalize("wastewater-treatment").funding_type == "loan"
    assert normalize("non-point-source-funding").funding_type is None


def test_tags_become_categories_only_when_the_table_knows_them():
    pairs = normalize("planning-advances").category_pairs()
    assert ("water", "clean water") in pairs and ("water", "drinking water") in pairs and ("infrastructure", "infrastructure") in pairs
    assert not any(code in ("finance", "grants") for _, code in pairs)
    assert de.tag_categories(["finance", "grants"]) == []


def test_match_and_fields():
    p = normalize("wastewater-planning-grants")
    assert p.match_required is True                 # "1:1 cash match requirement"
    assert normalize("land-conservation").match_required is None
    assert p.source_url == "https://dnrec.delaware.gov/environmental-finance/wastewater-planning-grants/"
    assert (p.administering_agency, p.agency_code, p.jurisdiction, p.funding_source) == ("Department of Natural Resources and Environmental Control", "DE-DNREC", "DE", "direct")
    assert p.summary and p.eligibility_structured["topics"]


def test_property_owner_and_private_pages_tag_no_town():
    for slug in ("septic-rehabilitation", "estuary-programs"):
        assert not {"municipality", "county"} & {t.value for t in normalize(slug).applicant_types}


def test_every_page_normalizes():
    for slug in de.PAGES:
        p = normalize(slug)
        assert p.name and p.record_hash and p.categories


class _Pages:
    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        return read(url.rstrip("/").rsplit("/", 1)[-1])


def test_fetch_reads_every_page_and_falls_back(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    monkeypatch.setattr(hl, "get", _Pages())
    records = de.fetch()
    assert [r.source_id for r in records] == list(de.PAGES)
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", _Pages(broken={f"{de.BASE}asset-management/"}))
    assert {r.source_id: r.payload for r in de.fetch(prior=prior)}["asset-management"] == prior["asset-management"]
    assert "asset-management" not in {r.source_id for r in de.fetch()}
    monkeypatch.setattr(hl, "get", _Pages())
    assert len(de.fetch(limit=3)) == 3
    assert de.resolve_missing("asset-management") == {"status": "unknown"}
