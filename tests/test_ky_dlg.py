"""Kentucky DLG Portal connector tests, against the saved opportunity lists and pages (never the network)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import ky_dlg as ky
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "ky_dlg"
IDS = ["LLISP", "LGEDFSCCS", "LMPP", "RDAAP"]


def rows() -> list[dict[str, str]]:
    return ky.parse_list((FIX / "list_open.json").read_text(encoding="utf-8"))["rows"]


def page(sid: str) -> dict:
    return ky.parse_page((FIX / f"{sid}.html").read_text(encoding="utf-8"))


def normalize(sid: str, status_list: str = "Open"):
    row = next(r for r in rows() if r["shortname"] == sid)
    raw = RawRecord(source_connector=ky.CONNECTOR, source_id=sid, payload={"row": row, "list": status_list, "page": page(sid)})
    return ky.normalize(raw, date(2026, 11, 4))


def tags(sid: str) -> set[str]:
    return {t.value for t in normalize(sid).applicant_types}


def test_lists_parse_the_templates_json():
    got = ky.parse_list((FIX / "list_open.json").read_text(encoding="utf-8"))
    assert [r["shortname"] for r in got["rows"]] == IDS and got["more"] is False
    assert got["rows"][2]["applandingpage"] == "/FCLMPP/LMPP" and got["rows"][2]["enddate"] == ""
    assert ky.parse_list((FIX / "list_expired.json").read_text(encoding="utf-8"))["rows"] == []
    assert ky.parse_list("\n\n  " + json.dumps({"moreRecords": True, "results": []}))["more"] is True


def test_page_title_summary_and_all_four_sections():
    p = page("LMPP")
    assert p["title"] == "Local Match Participation Program"
    assert p["summary"].startswith("The Flood Control LMPP is administered by the Department for Local Government")
    assert set(p["sections"]) == {"eligibility", "required_documentation", "award_details", "application_process"}
    assert p["sections"]["eligibility"].startswith("Eligible applicants: City governments, County governments")
    assert "{" not in p["sections"]["eligibility"]                 # the inline <style> is dropped
    for sid in IDS:                                                # the unclosed last h2 still yields its section
        assert page(sid)["sections"].get("application_process")


def test_fields():
    p = normalize("LMPP")
    assert (p.status, p.funding_type, p.funding_source, p.level, p.jurisdiction, p.agency_code) == (
        "open", "grant", "direct", "state", "KY", "KY-DLG")
    assert p.source_url == "https://www.dlgportal.ky.gov/en-US/FCLMPP/LMPP"
    assert (p.opens_at, p.closes_at, p.rolling, p.closes_at_text) == (None, None, None, None)
    assert set(p.eligibility_structured) == {"required_documentation", "award_details", "application_process"}
    assert p.categories == [] and p.alns == []
    assert normalize("LMPP", "Expired").status == "closed"
    assert normalize("LMPP", "Something").status == "unknown"


def test_applicants_from_eligibility_and_the_recipient_sentence():
    assert tags("LMPP") == {"municipality", "county"}              # the list survives the "will not fund" bullet
    assert tags("LGEDFSCCS") == {"county"}                         # "Local Government ... Fund (LGEDF)" is a name
    assert tags("LLISP") == {"municipality", "county", "special_district"}   # "local governments, public agencies, SPGEs"
    assert tags("RDAAP") == {"special_district"}                   # "grants to Special Purpose Governmental Entities"


def test_dates_when_the_portal_gives_them():
    row = dict(rows()[0], startdate="1/15/2027 12:00:00 AM", enddate="3/31/2027 11:59:00 PM")
    p = ky.normalize(RawRecord(source_connector=ky.CONNECTOR, source_id="LLISP",
                               payload={"row": row, "list": "Open", "page": page("LLISP")}))
    assert (p.opens_at, p.closes_at) == (date(2027, 1, 15), date(2027, 3, 31))


class _Site:
    def __init__(self, broken: set[str] | None = None):
        self.calls: list[str] = []
        self.broken = broken or set()

    def __call__(self, client, url: str) -> str:
        self.calls.append(url)
        if any(url.startswith(b) for b in self.broken):
            raise httpx.ConnectError("down")
        if url.startswith(ky.LIST_URL):
            return (FIX / ("list_open.json" if "Open" in url else "list_expired.json")).read_text(encoding="utf-8")
        sid = next(r["shortname"] for r in rows() if url == ky.page_url(r))
        return (FIX / f"{sid}.html").read_text(encoding="utf-8")


def test_fetch_reads_both_lists_then_each_page(monkeypatch):
    monkeypatch.setattr(ky.time, "sleep", lambda s: None)
    site = _Site()
    monkeypatch.setattr(ky, "_get", site)
    records = ky.fetch()
    assert [r.source_id for r in records] == IDS and {r.payload["list"] for r in records} == {"Open"}
    assert len(site.calls) == 2 + 4
    prior = {r.source_id: r.payload for r in records}
    lmpp = ky.page_url(rows()[2])
    monkeypatch.setattr(ky, "_get", _Site(broken={lmpp}))
    again = {r.source_id: r.payload for r in ky.fetch(prior=prior)}
    assert again["LMPP"]["page"] == prior["LMPP"]["page"]
    monkeypatch.setattr(ky, "_get", _Site(broken={ky.LIST_URL}))
    with pytest.raises(httpx.ConnectError):
        ky.fetch()
    monkeypatch.setattr(ky, "_get", _Site())
    assert [r.source_id for r in ky.fetch(limit=2)] == IDS[:2]


def test_resolve_missing_is_unknown():
    assert ky.resolve_missing("LMPP") == {"status": "unknown"}
