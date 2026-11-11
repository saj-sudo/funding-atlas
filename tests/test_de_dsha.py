"""Delaware State Housing Authority connector tests, against the six saved pages (never the network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import de_dsha as de
from connectors import hand_list as hl

FIX = Path(__file__).parent / "fixtures" / "de_dsha"
TODAY = date(2026, 11, 3)


def read(slug: str) -> str:
    return (FIX / f"{slug}.html").read_text(encoding="utf-8")


@pytest.fixture
def site(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    monkeypatch.setattr(hl, "get", lambda client, url: read(url.rstrip("/").rsplit("/", 1)[-1]))


def programs(site=None) -> dict:
    out = {}
    for r in de.fetch():
        out[r.source_id] = de.normalize(r, TODAY)
    return out


def test_fixtures_carry_no_scripts_or_contacts():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "hd-contact-card" not in text and "@destatehousing" not in text


def test_header_meta_sections_and_badges():
    page = de.parse_page(read("ddd-program"))
    assert page["title"] == "Downtown Development Districts" and page["lede"].startswith("Investors who make")
    assert ("Who applies", "Investors in a designated district") in page["meta"]
    assert not any(k.lower().startswith("questions") for k, _ in page["meta"])
    sections = de.parse_page(read("supportive-housing"))["sections"]
    sp = next(s for s in sections if s["id"] == "special-populations")
    assert sp["name"] == "Special Populations Housing Fund" and sp["badges"] == ["Not currently accepting applications"]
    names = [s["name"] for s in de.parse_page(read("community-benefit"))["sections"]]
    assert names[0] == "Home4Good" and "Neighborhood Assistance Act (NAA)" in names and not any("Archived" in n for n in names)


def test_fetch_yields_sections_and_pages(site):
    ids = [r.source_id for r in de.fetch()]
    assert "community-benefit#cdbg" in ids and "ddd-program" in ids and "lihtc" in ids and "lihtc#ao-land-bank" in ids and len(ids) == 18
    assert len(de.fetch(limit=3)) == 3


def test_cdbg_names_kent_and_sussex_localities(site):
    p = programs()["community-benefit#cdbg"]
    assert "Local and county governments in Kent and Sussex Counties are eligible to apply." in p.eligibility_text
    assert {"municipality", "county"} <= {t.value for t in p.applicant_types}
    assert p.funding_source == "pass_through" and p.funding_type == "grant"
    assert p.source_url == "https://www.destatehousing.com/community-benefit/#cdbg"


def test_status_from_the_card_the_badge_and_the_dated_lines(site):
    got = programs()
    h4g = got["community-benefit#home4good"]
    assert h4g.status == "closed" and h4g.closes_at_text.startswith("Home4Good 2026 round: Applications closed June 25")
    assert "501(c)(3) nonprofit organizations" in h4g.eligibility_text        # the card's Who applies reaches its program
    esg = got["community-benefit#esg"]
    assert esg.status == "open" and esg.opens_at == date(2026, 10, 14) and esg.closes_at == date(2026, 12, 1)
    assert got["supportive-housing#special-populations"].status == "closed"
    assert got["supportive-housing#special-populations"].closes_at_text == "Special Populations Fund & PSH: Not currently accepting applications"
    assert got["arpa-programs#mimf"].status == "closed" and got["arpa-programs#mimf"].closes_at == date(2024, 8, 1)
    assert got["arpa-programs#catalyst"].status == "unknown"


def test_one_program_pages(site):
    got = programs()
    ddd = got["ddd-program"]
    assert (ddd.status, ddd.opens_at, ddd.closes_at, ddd.rolling, ddd.funding_type) == ("open", date(2026, 7, 15), date(2027, 5, 30), True, "rebate")
    assert ddd.eligibility_structured["status_lines"]["Large Project reservations"] == "Not currently accepting applications"
    assert ddd.eligibility_text.startswith("Investors in a designated district")
    lihtc = got["lihtc"]
    assert lihtc.status == "open" and lihtc.closes_at is None and lihtc.funding_type == "tax_credit"
    assert "Nonprofit and for-profit developers" in lihtc.eligibility_text
    assert got["homeownership-production"].status == "open" and got["homeownership-production"].rolling is True


def test_lihtc_page_also_holds_the_land_bank_loan(site):
    """Saj's rule, 2026-11-11: a page with several programs is one record per program. The Land Bank keeps no id of the
    page's own; LIHTC keeps `lihtc` and loses nothing it read before."""
    got = programs()
    land = got["lihtc#ao-land-bank"]
    assert (land.name, land.status, land.rolling, land.funding_type) == ("Area of Opportunity Land Bank Loan", "open", True, "loan")
    assert land.closes_at_text == "Applications will be accepted on a rolling basis as long as funds are available."
    assert land.applicant_types == [] and land.eligibility_text is None      # "Who applies" is LIHTC's header card
    assert "$5,000,000" in land.summary and "Land Bank" not in (got["lihtc"].summary or "")
    assert len(got) == 18
    # a page whose heading changed is one record again
    page = de.parse_page(read("lihtc"))
    page["body"] = [(k, t.replace("Area of Opportunity Land Bank Program", "Land Bank")) for k, t in page["body"]]
    assert [sid for sid, _ in de.SITE.records_for("lihtc", "page", [page], 0)] == ["lihtc"]


def test_eligible_activities_is_not_an_eligibility_heading(site):
    p = programs()["homeownership-production"]
    assert not (p.eligibility_text or "").startswith("Funds for the program will be disbursed")


@pytest.mark.parametrize("sentence, opens, closes, status", [
    ("Rolling from July 15, 2026 through May 30, 2027", date(2026, 7, 15), date(2027, 5, 30), "open"),
    ("Current round: 2025–2026 — see round documents", None, None, "open"),
    ("Applications closed June 25 — awards announced December 2026", None, None, "closed"),
    ("Not currently accepting applications", None, None, "closed"),
    ("Apply by email — see instructions", None, None, "unknown"),
    ("Round opens", date(2026, 12, 1), None, "forecasted"),
    ("Round opens", date(2026, 10, 1), date(2026, 10, 20), "unknown"),
    (None, None, None, "unknown"),
])
def test_status_for(sentence, opens, closes, status):
    assert de.status_for(sentence, opens, closes, TODAY) == status


def test_fields(site):
    p = programs()["community-benefit#naa"]
    assert (p.administering_agency, p.agency_code, p.jurisdiction, p.categories, p.alns) == ("Delaware State Housing Authority", "DE-DSHA", "DE", [], [])
    assert p.summary and p.name == "Neighborhood Assistance Act (NAA)"


def test_a_failed_page_falls_back_to_prior(monkeypatch, site):
    recs = de.fetch()
    prior = {r.source_id: r.payload for r in recs}

    def broken(client, url):
        if url.endswith("/community-benefit/"):
            raise httpx.ConnectError("down")
        return read(url.rstrip("/").rsplit("/", 1)[-1])
    monkeypatch.setattr(hl, "get", broken)
    again = {r.source_id: r.payload for r in de.fetch(prior=prior)}
    assert again["community-benefit#cdbg"] == prior["community-benefit#cdbg"]
    assert "community-benefit#cdbg" not in {r.source_id for r in de.fetch()}
    assert de.resolve_missing("community-benefit#cdbg") == {"status": "unknown"}
