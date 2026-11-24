"""The fixture measure (scripts/measure_fixtures.py) reads saved pages through the connectors, never the network."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import measure_fixtures as mf  # noqa: E402


def test_reads_single_and_multi_page_slugs():
    result, missing = mf.records(["la_ocd", "sc_ria"])
    assert "la_ocd/cdbg#clearance" in result and result["la_ocd/lgap"]["status"] == "open"
    # RIA's grants slug is read from two saved pages (grants.html, grants.2.html)
    assert result["sc_ria/grants"]["closes_at"] == "2027-03-22"
    assert all("error" not in v and v["hash"] for v in result.values())
    assert missing == 0


def test_a_slug_without_a_fixture_is_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(mf, "FIXTURES", tmp_path)
    result, missing = mf.records(["la_ocd"])
    assert result == {} and missing == 3
