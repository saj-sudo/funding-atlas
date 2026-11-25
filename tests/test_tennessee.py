"""Tennessee's agencies on www.tn.gov (tn_ecd, tn_tdot) against the pages the Actions runner saved (12.9)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from connectors import tn_ecd, tn_tdot
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 24)


def page(mod, slug: str) -> dict:
    return mod.SITE.parse_page((FIX / mod.CONNECTOR / f"{slug}.html").read_text(encoding="utf-8"))


def every(mod, today: date = TODAY) -> dict:
    out: dict = {}
    for slug, path in mod.PAGES.items():
        for sid, payload in mod.SITE.records_for(slug, path, [page(mod, slug)], 0):
            out[sid] = mod.normalize(RawRecord(source_connector=mod.CONNECTOR, source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def test_ecd_four_records_named_from_the_page_title_but_cdbg():
    progs = every(tn_ecd)
    assert list(progs) == ["cdbg", "infrastructure-planning", "downtown-improvement", "threestar"]
    assert progs["cdbg"].name == "Community Development Block Grant (CDBG): Community Development Regular Round"
    assert progs["infrastructure-planning"].name == "Infrastructure Planning Grant"
    assert progs["downtown-improvement"].name == "Downtown Improvement Grant Program"
    assert all(p.jurisdiction == "TN" and p.administering_agency == tn_ecd.AGENCY for p in progs.values())
    assert all(p.source_url.startswith("https://www.tn.gov/ecd/") for p in progs.values())
    assert "historic-development" not in tn_ecd.PAGES   # its page says no further round is funded


def test_the_read_keeps_every_tab_and_drops_contacts_and_the_application_process():
    ipg = [t for _, t in page(tn_ecd, "infrastructure-planning")["blocks"]]
    assert any(t.startswith("Application Deadline:") for t in ipg)
    assert any("Salesforce system" in t for t in ipg)   # the second tab
    assert not any("@tn.gov" in t for t in ipg)
    dig = [t for _, t in page(tn_ecd, "downtown-improvement")["blocks"]]
    assert "Important Dates" in dig
    assert not any("Required Files" in t or "Project Need (20 points)" in t or "615" in t for t in dig)


def test_a_line_of_dates_is_read_one_date_to_a_line():
    dig = [t for _, t in page(tn_ecd, "downtown-improvement")["blocks"]]
    assert "August 28, 2026 - Application Due" in dig
    assert "October 20, 2026 - Grants Announced" in dig


def test_status_a_past_deadline_is_unknown_with_the_date_kept():
    progs = every(tn_ecd)
    ipg, dig = progs["infrastructure-planning"], progs["downtown-improvement"]
    assert (ipg.status, ipg.closes_at) == ("unknown", date(2026, 10, 30))
    assert (dig.status, dig.opens_at, dig.closes_at) == ("unknown", date(2026, 7, 7), date(2026, 8, 28))
    assert dig.closes_at_text == "August 28, 2026 - Application Due"
    for sid in ("cdbg", "threestar"):   # "once a year, in the spring" and "biennial" date nothing
        assert progs[sid].status == "unknown" and progs[sid].closes_at is None
    # the same pages read while their rounds were live
    assert every(tn_ecd, date(2026, 10, 1))["infrastructure-planning"].status == "open"
    assert every(tn_ecd, date(2026, 7, 1))["downtown-improvement"].status == "forecasted"


def test_funding_source_match_and_tags():
    progs = every(tn_ecd)
    assert {sid: p.funding_source for sid, p in progs.items()} == {
        "cdbg": "pass_through", "infrastructure-planning": "direct", "downtown-improvement": "direct",
        "threestar": "direct"}
    assert progs["infrastructure-planning"].match_required is True   # "the required 5% match funding"
    assert "county" in tags(progs["threestar"])   # "biennial grants will be available to counties"
    assert all(p.categories and p.categories[0].value == "infrastructure" for p in progs.values())
    assert all(p.amount_min is None and p.amount_max is None for p in progs.values())


def test_tdot_tap_is_one_undated_record():
    progs = every(tn_tdot)
    assert list(progs) == ["tap"]
    tap = progs["tap"]
    assert tap.name == "Transportation Alternatives Program"
    assert (tap.status, tap.closes_at, tap.funding_source) == ("unknown", None, "pass_through")
    assert {"municipality", "county"} <= tags(tap)   # "began providing funds to local governments in 1991"
    assert tap.categories[0].value == "transportation"
    blocks = page(tn_tdot, "tap")["blocks"]
    assert len(blocks) == 1 and not any("Awarded Projects" in t or "PROWAG" in t for _, t in blocks)


def test_fetch_paces_itself_and_falls_back(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", slept.append)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.HTTPStatusError("403", request=httpx.Request("GET", url), response=httpx.Response(403))
        slug = next(s for s, p in tn_ecd.PAGES.items() if url == tn_ecd.BASE + p)
        return (FIX / "tn_ecd" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = tn_ecd.fetch()
    assert [r.source_id for r in records] == list(tn_ecd.PAGES)
    assert slept and all(s >= 6.0 for s in slept)   # the load balancer walled a faster survey (12.6j)
    prior = {r.source_id: r.payload for r in records}
    refused = tn_ecd.BASE + tn_ecd.PAGES["cdbg"]
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(refused,)))
    assert {r.source_id: r.payload for r in tn_ecd.fetch(prior=prior)}["cdbg"] == prior["cdbg"]


def _served(url: str) -> str:
    slug = next(s for s, p in tn_ecd.PAGES.items() if url == tn_ecd.BASE + p)
    return (FIX / "tn_ecd" / f"{slug}.html").read_text(encoding="utf-8")


def test_the_runners_first_request_reset_is_retried(monkeypatch):
    # 12.9a: the first request of every runner session to www.tn.gov was a connection reset, and CDBG is the first page.
    slept: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", slept.append)
    resets = [2]

    def site(client, url):
        if resets[0]:
            resets[0] -= 1
            raise httpx.ConnectError("reset", request=httpx.Request("GET", url))
        return _served(url)

    monkeypatch.setattr(hl, "get", site)
    assert [r.source_id for r in tn_ecd.fetch()] == list(tn_ecd.PAGES)
    assert len(slept) == 2 + len(tn_ecd.PAGES) - 1 and all(s >= 6.0 for s in slept)


def test_a_status_is_never_retried(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    calls: list[str] = []
    refused = tn_ecd.BASE + tn_ecd.PAGES["cdbg"]

    def site(client, url):
        calls.append(url)
        if url == refused:
            raise httpx.HTTPStatusError("403", request=httpx.Request("GET", url), response=httpx.Response(403))
        return _served(url)

    monkeypatch.setattr(hl, "get", site)
    prior = {"cdbg": {"page": {"title": "stored", "blocks": []}}}
    records = {r.source_id: r.payload for r in tn_ecd.fetch(prior=prior)}
    assert calls.count(refused) == 1
    assert records["cdbg"] == prior["cdbg"]


def test_three_resets_fall_back_after_two_retries(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    calls: list[str] = []
    refused = tn_ecd.BASE + tn_ecd.PAGES["cdbg"]

    def site(client, url):
        calls.append(url)
        if url == refused:
            raise httpx.ReadError("reset", request=httpx.Request("GET", url))
        return _served(url)

    monkeypatch.setattr(hl, "get", site)
    prior = {"cdbg": {"page": {"title": "stored", "blocks": []}}}
    assert {r.source_id: r.payload for r in tn_ecd.fetch(prior=prior)}["cdbg"] == prior["cdbg"]
    assert calls.count(refused) == 3
    assert "cdbg" not in {r.source_id for r in tn_ecd.fetch()}
