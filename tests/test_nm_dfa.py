"""New Mexico DFA's Grant Search Dashboard (nm_dfa, 12.8b) against saved API answers; never the network."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import nm_dfa as m
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "nm_dfa"
TODAY = date(2026, 11, 20)
PAGE = json.loads((FIX / "open_page.json").read_text(encoding="utf-8"))
ONE = json.loads((FIX / "one_2009.json").read_text(encoding="utf-8"))
FEDERAL_SITE_ROWS = {"2001", "2214", "2637", "2764", "3799"}   # USDA RD, NRCS, the Southwest Border Region Commission


def serve(monkeypatch: pytest.MonkeyPatch, handler) -> list[str]:
    """Route the connector's client through `handler`; returns the URLs asked for."""
    asked: list[str] = []

    def app(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return handler(request)

    monkeypatch.setattr(m, "_client", lambda: httpx.Client(transport=httpx.MockTransport(app)))
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    return asked


@pytest.fixture
def programs(monkeypatch):
    serve(monkeypatch, lambda r: httpx.Response(200, json=PAGE))
    records = m.fetch()
    return {r.source_id: (r, m.normalize(r, TODAY)) for r in records}


def test_fixtures_hold_no_ones_contact_details():
    for f in FIX.iterdir():
        text = f.read_text(encoding="utf-8")
        assert "programOfficer" not in text and "createdBy" not in text, f.name


def test_fetch_keeps_the_states_own_rows_and_reads_one_page(monkeypatch, programs):
    assert len(programs) == 53                                    # 58 agency rows, less 5 on federal sites
    assert not FEDERAL_SITE_ROWS & set(programs)
    assert all(r.payload["source"] == "agency" for r, _ in programs.values())    # no Grants.gov copy
    assert not any(m.DROP & set(r.payload) for r, _ in programs.values())
    assert not any("mc_eid" in (r.payload.get("announcementUrl") or "") for r, _ in programs.values())


def test_paging_stops_at_the_total(monkeypatch):
    rows = PAGE["data"]["data"]

    def two_pages(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        chunk = rows[:40] if page == 1 else rows[40:]
        return httpx.Response(200, json={"status": "ok", "data": {"data": chunk, "total": len(rows)}})

    asked = serve(monkeypatch, two_pages)
    assert len(m.fetch()) == 53 and len(asked) == 2 and all("pageSize=200" in u and "excludeClosed=1" in u for u in asked)


def test_a_failed_list_raises(monkeypatch):
    serve(monkeypatch, lambda r: httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        m.fetch()
    serve(monkeypatch, lambda r: httpx.Response(200, json={"status": "error", "data": None}))
    with pytest.raises(ValueError):
        m.fetch()


def test_status_is_what_the_source_says(programs):
    road = programs["2009"][1]                                    # Local Government Road Fund CAP, closes 2027-03-15
    assert (road.status, road.closes_at, road.rolling) == ("open", date(2027, 3, 15), None)
    assert m.normalize(programs["2009"][0], date(2027, 3, 16)).status == "closed"
    assert programs["2024"][1].status == "forecasted" and programs["2024"][1].closes_at_text == "Forecasted"
    cwsrf = programs["2809"][1]                                   # applications accepted year-round
    assert (cwsrf.status, cwsrf.rolling, cwsrf.closes_at) == ("open", True, None)
    counts = {s: sum(1 for _, p in programs.values() if p.status == s) for s in ("open", "forecasted")}
    assert counts == {"open": 30, "forecasted": 23}


def test_fields_map_as_documented(programs):
    lwcf = programs["3019"][1]
    assert lwcf.administering_agency == "Energy, Minerals, and Natural Resources Department"
    assert lwcf.source_url.startswith("https://www.emnrd.nm.gov/")
    assert (lwcf.amount_min, lwcf.amount_max, lwcf.match_required) == (None, 500000, True)   # floor 0 is not stated
    assert lwcf.funding_source == "pass_through" and lwcf.funding_type == "grant"
    assert programs["2809"][1].funding_type == "loan" and programs["2009"][1].funding_type == "cooperative_agreement"
    assert programs["2009"][1].funding_source == "direct"
    assert programs["2024"][1].eligibility_structured["geography"].startswith("Doña Ana")


def test_applicants_from_labels_and_the_free_text_line(programs):
    tags = {sid: {t.value for t in p.applicant_types} for sid, (_, p) in programs.items()}
    assert {"county"} <= tags["2009"]                              # "Counties" in eligibleApplicantsOther
    assert {"municipality"} <= tags["2011"]                        # "Municipalities"
    assert {"municipality", "county", "tribe", "state", "higher_ed"} <= tags["3019"]   # "Higher Education": the table
    assert tags["3038"] == {"school"}                              # Teacher Housing: "Public Schools and Districts"
    for _, p in programs.values():                                 # one tag per applicant type
        values = [t.value for t in p.applicant_types]
        assert len(values) == len(set(values))


def test_categories_from_the_portal_labels(programs):
    cats = {sid: {t.value for t in p.categories} for sid, (_, p) in programs.items()}
    assert cats["2809"] >= {"water"}                               # "Water, Wastewater, Solid Waste, Utilities"
    assert "transportation" in cats["2009"]                        # "Roads & Bridges" or "Transportation"
    for _, p in programs.values():
        values = [t.value for t in p.categories]
        assert len(values) == len(set(values))


def test_resolve_missing_reads_the_one_record(monkeypatch):
    serve(monkeypatch, lambda r: httpx.Response(200, json=ONE))
    got = m.resolve_missing("2009")
    assert got["status"] in ("open", "closed") and got["closes_at"] == date(2027, 3, 15)
    serve(monkeypatch, lambda r: httpx.Response(200, json={"status": "ok", "data": None}))
    assert m.resolve_missing("1") == {"status": "unknown"}
    serve(monkeypatch, lambda r: httpx.Response(500))
    assert m.resolve_missing("1") is None


def test_kept_rule():
    base = {"source": "agency", "deleted": 0, "announcementUrl": "https://www.env.nm.gov/x"}
    assert m.kept(base)
    assert not m.kept(dict(base, source="grants.gov"))
    assert not m.kept(dict(base, deleted=1))
    assert not m.kept(dict(base, announcementUrl="https://www.rd.usda.gov/programs"))
    assert m.kept(dict(base, announcementUrl="https://notusda.gov.example.com/x"))   # a host, not a substring
    assert m.normalize(RawRecord(source_connector="nm_dfa", source_id="9", payload=dict(base, opportunityTitle="X")),
                       TODAY).source_url == "https://www.env.nm.gov/x"


def test_tracking_parameters_leave_the_link(programs):
    tfm = programs["3097"][1]                                      # EDD's Targeted Federal Match: a Mailchimp link
    assert "mc_eid" not in tfm.source_url and "mc_cid" not in tfm.source_url
    assert tfm.source_url.startswith("https://www.edd.newmexico.gov/divisions-and-offices/tio/targeted-federal-match/")
    assert m.clean_url("https://a.gov/p?id=3&utm_source=x&mc_eid=y") == "https://a.gov/p?id=3"
    assert m.clean_url("https://a.gov/p/") == "https://a.gov/p/"
