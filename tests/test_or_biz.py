"""Business Oregon connector tests, against the saved index and thirteen program pages (never the network): the two
views of the index, the page reader, the status table, applicants, categories, the fetch fallback."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from connectors import or_biz as ob
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "or_biz"
TODAY = date(2026, 11, 4)


def read(name: str) -> str:
    return (FIX / f"{name}.html").read_text(encoding="utf-8")


def programs() -> dict[str, dict]:
    return {p["source_id"]: p for p in ob.parse_index(read("index"))}


def normalize(sid: str, today: date = TODAY):
    page = ob.parse_page(read(sid.replace("/", "__")))
    return ob.normalize(RawRecord(source_connector=ob.CONNECTOR, source_id=sid, payload={"program": programs()[sid], "page": page}), today)


def test_fixtures_carry_no_scripts_or_addresses():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "@oregon.gov" not in text.replace("contact@example.oregon.gov", "")


def test_index_is_the_union_of_both_views_on_the_agency_host():
    got = programs()
    assert len(got) == 99
    assert sum(1 for p in got.values() if p["topic"]) == 76
    assert got["programs/cdbg"] == {"source_id": "programs/cdbg", "title": "Community Development Block Grants (CDBG)",
                                    "url": "https://www.oregon.gov/biz/programs/CDBG/Pages/default.aspx", "topic": "Infrastructure and Land Programs"}
    assert got["programs/hisf"]["topic"] is None   # alphabetical view only
    assert got["programs/rsia"]["topic"] == "Infrastructure and Land Programs"   # topic view only
    assert all(p["url"].startswith("https://www.oregon.gov/biz/") for p in got.values())
    assert "state-of-oregon-art-collection.org" in read("index") and "oregonartscommission.org" in read("index")


def test_source_ids():
    assert ob.source_id_for("https://www.oregon.gov/biz/programs/CDBG/Pages/default.aspx") == "programs/cdbg"
    assert ob.source_id_for("https://www.oregon.gov/biz/programs/BDP/DCTP/Pages/default.aspx") == "programs/bdp/dctp"
    assert ob.source_id_for("https://www.oregon.gov/biz/aboutus/artscommission/grants/for-organizations/arts-build-communities/Pages/default.aspx") == "aboutus/artscommission/grants/for-organizations/arts-build-communities"


def test_page_reader_takes_the_intro_and_body_once_each():
    page = ob.parse_page(read("programs__levee"))
    assert page["title"] == "Levee Project Grant Fund Program"
    kinds_texts = page["blocks"]
    assert ("label", "Who is Eligible?") in kinds_texts
    assert kinds_texts.count(("label", "Who is Eligible?")) == 1 and ("p", "Who is Eligible?") not in kinds_texts
    assert ("p", "-Municipalities;") in kinds_texts
    text = " ".join(t for _, t in kinds_texts)
    assert "Additional Resources" not in text and "@" not in text


def test_status_table():
    assert (normalize("programs/levee").status, normalize("programs/levee").rolling) == ("open", True)
    assert normalize("programs/levee").closes_at_text == "Applications are accepted year-round based on funding availability."
    assert normalize("programs/hisf").status == "closed"
    assert normalize("programs/sbma").status == "closed"
    assert normalize("programs/rsia").status == "closed"
    cdbg = normalize("programs/cdbg")
    assert (cdbg.status, cdbg.closes_at_text) == ("unknown", "February 1–April 30, applications accepted.")
    bdp = normalize("programs/bdp")
    assert (bdp.status, bdp.closes_at) == ("unknown", date(2024, 4, 25))
    abc = normalize("aboutus/artscommission/grants/for-organizations/arts-build-communities")
    assert abc.status == "unknown" and "accepted for further review" not in (abc.closes_at_text or "")
    assert normalize("programs/srf").status == "unknown" and normalize("programs/srf").closes_at_text is None


@pytest.mark.parametrize("sentence, closes, status, rolling", [
    ("Applications are accepted year-round based on funding availability.", None, "open", True),
    ("Business Oregon is now accepting applications through March 1, 2027.", date(2027, 3, 1), "open", None),
    ("Business Oregon is now accepting applications through March 1, 2026.", date(2026, 3, 1), "unknown", None),
    ("We're currently not accepting any applications at the moment.", None, "closed", None),
    ("This application period for this program is now closed.", None, "closed", None),
    ("Applications that meet program requirements are accepted for further review.", None, "unknown", None),
    ("Applications are open to public comments and challenges.", None, "unknown", None),
    ("No Longer Accepting Applications", None, "closed", None),
    ("The grant application window is currently closed.", None, "closed", None),
    (None, None, "unknown", None),
])
def test_status_for(sentence, closes, status, rolling):
    assert ob.status_for(sentence, closes, TODAY) == (status, rolling)


def test_applicants():
    assert [t.value for t in normalize("programs/cdbg").applicant_types] == ["municipality", "county", "tribe"]
    levee = normalize("programs/levee")
    assert levee.eligibility_text.startswith("-Municipalities;") and "municipality" in [t.value for t in levee.applicant_types]
    assert normalize("programs/srf").eligibility_text is None and normalize("programs/srf").applicant_types == []
    abc = normalize("aboutus/artscommission/grants/for-organizations/arts-build-communities")
    assert {t.value for t in abc.applicant_types} >= {"municipality", "nonprofit", "tribe"}


def test_fields_and_categories():
    p = normalize("programs/cdbg")
    assert (p.name, p.agency_code, p.jurisdiction, p.funding_type, p.funding_source) == ("Community Development Block Grants (CDBG)", "OR-BIZ", "OR", "grant", "pass_through")
    assert [(c.value, c.source_code) for c in p.categories] == [("infrastructure", "Infrastructure and Land Programs")]
    assert p.eligibility_structured == {"topic": "Infrastructure and Land Programs"} and p.summary
    assert normalize("programs/aggiebond").funding_type == "loan" and normalize("programs/aggiebond").categories == []
    assert normalize("programs/hisf").eligibility_structured is None and normalize("programs/bep").funding_type is None


def test_a_record_without_a_page_keeps_the_index_facts():
    raw = RawRecord(source_connector=ob.CONNECTOR, source_id="programs/cdbg", payload={"program": programs()["programs/cdbg"], "page": None})
    p = ob.normalize(raw, TODAY)
    assert p.name.startswith("Community Development") and p.status == "unknown" and p.summary is None and p.eligibility_text is None


class _Site:
    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        if url == ob.INDEX_URL:
            return read("index")
        sid = ob.source_id_for(url)
        path = FIX / f"{sid.replace('/', '__')}.html"
        return path.read_text(encoding="utf-8") if path.exists() else "<html><main><h1>x</h1></main></html>"


def test_fetch_reads_the_index_then_each_program_page(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    site = _Site()
    monkeypatch.setattr(ob, "_get", site)
    records = ob.fetch(limit=5)
    assert [r.source_id for r in records] == list(programs())[:5] and len(site.calls) == 6
    full = ob.fetch()
    assert len(full) == 99 and all(r.payload["page"] is not None for r in full)
    prior = {r.source_id: r.payload for r in full}
    url = programs()["programs/cdbg"]["url"]
    monkeypatch.setattr(ob, "_get", _Site(broken={url}))
    again = {r.source_id: r.payload for r in ob.fetch(prior=prior)}
    assert again["programs/cdbg"]["page"] == prior["programs/cdbg"]["page"]
    assert {r.source_id: r.payload for r in ob.fetch()}["programs/cdbg"]["page"] is None
    monkeypatch.setattr(ob, "_get", _Site(broken={ob.INDEX_URL}))
    with pytest.raises(httpx.ConnectError):
        ob.fetch()


def test_resolve_missing_is_unknown():
    assert ob.resolve_missing("programs/cdbg") == {"status": "unknown"}
