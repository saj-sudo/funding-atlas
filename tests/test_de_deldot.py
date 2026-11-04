"""Delaware DelDOT connector tests, against the three saved pages (never the network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import de_deldot as de
from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "de_deldot"
TODAY = date(2026, 11, 3)


def read(name: str) -> str:
    return (FIX / f"{name}.html").read_text(encoding="utf-8")


def normalize(slug: str, today: date = TODAY):
    paths = de.PAGES[slug]
    pages = [de.parse_page(read(f"{slug}_{j}")) for j in range(len(paths))]
    return de.normalize(RawRecord(source_connector=de.CONNECTOR, source_id=slug, payload={"paths": list(paths), "pages": pages}), today)


def test_fixtures_carry_no_scripts_or_contacts():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "302.760" not in text


def test_title_from_the_title_tag_not_the_banner_h1():
    assert de.parse_page(read("tap_0"))["title"] == "Transportation Alternatives Program - TAP"
    assert de.parse_page(read("srts_0"))["title"] == "Safe Routes to School Program"


def test_sponsor_list_under_its_label():
    p = normalize("tap")
    lines = p.eligibility_text.split("\n")
    assert "Local Governments" in lines and "Non-Profits" in lines and "School Districts and local education agencies" in lines
    assert {"municipality", "county", "nonprofit", "school"} <= {t.value for t in p.applicant_types}


def test_call_out_date_on_a_stale_page_is_unknown():
    p = normalize("tap")
    assert p.closes_at_text.startswith("2026 Project Call-Out for New TAP Applications - deadline April 17th, 2026")
    assert p.closes_at == date(2026, 4, 17) and p.status == "unknown"
    assert normalize("tap", today=date(2026, 4, 1)).status == "open"


def test_federal_wording_and_match():
    p = normalize("tap")
    assert p.funding_source == "pass_through" and p.match_required is True      # "up to 80% of a project"


def test_safe_routes_names_schools_only():
    p = normalize("srts")
    assert {t.value for t in p.applicant_types} == {"school"}
    assert p.status == "unknown" and p.closes_at_text is None


def test_fields():
    p = normalize("tap")
    assert p.source_url == "https://deldot.gov/Programs/tap/"
    assert (p.administering_agency, p.agency_code, p.jurisdiction, p.funding_type, p.categories) == ("Department of Transportation", "DE-DELDOT", "DE", "grant", [])
    assert p.summary and p.eligibility_structured is None


class _Pages:
    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        for slug, paths in de.PAGES.items():
            for j, path in enumerate(paths):
                if url == de.BASE + path:
                    return read(f"{slug}_{j}")
        raise AssertionError(url)


def test_fetch_reads_both_programs_and_falls_back(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    monkeypatch.setattr(hl, "get", _Pages())
    records = de.fetch()
    assert [r.source_id for r in records] == ["tap", "srts"] and len(records[0].payload["pages"]) == 2
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", _Pages(broken={de.BASE + de.PAGES["tap"][1]}))
    assert {r.source_id: r.payload for r in de.fetch(prior=prior)}["tap"] == prior["tap"]
    assert [r.source_id for r in de.fetch()] == ["srts"]
    monkeypatch.setattr(hl, "get", _Pages())
    assert len(de.fetch(limit=1)) == 1
    assert de.resolve_missing("tap") == {"status": "unknown"}
