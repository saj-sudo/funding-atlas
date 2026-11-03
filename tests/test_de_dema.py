"""Delaware DEMA connector tests, against the saved grants page and preparedness tab (never the network)."""

from __future__ import annotations

from pathlib import Path

import httpx

from connectors import de_dema as de
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "de_dema"


def read(name: str) -> str:
    return (FIX / f"{name}.html").read_text(encoding="utf-8")


def records() -> dict[str, RawRecord]:
    details = de.parse_preparedness(read("preparedness"))
    return {e["id"]: RawRecord(source_connector=de.CONNECTOR, source_id=e["id"], payload={"entry": e, "details": details.get(e["id"])})
            for e in de.parse_entries(read("grants"))}


def normalize(entry_id: str):
    return de.normalize(records()[entry_id])


def test_entries_from_both_accordions():
    ids = list(records())
    assert ids[:4] == ["NSGP", "SLCGP", "HSGP", "EMPG"] and "publicAssistance" in ids and "hazard-mitigation" in ids
    assert len(ids) == 10
    e = records()["HSGP"].payload["entry"]
    assert e["name"] == "Homeland Security Grant Program (HSGP)" and e["section"] == "Preparedness Grants"
    assert e["blurb"].startswith("Supports state, local, tribal, and territorial governments")
    assert e["url"] == "https://dema.delaware.gov/about/grants/index.shtml?dc=preparednessgrants#HSGP"


def test_preparedness_blocks_give_subrecipient_projects_and_apply():
    details = de.parse_preparedness(read("preparedness"))
    assert set(details) == {"NSGP", "SLCGP", "HSGP", "EMPG"}
    assert details["NSGP"]["eligible"].startswith("Nonprofit organizations that (1) meet the description under 501[C3]")
    assert details["HSGP"]["eligible"].startswith("[Invitation Only] State and local government agencies")
    assert "annually in the spring" in details["NSGP"]["apply"] and details["NSGP"]["projects"]


def test_applicants_from_the_subrecipient_paragraph_only():
    assert {t.value for t in normalize("NSGP").applicant_types} == {"nonprofit"}
    assert {"municipality", "county", "tribe"} <= {t.value for t in normalize("HSGP").applicant_types}
    assert normalize("HSGP").eligibility_structured["invitation_only"] is True
    assert normalize("hazard-mitigation").applicant_types == [] and normalize("hazard-mitigation").eligibility_text is None


def test_fields_and_categories():
    p = normalize("EMPG")
    assert (p.status, p.funding_source, p.funding_type, p.jurisdiction, p.agency_code) == ("unknown", "pass_through", "grant", "DE", "DE-DEMA")
    assert p.category_pairs() == [("public_safety", "Preparedness Grants")]
    assert normalize("publicAssistance").category_pairs() == [("public_safety", "Recovery Assistance")]
    assert p.closes_at_text == "This program is by invitation only." and p.eligibility_structured["invitation_only"] is True
    assert "annually in the spring" in normalize("NSGP").closes_at_text and normalize("NSGP").closes_at is None
    assert normalize("flood-mitigation-assistance").source_url.startswith("https://www.fema.gov/")


def test_fixtures_carry_no_scripts_or_contacts():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "@delaware.gov" not in text.replace("example.delaware.gov", "")


def test_fetch_and_fallback(monkeypatch):
    monkeypatch.setattr(de.time, "sleep", lambda s: None)
    pages = {de.GRANTS_URL: "grants", de.PREP_URL: "preparedness"}
    monkeypatch.setattr(de, "_get", lambda client, url: read(pages[url]))
    recs = de.fetch()
    assert len(recs) == 10 and recs[0].payload["details"]["eligible"]
    prior = {r.source_id: r.payload for r in recs}

    def broken_prep(client, url):
        if url == de.PREP_URL:
            raise httpx.ConnectError("down")
        return read(pages[url])
    monkeypatch.setattr(de, "_get", broken_prep)
    again = {r.source_id: r.payload for r in de.fetch(prior=prior)}
    assert again["NSGP"]["details"] == prior["NSGP"]["details"]
    assert len(de.fetch(limit=2)) == 2
    assert de.resolve_missing("NSGP") == {"status": "unknown"}
