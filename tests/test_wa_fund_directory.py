"""Washington Fund Directory tests, against the saved landing page and six topic pages (never the network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from connectors import wa_fund_directory as wa
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "wa_fund_directory"
TODAY = date(2026, 11, 4)
TOPICS = ["education", "emergency-management", "environment-water-energy", "housing-infrastructure-economic-development",
          "recreation-culture-social-services", "transportation"]


def read(name: str) -> str:
    return (FIX / f"{name}.html").read_text(encoding="utf-8")


def records() -> dict[str, dict]:
    topics = wa.parse_topics(read("index"))
    rows = []
    for t in topics:
        rows += wa.parse_topic(read(t["url"].rstrip("/").rsplit("/", 1)[-1]), t["name"])
    return {r["source_id"]: r for r in wa.merge(rows)}


def normalize(sid: str):
    return wa.normalize(RawRecord(source_connector=wa.CONNECTOR, source_id=sid, payload=records()[sid]), TODAY)


def test_fixtures_carry_no_scripts():
    for path in FIX.iterdir():
        assert "<script" not in path.read_text(encoding="utf-8")


def test_landing_lists_six_topics_in_order():
    topics = wa.parse_topics(read("index"))
    assert [t["url"].rsplit("/", 1)[-1] for t in topics] == TOPICS
    assert topics[2]["name"] == "Environmental, Water, & Energy"


def test_topic_tables_merge_into_one_record_per_program():
    got = records()
    assert len(got) == 128
    cdbg = got["cdbg-general-purpose-grant-program"]
    assert cdbg["url"] == "https://www.commerce.wa.gov/cdbg/cdbg-general-purpose/"
    assert (cdbg["type"], cdbg["fund_source"], cdbg["agency"]) == ("Economic Development", "Grant", "Department of Commerce")
    assert cdbg["topics"] == ["Housing, Infrastructure, & Economic Development"]
    assert len(got["local-program"]["topics"]) == 4   # listed under four topics, one record
    assert all(r["url"] and r["agency"] for r in got.values())


def test_every_record_is_an_unknown_directory_row():
    for sid in records():
        p = normalize(sid)
        assert (p.status, p.closes_at, p.eligibility_text, p.applicant_types) == ("unknown", None, None, [])
        assert p.jurisdiction == "WA" and p.summary and p.record_hash


def test_fields_codes_and_categories():
    p = normalize("cdbg-general-purpose-grant-program")
    assert (p.name, p.administering_agency, p.agency_code, p.funding_type, p.funding_source) == ("CDBG General Purpose Grant Program", "Department of Commerce", "WA-COM", "grant", "direct")
    assert [(c.value, c.source_code) for c in p.categories] == [("infrastructure", "Economic Development")]
    assert p.eligibility_structured == {"type_of_program": "Economic Development", "fund_source": "Grant", "topics": ["Housing, Infrastructure, & Economic Development"]}
    assert normalize("crab-emergency-loan-program").funding_type == "loan"
    assert normalize("crab-emergency-loan-program").agency_code == "WA-CRAB"
    assert [c.value for c in normalize("crab-emergency-loan-program").categories] == ["public_safety"]
    assert wa.agency_code_for("Dept. of Commerce") == "WA-COM" and wa.agency_code_for("Some New Board") == "WA-SNB"
    codes = {normalize(sid).agency_code for sid in records()}
    assert codes >= {"WA-COM", "WA-ECY", "WA-RCO", "WA-WSDOT", "WA-MIL", "WA-TIB"} and all(c.startswith("WA-") for c in codes)


class _Site:
    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        return read("index") if url == wa.INDEX_URL else read(url.rstrip("/").rsplit("/", 1)[-1])


def test_fetch_reads_the_landing_then_six_topics(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    site = _Site()
    monkeypatch.setattr(wa, "_get", site)
    recs = wa.fetch()
    assert len(recs) == 128 and len(site.calls) == 7 and site.calls[0] == wa.INDEX_URL
    assert len(wa.fetch(limit=5)) == 5
    monkeypatch.setattr(wa, "_get", _Site(broken={wa.INDEX_URL + "/transportation"}))
    with pytest.raises(httpx.ConnectError):
        wa.fetch()


def test_resolve_missing_is_unknown():
    assert wa.resolve_missing("x") == {"status": "unknown"}
