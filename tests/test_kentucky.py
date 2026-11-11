"""Kentucky's four agency connectors (ky_dlgfed, ky_tc, ky_eec, ky_kia) and their SharePoint base, against saved pages."""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from connectors import kentucky_sharepoint as ky
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 11)
AGENCIES = ["ky_dlgfed", "ky_tc", "ky_eec", "ky_kia"]


def mod(name: str):
    return importlib.import_module(f"connectors.{name}")


def page(name: str, slug: str) -> dict:
    return mod(name).SITE.parse_page((FIX / name / f"{slug}.html").read_text(encoding="utf-8"))


def programs(name: str, slug: str, today: date = TODAY) -> dict:
    m = mod(name)
    records = m.SITE.records_for(slug, m.PAGES[slug], [page(name, slug)], 0)
    return {sid: m.normalize(RawRecord(source_connector=name, source_id=sid, payload=payload), today) for sid, payload in records}


def program(name: str, sid: str, today: date = TODAY):
    return programs(name, sid.split("#")[0], today)[sid]


def tags(name: str, sid: str) -> set[str]:
    return {t.value for t in program(name, sid).applicant_types}


def text(name: str, slug: str) -> str:
    return " ".join(t for _, t in page(name, slug)["blocks"])


def test_every_page_reads():
    for name in AGENCIES:
        m = mod(name)
        for slug in m.PAGES:
            assert page(name, slug)["blocks"], (name, slug)
            for p in programs(name, slug).values():
                assert p.name and p.jurisdiction == "KY" and p.source_url.startswith(m.BASE), (name, slug)


def test_reader_keeps_a_deadline_beside_a_contact_and_reads_line_divs():
    # RTP's "It is due on Friday, October 30th, 2026. If you have any questions, please contact ...@ky.gov" is one
    # paragraph: the contact sentence goes, the deadline stays.
    rtp = text("ky_dlgfed", "rtp")
    assert "due on Friday, October 30th, 2026" in rtp and "@ky.gov" not in rtp
    # TC's text sits in Content Editor web parts, not in the RichHtmlField (which is empty there).
    assert "Transportation Alternatives Program (TAP) provides funding" in text("ky_tc", "tap")
    # EEC's "Funding Source: ..." lines are `div`s, read as paragraphs.
    assert ("p", "Funding Source: Kentucky Pride Fund") in page("ky_eec", "illegal-dump")["blocks"]
    assert ky.parse_page("<html><h1>Gone</h1></html>") == {"title": "Gone", "blocks": []}


def test_status_and_dates():
    cases = {
        ("ky_dlgfed", "cdbg-community"): ("unknown", date(2026, 4, 1), date(2026, 9, 1)),      # window ended
        ("ky_dlgfed", "cdbg-facilities"): ("unknown", date(2026, 4, 1), date(2026, 9, 1)),
        ("ky_dlgfed", "cdbg-emergency"): ("open", date(2026, 4, 1), date(2027, 1, 31)),
        ("ky_dlgfed", "cdbg-economic"): ("open", date(2026, 4, 1), date(2027, 3, 1)),
        ("ky_dlgfed", "cdbg-housing"): ("open", date(2026, 4, 1), date(2027, 2, 1)),
        ("ky_dlgfed", "cdbg-rky"): ("open", date(2026, 4, 1), date(2027, 2, 1)),
        ("ky_dlgfed", "arc"): ("open", date(2026, 8, 1), None),     # "Pre-applications ... are being accepted", rolling from 2026-08-01
        ("ky_dlgfed", "rtp"): ("unknown", None, date(2026, 10, 30)),
        ("ky_dlgfed", "lwcf"): ("unknown", None, date(2026, 10, 30)),
        ("ky_dlgfed", "dra"): ("unknown", None, None),
        ("ky_tc", "tap"): ("unknown", None, None),                  # "The next application cycle ... will be held in 2027"
        ("ky_tc", "cmaq"): ("closed", None, None),                  # "The Office of Local Programs is not currently accepting applications for funding." (12.6f)
        ("ky_kia", "fund-a"): ("unknown", None, None),
    }
    for (name, sid), (status, opens, closes) in cases.items():
        p = program(name, sid)
        assert (p.status, p.opens_at, p.closes_at) == (status, opens, closes), (name, sid)
    assert program("ky_dlgfed", "cdbg-community", date(2026, 8, 15)).status == "open"


def test_application_window_is_read_only_when_nothing_else_is_a_deadline():
    sents = ["Applications Accepted: Dates are April 1, 2026 - September 1, 2026."]
    assert hl.deadline(sents) == (sents[0], date(2026, 9, 1)) and hl.opening(sents) == date(2026, 4, 1)
    # a grant term is not an application window, and a range with no application in the sentence is not read
    assert hl.deadline(["The grant term is April 1, 2026 - September 1, 2027 and applications are reviewed."]) == (None, None)
    assert hl.deadline(["The conference runs April 1, 2026 - April 3, 2026."]) == (None, None)
    # a deadline word still wins over a range
    assert hl.deadline(["Applications are due May 1, 2026. Applications Accepted: April 1, 2026 - September 1, 2026."])[1] == date(2026, 5, 1)


def test_applicants():
    for sid in ("cdbg-community", "cdbg-housing", "cdbg-facilities", "cdbg-economic"):
        assert tags("ky_dlgfed", sid) == {"municipality", "county"}, sid
    assert tags("ky_dlgfed", "cdbg-emergency") == {"municipality"}      # "Only communities ... may submit an application"
    assert tags("ky_dlgfed", "dra") == {"municipality", "county", "special_district", "nonprofit"}   # "Who Can Apply: ..."
    assert tags("ky_dlgfed", "arc") == {"municipality", "county", "special_district", "nonprofit"}
    assert tags("ky_dlgfed", "lwcf") == {"municipality", "county"}
    for sid in ("rtp", "rhp", "cdbg-rky"):
        assert tags("ky_dlgfed", sid) == set(), sid                      # the page names no applicant
    # "Local and state government agencies are eligible to apply"; the non-profits "may partner", they do not apply
    assert tags("ky_tc", "cmaq") == {"municipality", "county", "state"}
    assert "may partner with an eligible applicant" in program("ky_tc", "cmaq").eligibility_text
    assert tags("ky_tc", "tap") == set()
    # "The applicant must be a governmental agency" is kept as the eligibility text; the statute that defines the phrase is
    # quoted for the three pages that use it (Saj's call, 2026-11-11), dated and attributed, and tags municipality and county
    assert "The applicant must be a governmental agency" in program("ky_kia", "fund-b").eligibility_text
    for sid in ("fund-b", "fund-c", "fund-f"):
        quote = program("ky_kia", sid).eligibility_text
        assert 'KRS 224A.011(21), definition of "governmental agency", read 2026-11-11: ' in quote, sid
        assert "incorporated cities; counties" in quote and "water districts" in quote and "[...]" in quote, sid
        assert "not by way of limitation" not in quote, sid          # cut: the tagger drops a negated sentence
        assert tags("ky_kia", sid) == {"municipality", "county"}, sid
    # Fund A and the Cleaner Water grants name no applicant and borrow none
    assert tags("ky_kia", "fund-a") == set() and tags("ky_kia", "cleaner-water") == set()
    assert "KRS 224A" not in (program("ky_kia", "fund-a").eligibility_text or "")


def test_categories_funding_type_and_source():
    assert program("ky_dlgfed", "lwcf").category_pairs() == [("parks", "parks and recreation")]
    assert program("ky_dlgfed", "cdbg-facilities").category_pairs() == [("water", "wastewater")]
    assert program("ky_dlgfed", "arc").category_pairs() == [("infrastructure", "community development")]
    assert program("ky_tc", "tap").category_pairs() == [("transportation", "transportation")]
    for sid in ("fund-a", "fund-b", "fund-c", "fund-f"):
        assert program("ky_kia", sid).funding_type == "loan", sid          # "Fund A - Wastewater" carries no keyword
    assert program("ky_kia", "cleaner-water").funding_type == "grant"
    assert program("ky_kia", "fund-f").category_pairs() == [("water", "drinking water")]
    for sid in ("lwcf", "rtp", "rhp"):
        assert program("ky_dlgfed", sid).funding_source == "pass_through", sid
    assert program("ky_dlgfed", "cdbg-community").funding_source == "direct"   # DLG's page names no federal source; HUD is on the overview


def test_eec_grants_and_loans_page_is_six_records():
    eec = programs("ky_eec", "illegal-dump")
    # the first program keeps the page's id; the state revolving funds (KIA's Funds A and F) and UST claims are in no record
    assert list(eec) == ["illegal-dump", "illegal-dump#litter-abatement", "illegal-dump#nonpoint-source", "illegal-dump#waste-tire",
                         "illegal-dump#recycling-hhw", "illegal-dump#swpap"]
    assert [p.name for p in eec.values()][:2] == ["Illegal Dump Cleanup Grant Program", "Litter Abatement Grant Program"]
    assert all(p.funding_type == "grant" and p.status == "unknown" for p in eec.values())
    assert not any("Revolving" in p.name or "Underground" in p.name for p in eec.values())
    # "Funding Source: Kentucky Pride Fund" is direct; "U.S. Environmental Protection Agency" is a federal pass-through
    assert {sid: p.funding_source for sid, p in eec.items()} == {
        "illegal-dump": "direct", "illegal-dump#litter-abatement": "direct", "illegal-dump#nonpoint-source": "pass_through",
        "illegal-dump#waste-tire": "direct", "illegal-dump#recycling-hhw": "direct", "illegal-dump#swpap": "pass_through"}
    assert tags("ky_eec", "illegal-dump") == {"county"}                       # "Eligible Entities: County Governments"
    assert tags("ky_eec", "illegal-dump#litter-abatement") == {"municipality", "county"}
    assert tags("ky_eec", "illegal-dump#nonpoint-source") == set()            # "All entities are eligible to apply"
    assert eec["illegal-dump"].summary.startswith("The Division of Waste Management's Resource Conservation")   # not the label lines
    assert program("ky_eec", "illegal-dump").category_pairs() == [("other", "environment")]
    assert program("ky_eec", "illegal-dump#swpap").category_pairs() == [("water", "drinking water")]


def test_shared_table_edges():
    assert hl.META_LINE_RE.search("Funding Source: Kentucky Pride Fund")
    assert hl.summary_for([("p", "Administering Agency: X"), ("p", "The program funds roads.")]) == "The program funds roads."
    assert hl.funding_source_for([("p", "Funding Source: U.S. Environmental Protection Agency")], "") == "pass_through"
    assert hl.funding_source_for([("p", "Funding Source: Kentucky Pride Fund")], "") == "direct"
    assert hl.applicant_lines([("label", "Eligibility:"), ("li", "Cities")]) == ["Cities"]


def test_fetch_and_fallback(monkeypatch):
    m = mod("ky_eec")
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    slug = "illegal-dump"

    def site(client, url, broken=False):
        if broken:
            raise httpx.ConnectError("down")
        assert url == m.BASE + m.PAGES[slug]
        return (FIX / "ky_eec" / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    records = m.fetch()
    assert len(records) == 6 and records[0].source_id == "illegal-dump" and records[1].source_id == "illegal-dump#litter-abatement"
    assert len(m.fetch(limit=2)) == 2
    # an unreadable page keeps every stored record of the slug, split ones included
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=True))
    assert {r.source_id: r.payload for r in m.fetch(prior=prior)} == prior
    assert m.resolve_missing("illegal-dump#swpap") == {"status": "unknown"}


@pytest.mark.parametrize("name", AGENCIES)
def test_module_contract(name):
    m = mod(name)
    assert m.CONNECTOR == name and m.AGENCY_CODE.startswith("KY-") and m.CATEGORY_LABEL
    assert callable(m.fetch) and callable(m.normalize) and callable(m.resolve_missing)
