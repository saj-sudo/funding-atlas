"""Virginia DCJS connector tests. Everything runs against the saved pages (never the network): the view trimmed to
five rows plus one repeat, and five program pages with their contact block removed."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import va_dcjs as va
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "va_dcjs"
TODAY = date(2026, 11, 3)
AID_599 = "fy-2027-state-aid-localities-police-departments-599"
SSO = "fy-2027-school-safety-officer-program"
JJDP = "virginia-juvenile-justice-and-delinquency-prevention-and-intervention-summer-grant"
OPIOID = "cy-2027-2029-virginia-opioid-use-reduction-and-jail-based-substance-use-disorder"
FVIP = "firearm-violence-intervention-and-prevention-fvip-grant-program-cy2026-2027"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def rows() -> dict[str, dict]:
    return {r["slug"]: r for r in va.parse_rows(read("grants.html"))}


def program(slug: str) -> dict:
    return va.parse_program(read(f"program_{slug}.html"))


def normalize(slug: str, today: date = TODAY):
    return va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id=slug, payload={"row": rows()[slug], "program": program(slug)}), today)


# ---------- the view ----------

def test_rows_parse_with_iso_dates_and_the_repeat_dropped():
    got = rows()
    assert set(got) == {AID_599, SSO, JJDP, OPIOID, FVIP} and len(got) == 5
    assert list(got)[0] == OPIOID                                   # view order: latest due date first
    r = got[AID_599]
    assert r["url"] == f"https://www.dcjs.virginia.gov/grants/programs/{AID_599}"
    assert r["title"].startswith("FY 2027 State Aid to Localities with Police Departments")
    assert r["due"] == "2026-08-04T21:00:00Z" and r["posted"] == "2026-07-07T12:00:00Z"
    assert read("grants.html").count(f"/grants/programs/{OPIOID}") >= 2       # the first row is repeated in the fixture


def test_fixtures_carry_no_scripts_or_contact_block():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "Grant Coordinator" not in text


# ---------- a program page ----------

def test_body_is_the_content_block_not_the_mega_menu():
    p = program(SSO)
    assert p["title"] == "FY 2027 School Safety Officer Program"
    assert p["paragraphs"] and not any("Meet the Director" in t for t in p["paragraphs"])
    assert (p["due"][:10], p["posted"][:10], p["archive"][:10]) == ("2026-03-10", "2026-02-10", "2027-03-10")


def test_eligibility_under_a_heading():
    assert program(SSO)["eligibility"][0].startswith("Local units of government are eligible to apply.")


def test_eligibility_under_a_bold_run_label():
    passage = program(AID_599)["eligibility"]
    assert passage and any("locality" in line for line in passage)


def test_a_page_without_the_passage_has_none():
    assert program(OPIOID)["eligibility"] == [] and normalize(OPIOID).eligibility_text is None
    assert normalize(OPIOID).applicant_types == []


def test_eligibility_passage_stops_at_the_next_label():
    body = va._soup("<div id='block-uswds-base-subtheme-content'><div class='field--name-body'>"
                    "<h3>Eligibility</h3><p>Counties may apply.</p><ul><li>Towns too.</li></ul>"
                    "<h3>Application Guidelines and Procedures</h3><p>Cities are mentioned here but this is not it.</p>"
                    "<p><strong>Eligible Applicants:</strong> Nonprofits.</p><p>Still on.</p><p><strong>Contact:</strong></p><p>Off.</p>"
                    "</div></div>").select_one(va.BODY_SELECTOR)
    assert va.eligibility_passage(body) == ["Counties may apply.", "Towns too.", "Nonprofits.", "Still on."]


def test_guidelines_pdfs_are_kept_as_urls_only():
    g = program(AID_599)["guidelines"]
    assert g and all(u.startswith("https://www.dcjs.virginia.gov/") and u.lower().endswith(".pdf") for u in g)
    assert normalize(AID_599).eligibility_structured["guidelines"] == g


# ---------- status and dates ----------

@pytest.mark.parametrize("due, status", [
    (date(2026, 11, 3), "open"), (date(2026, 12, 1), "open"), (date(2026, 11, 2), "closed"), (None, "unknown"),
])
def test_status_for(due, status):
    assert va.status_for(due, TODAY) == status


def test_dates_come_from_the_page_and_status_from_the_due_date():
    p = normalize(SSO)
    assert (p.opens_at, p.closes_at, p.status) == (date(2026, 2, 10), date(2026, 3, 10), "closed")
    assert normalize(SSO, today=date(2026, 3, 10)).status == "open"
    assert p.eligibility_structured["due_at"].startswith("2026-03-10T") and p.eligibility_structured["archive_date"] == "2027-03-10"


def test_row_dates_are_used_when_the_page_could_not_be_read():
    p = va.normalize(RawRecord(source_connector=va.CONNECTOR, source_id=SSO, payload={"row": rows()[SSO], "program": None}), TODAY)
    assert (p.closes_at, p.status, p.summary, p.eligibility_text) == (date(2026, 3, 10), "closed", None, None)


@pytest.mark.parametrize("value, expected", [("2026-08-04T21:00:00Z", date(2026, 8, 4)), ("", None), ("soon", None)])
def test_parse_iso_date(value, expected):
    assert va.parse_iso_date(value) == expected


# ---------- applicants ----------

def test_localities_and_local_units_of_government_tag_municipality_and_county():
    assert {t.value for t in normalize(AID_599).applicant_types} == {"municipality", "county"}
    assert {t.source_code for t in normalize(AID_599).applicant_types} == {"localities"}
    assert {t.value for t in normalize(SSO).applicant_types} == {"municipality", "county"}


def test_the_negated_sentence_is_dropped_and_the_statement_kept():
    p = normalize(JJDP)
    assert "is not open to" in p.eligibility_text
    assert {t.value for t in p.applicant_types} == {"municipality", "county"}


def test_nonprofits_only():
    assert "nonprofit" in {t.value for t in normalize(FVIP).applicant_types}
    assert not {"municipality", "county"} & {t.value for t in normalize(FVIP).applicant_types}


# ---------- mapping ----------

def test_fields():
    p = normalize(AID_599)
    assert (p.level, p.jurisdiction, p.administering_agency, p.agency_code) == ("state", "VA", "Department of Criminal Justice Services", "VA-DCJS")
    assert (p.funding_type, p.funding_source, p.amount_min, p.match_required, p.rolling, p.categories, p.alns) == ("grant", "direct", None, None, None, [], [])
    assert p.source_url.endswith(AID_599) and p.external_number is None and p.closes_at_text is None
    assert p.summary and "accepting applications through" not in p.summary


def test_summary_skips_the_ogms_boilerplate():
    assert va.summary_for(["DCJS is accepting applications through OGMS for X.", "The purpose is Y."]) == "The purpose is Y."
    assert va.summary_for(["DCJS is accepting applications through OGMS for X."]) == "DCJS is accepting applications through OGMS for X."
    assert va.summary_for([]) is None


def test_every_saved_row_normalizes():
    for slug in rows():
        p = normalize(slug)
        assert p.name and p.status == "closed" and p.record_hash


# ---------- fetch ----------

class _Pages:
    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        if url == va.LIST_URL:
            return read("grants.html")
        return read(f"program_{url.rsplit('/', 1)[-1]}.html")


@pytest.fixture
def pages(monkeypatch):
    monkeypatch.setattr(va.time, "sleep", lambda s: None)
    stub = _Pages()
    monkeypatch.setattr(va, "_get", stub)
    return stub


def test_fetch_reads_the_view_then_every_program_page(pages):
    records = va.fetch()
    assert [r.source_id for r in records] == list(rows())
    assert pages.calls == [va.LIST_URL] + [r["url"] for r in rows().values()]
    assert records[0].payload["program"]["title"].startswith("CY 2027-2029 Virginia Opioid")
    assert len(va.fetch(limit=2)) == 2


def test_an_unreadable_program_page_falls_back_to_prior(monkeypatch, pages):
    first = {r.source_id: r.payload for r in va.fetch()}
    monkeypatch.setattr(va, "_get", _Pages(broken={rows()[SSO]["url"]}))
    again = {r.source_id: r.payload for r in va.fetch(prior=first)}
    assert again[SSO]["program"] == first[SSO]["program"]
    assert {r.source_id: r.payload for r in va.fetch()}[SSO]["program"] is None


def test_an_unreadable_view_aborts(monkeypatch, pages):
    monkeypatch.setattr(va, "_get", _Pages(broken={va.LIST_URL}))
    with pytest.raises(httpx.ConnectError):
        va.fetch()


# ---------- resolve_missing ----------

def test_resolve_missing_reads_the_page_back(monkeypatch):
    monkeypatch.setattr(va, "_get", lambda client, url: read(f"program_{SSO}.html"))
    assert va.resolve_missing(SSO) == {"status": "closed", "closes_at": date(2026, 3, 10)}
    due_at = program(SSO)["due"]
    monkeypatch.setattr(va, "_get", lambda client, url: read(f"program_{SSO}.html").replace(due_at, "2099-03-10T17:00:00Z"))
    assert va.resolve_missing(SSO) == {"status": "unknown"}

    def boom(client, url):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(va, "_get", boom)
    assert va.resolve_missing(SSO) is None
