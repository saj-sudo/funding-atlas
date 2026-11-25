"""Georgia's Department of Community Affairs (ga_dca) against saved pages (milestone 12.9)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from connectors import ga_dca as m
from connectors import hand_list as hl
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "ga_dca"
TODAY = date(2026, 11, 24)
CDBG = ["cdbg-annual", "cdbg-eip", "cdbg-redevelopment", "cdbg-itad"]
NEW = ["onegeorgia-site-development", "onegeorgia-workforce-housing", "ddrlf", "chip"]   # 12.11


def page(slug: str) -> dict:
    return m.parse_page((FIX / f"{slug}.html").read_text(encoding="utf-8"))


def every(today: date = TODAY) -> dict:
    out: dict = {}
    for slug, path in m.PAGES.items():
        for sid, payload in m.SITE.records_for(slug, path, [page(slug)], 0):
            out[sid] = m.normalize(RawRecord(source_connector="ga_dca", source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def texts(slug: str) -> list[str]:
    return [t for _, t in page(slug)["blocks"]]


def test_nine_records_titled_from_the_page_heading():
    progs = every()
    assert list(progs) == [*CDBG, "onegeorgia-equity", *NEW]
    assert [p.name for p in progs.values()] == [
        "Annual CDBG Competition", "Employment Incentive Program", "Redevelopment Fund",
        "Immediate Threat and Danger Program", "OneGeorgia Equity Fund", "Site Development Initiative",
        "Workforce Housing Initiative", "Downtown Development Revolving Loan Fund (DDRLF)",
        "Community HOME Investment Program (CHIP)"]
    assert all(p.jurisdiction == "GA" and p.agency_code == "GA-DCA" for p in progs.values())
    assert progs["onegeorgia-equity"].source_url == "https://dca.georgia.gov/financing-tools/infrastructure/onegeorgia-authority/equity-fund"


def test_the_cards_are_dropped_but_the_apply_card_and_the_read_stops_at_the_faq():
    annual = page("cdbg-annual")["blocks"]
    assert ("label", "Apply for the FY2027 CDBG Annual Competition") in annual
    for slug in m.PAGES:
        lines = [t for t in texts(slug) if not t.startswith("The CHIP program does not provide direct assistance")]
        assert not any("Documents & Downloads" in t or "Contact" in t or "email" in t.lower() or "@" in t for t in lines)
    assert "Redevelopment Fund Flyer" not in texts("cdbg-redevelopment")
    equity = texts("onegeorgia-equity")
    assert "OneGeorgia Equity Regulations" not in equity
    assert not any("Frequently Asked" in t or "FAQs" in t for t in equity)
    # the quarterly sentence takes its list of months; they are not left as four one-word items
    assert "Online Applications are accepted quarterly on the 2nd Friday of the following months: January, April, July, October" in equity
    assert "January" not in equity


def test_status_no_page_dates_a_round_but_chip():
    progs = every()
    assert all((p.status, p.closes_at, p.opens_at) == ("unknown", None, None) for sid, p in progs.items() if sid != "chip")
    assert progs["cdbg-annual"].closes_at_text == "Apply for the FY2027 CDBG Annual Competition"
    assert progs["onegeorgia-equity"].closes_at_text.startswith("Online Applications are accepted quarterly on the 2nd Friday")
    assert progs["onegeorgia-equity"].closes_at_text.endswith("January, April, July, October")
    for sid in ("cdbg-eip", "cdbg-redevelopment", "cdbg-itad"):
        assert progs[sid].closes_at_text is None


def test_funding_source_match_and_categories():
    progs = every()
    assert {sid: p.funding_source for sid, p in progs.items()} == {**{sid: "pass_through" for sid in CDBG}, "onegeorgia-equity": "direct",
                                                                  **{sid: "direct" for sid in NEW if sid != "chip"}, "chip": "pass_through"}
    # "Grants up to $500,000 ... no matching funds required. Grants of $500,001 to $750,000 - 5% ...": it depends, so null
    assert progs["cdbg-annual"].match_required is None
    assert all(p.categories[0].value == "infrastructure" and p.funding_type == "grant" for sid, p in progs.items() if sid not in NEW)
    assert progs["onegeorgia-workforce-housing"].categories[0].value == progs["chip"].categories[0].value == "housing"
    assert progs["ddrlf"].funding_type == "loan"


def test_applicants_units_of_general_local_government_and_the_recipient_sentences():
    progs = every()
    for sid in ("cdbg-annual", "cdbg-itad"):
        assert tags(progs[sid]) == {"municipality", "county"}
        assert "units of general" in progs[sid].eligibility_text   # the stored text is the page's own wording
    assert progs["cdbg-redevelopment"].eligibility_text.startswith("The RDF provides local governments access to flexible financial assistance")
    assert "financing to local governments" in progs["cdbg-eip"].eligibility_text
    assert tags(progs["cdbg-redevelopment"]) == tags(progs["cdbg-eip"]) == {"municipality", "county"}
    assert tags(progs["onegeorgia-equity"]) == {"municipality", "county", "special_district"}
    assert "units of local government" == m.tag_line("Eligible applicants are units of general purpose local government, "
                                                     "excluding metropolitan cities, urban counties")[-25:]


def test_fetch_and_fallback(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", slept.append)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert [r.source_id for r in records] == list(m.PAGES)
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["cdbg-itad"],)))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)}["cdbg-itad"] == prior["cdbg-itad"]
    assert [r.source_id for r in m.fetch()] == [s for s in m.PAGES if s != "cdbg-itad"]
    assert set(slept) == {3.0}


def test_the_three_pages_of_12_11_and_the_title_when_there_is_no_h1():
    progs = every()
    assert page("ddrlf")["title"] == "Downtown Development Revolving Loan Fund (DDRLF)"   # from <title>: the page has no h1
    assert tags(progs["ddrlf"]) == {"municipality", "county", "special_district"}
    assert tags(progs["onegeorgia-site-development"]) == {"special_district"}   # "Applicant must be a development authority"
    assert {"municipality", "county"} <= tags(progs["onegeorgia-workforce-housing"])
    assert progs["onegeorgia-workforce-housing"].closes_at_text.startswith("Online Applications are accepted quarterly")


def test_chip_reads_its_application_portal_section_and_open_through():
    # the round is printed under "Application Portal", after "Documents & Downloads" where the read stops
    assert texts("chip")[0] == "Application Portal"
    assert texts("chip")[1].startswith("The 2027 CHIP grant cycle is now open through January 31, 2027.")
    chip = every()["chip"]
    assert (chip.status, chip.opens_at, chip.closes_at) == ("open", None, date(2027, 1, 31))
    assert chip.closes_at_text == "The 2027 CHIP grant cycle is now open through January 31, 2027."
    assert tags(chip) == {"municipality", "county", "nonprofit"}
    assert every(date(2027, 2, 15))["chip"].status == "unknown"   # past its date the page's "now open" is not repeated
