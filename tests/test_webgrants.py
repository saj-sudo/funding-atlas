"""WebGrants storefront connector tests. Everything runs against the saved pages (never the network): three lists
(Iowa, Montana Agriculture, and Montana Fish, Wildlife and Parks with no rows) and six detail pages."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import webgrants as wg
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "webgrants"
TODAY = date(2026, 10, 28)
ENERGY, CDBG, TAX, NODESC = "ia-230028", "ia-666997", "ia-371353", "ia-667406"
WEED, POTATO = "mtagr-27785", "mtagr-28249"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def list_rows(key: str) -> list[dict[str, str]]:
    return wg.parse_list(read(f"{key}_list.html"))


def row_for(source_id: str) -> dict[str, str]:
    key, ident = source_id.split("-", 1)
    return next(r for r in list_rows(key) if r["id"] == ident)


def payload(source_id: str) -> dict:
    key = source_id.split("-", 1)[0]
    return {"host": key, "list": row_for(source_id), "detail": wg.parse_detail(read(f"detail_{source_id}.html"))}


def normalize(source_id: str):
    return wg.normalize(RawRecord(source_connector=wg.CONNECTOR, source_id=source_id, payload=payload(source_id)), TODAY)


# ---------- the list ----------

def test_lists_parse_by_header_name():
    assert [r["id"] for r in list_rows("ia")] == ["230028", "371353", "666997", "667406"]
    assert [r["id"] for r in list_rows("mtagr")] == ["27785", "28249"]
    energy = row_for(ENERGY)
    assert energy["title"] == "Iowa Energy Center Grant Program" and energy["agency"] == "Economic Development Authority"
    assert energy["status"] == "Posted" and energy["pre_due"] == "Sep 17, 2026 8:30 AM"
    assert energy["final_due"] == "Nov 2, 2026 11:59 PM" and energy["oid"] == "1506540313360|Opportunity"
    assert energy["categorical_area"] == "Community Development,Economic Development,Energy"


def test_a_table_with_no_rows_is_an_empty_list():
    assert list_rows("mtfwp") == []
    assert wg.parse_list("<html>no table</html>") == []


def test_a_column_that_is_missing_does_not_shift_the_others():
    html = ("<table id='storefrontFO'><thead><tr><th>ID</th><th>Status</th><th>Title</th>"
            "<th>Final-Application Due Date</th></tr></thead><tbody><tr><td>1</td><td>Posted</td>"
            "<td><a href='viewStorefrontOpportunity.do?OIDString=9|Opportunity'>T</a></td><td>Jan 2, 2027 5:00 PM</td></tr>"
            "</tbody></table>")
    assert wg.parse_list(html) == [{"id": "1", "status": "Posted", "title": "T", "final_due": "Jan 2, 2027 5:00 PM", "oid": "9|Opportunity"}]


# ---------- the detail page ----------

def test_detail_fields_and_blocks():
    detail = payload(ENERGY)["detail"]
    assert detail["fields"]["Award Amount Range"] == "No Limit - $1,000,000.00"
    assert detail["fields"]["Recurring Opportunity"] == "No" and detail["fields"]["Status"] == "Posted"
    assert any(text == "Eligible Applicants" and heading for _, text, heading in detail["blocks"])


def test_a_page_without_a_description_has_no_blocks():
    detail = payload(NODESC)["detail"]
    assert detail["blocks"] == [] and detail["fields"]["Status"] == "Posted"


def test_eligibility_sections_open_at_the_label_and_close_at_the_next_heading():
    sections = wg.eligibility_sections(payload(ENERGY)["detail"]["blocks"])
    assert [h for h, _ in sections] == ["Eligible Applicants", "Eligibility Requirements"]
    assert sections[0][1][0][1].startswith("Iowa Businesses, colleges and universities")
    assert not any(text == "Ineligible Projects" for _, lines in sections for _, text in lines)


def test_an_all_caps_heading_with_a_colon_opens_a_section():
    blocks = [["p", "ELIGIBLE APPLICANTS:", True], ["p", "School districts may apply.", False], ["p", "HOW TO APPLY", True],
              ["p", "Cities, send a letter.", False]]
    assert wg.eligibility_sections(blocks) == [("ELIGIBLE APPLICANTS", [("p", "School districts may apply.")])]


# ---------- applicants ----------

def tags(source_id: str) -> set[str]:
    return {t.value for t in normalize(source_id).applicant_types}


def test_applicants_from_the_eligible_applicants_section():
    assert tags(ENERGY) == {"business", "higher_ed", "nonprofit"}


def test_the_municipal_round_names_local_governments_and_tribes():
    assert tags(CDBG) == {"municipality", "county", "tribe"}
    assert "Units of General Local Government" in normalize(CDBG).eligibility_text


def test_a_negated_sentence_does_not_tag_even_beside_the_applicant_sentence():
    """Units of government (cities, counties) are not eligible to apply for credits."""
    p = normalize(TAX)
    assert "cities, counties" in p.eligibility_text and p.applicant_types == []


def test_pages_without_an_eligibility_heading_get_no_applicants():
    assert tags(WEED) == set() and tags(NODESC) == set()
    assert normalize(WEED).eligibility_text is None


def test_paragraph_list_items_after_a_colon_are_a_known_gap():
    """Montana's potato page lists 'Local Governments' as plain paragraphs, so only the lead-in sentence is read."""
    assert tags(POTATO) == {"individual"}


def test_applicant_sentences_stop_at_a_condition_lead_in():
    lines = [("p", "Nonprofits may apply."), ("p", "Buildings must meet these criteria:"), ("li", "Located in a city")]
    assert wg.applicant_sentences(lines) == ["Nonprofits may apply."]


# ---------- mapping ----------

def test_energy_round_fields():
    p = normalize(ENERGY)
    assert p.source_url == "https://www.iowagrants.gov/viewStorefrontOpportunity.do?OIDString=1506540313360|Opportunity"
    assert (p.external_number, p.level, p.jurisdiction) == ("230028", "state", "IA")
    assert (p.administering_agency, p.agency_code, p.funding_type, p.funding_source) == ("Economic Development Authority", None, "grant", "direct")
    assert (p.amount_min, p.amount_max) == (None, 1000000)
    assert (p.status, p.opens_at, p.closes_at) == ("open", date(2026, 8, 24), date(2026, 11, 2))
    assert p.closes_at_text == "Pre-application due: 2026-09-17" and p.rolling is None
    assert p.summary.startswith("The Iowa Energy Center Grant Program")
    assert p.eligibility_structured == {"categorical_area": ["Community Development", "Economic Development", "Energy"], "recurring": "No"}


def test_montana_host_is_montana():
    p = normalize(WEED)
    assert p.jurisdiction == "MT" and p.administering_agency == "Department of Agriculture"
    assert p.source_url.startswith("https://mtagr.webgrantscloud.com/")


def test_no_final_deadline_is_rolling_and_a_tax_credit_keeps_its_type():
    p = normalize(TAX)
    assert p.closes_at is None and p.rolling is True and p.funding_type == "tax_credit"


@pytest.mark.parametrize("pre, final, recurring, expected", [
    ("Sep 17, 2026 8:30 AM", "Nov 2, 2026 11:59 PM", "No", "Pre-application due: 2026-09-17"),
    ("Nov 16, 2026 12:00 PM", "Nov 16, 2026 12:00 PM", "No", None),       # the list repeats the final date (round 687121)
    ("Not Applicable", "Nov 2, 2026 11:59 PM", "Yes", "Recurring opportunity"),
    ("Sep 17, 2026 8:30 AM", "Nov 2, 2026 11:59 PM", "Yes", "Pre-application due: 2026-09-17; Recurring opportunity"),
    ("Not Applicable", "Not Applicable", "", None),
])
def test_closes_text_for(pre, final, recurring, expected):
    assert wg.closes_text_for(pre, final, recurring) == expected


def test_recurring_yes_feeds_the_cycle_text_not_rolling():
    p = normalize(NODESC)
    assert p.closes_at_text == "Recurring opportunity" and p.rolling is None
    assert p.summary is None and p.eligibility_text is None


def test_the_program_officer_is_in_neither_the_payload_nor_the_record():
    assert "Buckingham" in read(f"detail_{ENERGY}.html")          # the page has it
    assert "Buckingham" not in str(payload(ENERGY)) and "Program Officer" not in payload(ENERGY)["detail"]["fields"]
    p = normalize(ENERGY)
    for value in (p.summary, p.eligibility_text, str(p.eligibility_structured)):
        assert "Buckingham" not in (value or "")


@pytest.mark.parametrize("label, posted, final, expected", [
    ("Posted", date(2026, 8, 1), date(2026, 11, 1), "open"),
    ("Posted", date(2026, 8, 1), None, "open"),
    ("Posted", date(2026, 8, 1), date(2026, 10, 28), "open"),
    ("Posted", date(2026, 8, 1), date(2026, 10, 27), "closed"),
    ("Posted", date(2026, 11, 1), date(2026, 12, 1), "forecasted"),
    ("Closed", date(2026, 8, 1), date(2026, 12, 1), "unknown"),
    ("", None, None, "unknown"),
])
def test_status_for(label, posted, final, expected):
    assert wg.status_for(label, posted, final, TODAY) == expected


@pytest.mark.parametrize("text, expected", [
    ("No Limit - $1,000,000.00", (None, 1000000)), ("$5,000.00 - $50,000.00", (5000, 50000)),
    ("Not Applicable", (None, None)), ("No Limit - No Limit", (None, None)), ("", (None, None)),
])
def test_amount_fields(text, expected):
    assert wg.amount_fields(text) == expected


def test_categories_use_the_shared_table_and_skip_unspecified():
    assert [(t.value, t.source_code) for t in wg.category_tags("Disaster Assistance,Child Health,Agriculture,Unspecified")] == [
        ("public_safety", "Disaster Assistance"), ("health", "Child Health"), ("other", "Agriculture"),
    ]
    assert wg.category_tags("") == []


def test_every_saved_round_normalizes():
    for source_id in (ENERGY, CDBG, TAX, NODESC, WEED, POTATO):
        p = normalize(source_id)
        assert p.name and p.status == "open" and p.source_url.startswith("https://")


# ---------- fetch ----------

class _Pages:
    """A stand-in for `_get`: URL -> saved page. `broken` URLs raise a connection error."""

    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        for key, (base, _) in wg.HOSTS.items():
            if url == base + wg.LIST_PATH:
                return read(f"{key}_list.html")
            if url.startswith(base + "/viewStorefrontOpportunity.do?OIDString="):
                oid = url.split("OIDString=", 1)[1]
                row = next(r for r in list_rows(key) if r["oid"] == oid)
                return read(f"detail_{key}-{row['id']}.html")
        raise AssertionError(url)


@pytest.fixture
def pages(monkeypatch):
    monkeypatch.setattr(wg.time, "sleep", lambda s: None)
    stub = _Pages()
    monkeypatch.setattr(wg, "_get", stub)
    return stub


def test_fetch_reads_every_list_and_every_detail(pages):
    records = wg.fetch()
    assert [r.source_id for r in records] == ["ia-230028", "ia-371353", "ia-666997", "ia-667406", "mtagr-27785", "mtagr-28249"]
    assert sum(1 for u in pages.calls if wg.LIST_PATH in u) == 3
    assert records[0].payload["host"] == "ia" and records[0].payload["detail"]["fields"]["Status"] == "Posted"
    assert len(wg.fetch(limit=2)) == 2


def test_an_unreadable_detail_falls_back_to_the_stored_copy(monkeypatch, pages):
    first = {r.source_id: r.payload for r in wg.fetch()}
    bad = "https://www.iowagrants.gov/viewStorefrontOpportunity.do?OIDString=" + row_for(ENERGY)["oid"]
    monkeypatch.setattr(wg, "_get", _Pages(broken={bad}))
    again = {r.source_id: r.payload for r in wg.fetch(prior=first)}
    assert again[ENERGY]["detail"] == first[ENERGY]["detail"]
    without = {r.source_id: r.payload for r in wg.fetch()}
    assert without[ENERGY]["detail"] is None
    p = wg.normalize(RawRecord(source_connector=wg.CONNECTOR, source_id=ENERGY, payload=without[ENERGY]), TODAY)
    assert p.name == "Iowa Energy Center Grant Program" and p.amount_max is None and p.applicant_types == []


def test_an_unreadable_list_aborts_the_run(monkeypatch, pages):
    monkeypatch.setattr(wg, "_get", _Pages(broken={"https://mtagr.webgrantscloud.com" + wg.LIST_PATH}))
    with pytest.raises(httpx.ConnectError):
        wg.fetch()


# ---------- _get, through a real client ----------

def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_get_retries_a_dropped_connection(monkeypatch):
    monkeypatch.setattr(wg.time, "sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("reset")
        return httpx.Response(200, text="ok")

    assert wg._get(_client(handler), "https://x.test/") == "ok" and len(calls) == 3


def test_get_gives_up_after_three_tries(monkeypatch):
    monkeypatch.setattr(wg.time, "sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectError("reset")

    with pytest.raises(httpx.ConnectError):
        wg._get(_client(handler), "https://x.test/")
    assert len(calls) == wg.TRIES


def test_get_does_not_retry_an_http_error_status():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500, text="boom")

    with pytest.raises(httpx.HTTPStatusError):
        wg._get(_client(handler), "https://x.test/")
    assert len(calls) == 1


# ---------- resolve_missing ----------

def test_a_round_that_left_the_list_is_unknown_without_a_request(monkeypatch):
    monkeypatch.setattr(wg, "_get", lambda *a: pytest.fail("no request"))
    monkeypatch.setattr(wg, "_client", lambda: pytest.fail("no client"))
    assert wg.resolve_missing(ENERGY) == {"status": "unknown"}
