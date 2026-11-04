"""North Carolina seed-list tests, against the saved nc.gov grant table (never the network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import nc_grants as nc
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "nc_grants"
TODAY = date(2026, 11, 4)


def read() -> str:
    return (FIX / "index.html").read_text(encoding="utf-8")


def rows() -> dict[str, dict]:
    return {r["source_id"]: r for r in nc.parse_index(read())}


def normalize(sid: str):
    return nc.normalize(RawRecord(source_connector=nc.CONNECTOR, source_id=sid, payload=rows()[sid]), TODAY)


def test_fixture_carries_no_scripts():
    assert "<script" not in read()


def test_table_reads_75_programs_from_86_rows():
    got = rows()
    assert len(got) == 75
    assert read().count("<tr>") + read().count("<tr ") == 87   # header plus 86 rows
    r = got["building-and-site-fund-grants"]
    assert r["program"] == "Building and Site Fund Grants" and r["agency"] == "Commerce"
    assert r["url"] == "https://www.commerce.nc.gov/grants-incentives/building-or-site-funds"
    assert r["categories"] == ["Agriculture", "Economic Development"]   # listed twice, one record
    assert r["description"].startswith("Building and Site Fund Grants include")
    assert all(r["url"].startswith("http") and r["agency"] for r in got.values())


def test_every_record_is_an_unknown_directory_row():
    for sid in rows():
        p = normalize(sid)
        assert (p.status, p.closes_at, p.closes_at_text, p.eligibility_text, p.applicant_types) == ("unknown", None, None, None, [])
        assert p.jurisdiction == "NC" and p.level == "state" and p.summary and p.record_hash


def test_fields_and_categories():
    p = normalize("building-and-site-fund-grants")
    assert (p.name, p.administering_agency, p.agency_code, p.funding_type) == ("Building and Site Fund Grants", "Commerce", "NC-COMMERCE", "grant")
    assert [(c.value, c.source_code) for c in p.categories] == [("infrastructure", "Economic Development")]
    assert p.eligibility_structured == {"categories": ["Agriculture", "Economic Development"]}
    m = normalize("migrant-housing-grants")
    assert m.agency_code == "NC-DOL" and [c.value for c in m.categories] == ["health"]
    arts = normalize("nc-arts-council-grants")
    assert arts.categories == [] and arts.eligibility_structured == {"categories": ["Art & Culture"]}
    assert sum(1 for sid in rows() if normalize(sid).funding_source == "pass_through") == 3


def test_fetch_is_one_get_and_aborts_without_the_table(monkeypatch):
    calls = []

    def fake(client, url):
        calls.append(url)
        return read()

    monkeypatch.setattr(nc, "_get", fake)
    records = nc.fetch()
    assert len(records) == 75 and calls == [nc.INDEX_URL]
    assert [r.source_id for r in nc.fetch(limit=3)] == list(rows())[:3]

    def broken(client, url):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(nc, "_get", broken)
    with pytest.raises(httpx.ConnectError):
        nc.fetch()


def test_resolve_missing_is_unknown():
    assert nc.resolve_missing("x") == {"status": "unknown"}
