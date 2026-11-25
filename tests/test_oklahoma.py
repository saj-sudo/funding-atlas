"""Oklahoma Department of Commerce (ok_commerce) against saved pages (12.9)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx

from connectors import hand_list as hl
from connectors import ok_commerce as m
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "ok_commerce"
TODAY = date(2026, 11, 24)
HUB_IDS = ["cdbg", "cdbg#small-cities", "cdbg#community-revitalization", "cdbg#water-wastewater-construction", "cdbg#edif",
           "cdbg#water-wastewater-engineering", "cdbg#reap"]


def page(slug: str) -> dict:
    return m.parse_page((FIX / f"{slug}.html").read_text(encoding="utf-8"))


def every(today: date = TODAY) -> dict:
    out: dict = {}
    for slug, path in m.PAGES.items():
        for sid, payload in m.SITE.records_for(slug, path, [page(slug)], 0):
            out[sid] = m.normalize(RawRecord(source_connector="ok_commerce", source_id=sid, payload=payload), today)
    return out


def tags(p) -> set[str]:
    return {t.value for t in p.applicant_types}


def no_pdf(client, url):
    raise httpx.ConnectError("down")


def test_the_hub_is_seven_records_and_the_fund_one():
    progs = every()
    assert list(progs) == HUB_IDS + ["odmrmf"]
    assert progs["cdbg"].name == "CDBG Capital Improvement Planning (CIP)"          # the first program keeps the page's id
    assert progs["cdbg#edif"].name == "CDBG Economic Development Infrastructure Financing (EDIF)"
    assert progs["cdbg#reap"].name == "CDBG Rural Economic Action Plan (REAP)"
    assert progs["odmrmf"].name == "Oklahoma Disaster Mitigation and Recovery Matching Fund Program (ODMRMF)"
    assert all(p.jurisdiction == "OK" and p.agency_code == "OK-COMMERCE" for p in progs.values())
    assert all(p.source_url == m.BASE + m.PAGES["cdbg"] for sid, p in progs.items() if sid != "odmrmf")
    assert progs["cdbg#small-cities"].summary.startswith("Oklahoma’s Small Cities program helps fund infrastructure")


def test_what_is_not_read():
    hub = " ".join(t for _, t in page("cdbg")["blocks"])
    # the SAM.gov how-to, the trainings, the State Plan hearing notice and its comment period, the resources
    for gone in ("DUNs", "Save the Dates", "Continuing Education", "Public Hearing", "December 18, 2026", "Davis Bacon",
                 "Section 3", "CIP Guidance", "Program Objectives"):
        assert gone not in hub, gone
    assert "Eligibility is generally limited to units of general local government" in hub
    # Coronavirus Relief and the Disaster Recovery entries are on the page and in no record
    assert "Coronavirus Relief" in hub and "Disaster Recovery" in hub
    records = dict(m.SITE.records_for("cdbg", m.PAGES["cdbg"], [page("cdbg")], 0))
    for sid, payload in records.items():
        text = " ".join(t for _, t in payload["page"]["blocks"])
        assert "Coronavirus" not in text and "Disaster Recovery" not in text, sid
    fund = [t for _, t in page("odmrmf")["blocks"]]
    assert "SWODA" in fund and not any("Policies" in t or "Annual Reporting" in t or "Return to top" in t for t in fund)


def test_no_page_states_a_round():
    for today in (TODAY, date(2026, 9, 1)):       # before the hearing's comment period closes too: it is not a round
        for sid, p in every(today).items():
            assert (p.status, p.opens_at, p.closes_at, p.closes_at_text) == ("unknown", None, None, None), sid


def test_funding_source_applicants_and_categories():
    progs = every()
    assert all(progs[sid].funding_source == "pass_through" for sid in HUB_IDS)          # "... from ... (HUD)"
    assert progs["odmrmf"].funding_source == "direct"                                   # "provided by the State Treasury"
    for sid in HUB_IDS:
        assert tags(progs[sid]) == {"municipality", "county"}, sid
        assert "units of general local government such as cities, towns, and counties" in progs[sid].eligibility_text
    assert "may apply under this category" in progs["cdbg#water-wastewater-construction"].eligibility_text
    # the fund's applicants are the planning districts: its purpose sentence ("to help local governments") tags no one
    fund = progs["odmrmf"]
    assert tags(fund) == set()
    assert "Substate Planning Districts (SSPDs) or Councils of Government (COGs)" in fund.eligibility_text
    assert "ACOG" in fund.eligibility_text and "to help local governments" not in fund.eligibility_text
    assert "to help local governments" in fund.summary
    cats = {sid: [c.value for c in p.categories] for sid, p in progs.items()}
    assert cats["cdbg"] == ["infrastructure"] and cats["cdbg#water-wastewater-engineering"] == ["water"]
    assert cats["cdbg#water-wastewater-construction"] == ["water"] and cats["odmrmf"] == ["public_safety"]
    assert all(p.funding_type == "grant" for p in progs.values())


def test_no_contact_is_stored():
    for slug in m.PAGES:
        text = " ".join(t for _, t in page(slug)["blocks"])
        assert "@" not in text and "405-" not in text and "800-" not in text, slug


def test_fetch_and_fallback(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(hl.time, "sleep", slept.append)

    def site(client, url, broken=()):
        if url in broken:
            raise httpx.ConnectError("down")
        slug = next(s for s, p in m.PAGES.items() if url == m.BASE + p)
        return (FIX / f"{slug}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(hl, "get", site)
    monkeypatch.setattr(m, "get_pdf", no_pdf)
    records = m.fetch()
    assert [r.source_id for r in records] == HUB_IDS + ["odmrmf"]
    assert slept == [3.0] * (1 + len(HUB_IDS))   # the second page, then each program's guidance PDF
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", lambda c, u: site(c, u, broken=(m.BASE + m.PAGES["cdbg"],)))
    again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
    assert list(again) == HUB_IDS + ["odmrmf"] and again["cdbg#reap"] == prior["cdbg#reap"]
    assert [r.source_id for r in m.fetch(prior={})] == ["odmrmf"]


# ---------- 12.12: the guidance PDFs ----------
GUIDE = FIX / "guidance"
PDFS = {
    "cdbg": "2026-CDBG-CIP-Application-Guidelines.pdf",
    "cdbg#small-cities": "2026-CDBG-Small-Cities-Application-Guidelines.pdf",
    "cdbg#community-revitalization": "2026-CDBG-CR-Application-Guidelines.pdf",
    "cdbg#water-wastewater-construction": "2026-CDBG-WW-Construction-Application-Guidelines.pdf",
    "cdbg#edif": "2026-CDBG-Economic-Development-Infrastructure-Financing-EDIF-Application-Guidelines.pdf",
    "cdbg#water-wastewater-engineering": "2026-WW-Engineering-Application-Guidance.pdf",
    "cdbg#reap": "2026-CDBG-REAP-Application-Guidelines.pdf",
}


def with_guidance(today: date) -> dict:
    """Each hub record as stored after a run that read its PDF: the sentences are those the 2026 PDFs gave on
    2026-11-25 (`guidance/sentences.json`, from the full files; two excerpts are kept as PDFs)."""
    said = json.loads((GUIDE / "sentences.json").read_text(encoding="utf-8"))
    out = {}
    for sid, payload in m.SITE.records_for("cdbg", m.PAGES["cdbg"], [page("cdbg")], 0):
        payload["guidance"] = {"url": payload["guidance_url"], "sentences": said[sid]}
        out[sid] = m.normalize(RawRecord(source_connector="ok_commerce", source_id=sid, payload=payload), today)
    return out


def test_each_program_links_its_own_guidance_pdf():
    payloads = dict(m.SITE.records_for("cdbg", m.PAGES["cdbg"], [page("cdbg")], 0))
    assert {sid: p["guidance_url"].rsplit("/", 1)[1] for sid, p in payloads.items()} == PDFS
    assert all(p["guidance_url"].startswith("https://www.okcommerce.gov/wp-content/uploads/") for p in payloads.values())
    assert all("guidance" not in p["page"] for p in payloads.values())   # the link map is not stored with the page
    (fund,) = m.SITE.records_for("odmrmf", m.PAGES["odmrmf"], [page("odmrmf")], 0)
    assert "guidance_url" not in fund[1]


def test_pdf_sentences_keep_application_deadlines_only():
    cr = m.pdf_sentences((GUIDE / "community-revitalization.pdf").read_bytes())
    assert cr == ["All CDBG Community Revitalization applications must be completed online no later than March 27, 2026, 5:00 p.m."]
    assert m.pdf_sentences((GUIDE / "edif.pdf").read_bytes()) == []
    # a Letter of Intent, a closeout or an audit date names no application
    said = json.loads((GUIDE / "sentences.json").read_text(encoding="utf-8"))
    assert not any("Letter of Intent" in s or "closeout" in s.lower() or "audit" in s.lower() for v in said.values() for s in v)


def test_the_pdf_dates_the_round_the_page_does_not_state():
    closes = {"cdbg": date(2026, 7, 10), "cdbg#small-cities": date(2026, 6, 19), "cdbg#community-revitalization": date(2026, 3, 27),
              "cdbg#water-wastewater-construction": date(2026, 5, 1), "cdbg#water-wastewater-engineering": date(2026, 5, 1),
              "cdbg#reap": date(2026, 2, 27)}
    before = with_guidance(date(2026, 1, 10))
    for sid, d in closes.items():
        assert (before[sid].status, before[sid].closes_at, before[sid].opens_at) == ("open", d, None), sid
    after = with_guidance(date(2026, 11, 25))
    for sid, d in closes.items():
        assert (after[sid].status, after[sid].closes_at) == ("unknown", d), sid   # past: the date is kept, the status not guessed
    assert after["cdbg"].closes_at_text == ("2026 CDBG CIP Application Guidelines (PDF): CIP applications must be submitted to "
                                            "ODOC by 5:00 PM, July 10, 2026.")
    assert after["cdbg"].source_url == m.BASE + m.PAGES["cdbg"]   # the hub, not the PDF
    edif = after["cdbg#edif"]
    assert (edif.status, edif.closes_at, edif.closes_at_text) == ("unknown", None, None)


def test_a_round_the_page_states_wins_over_the_pdf():
    (sid, payload), *_ = [x for x in m.SITE.records_for("cdbg", m.PAGES["cdbg"], [page("cdbg")], 0)
                          if x[0] == "cdbg#community-revitalization"]
    payload["page"]["blocks"].append(("p", "Applications are due December 15, 2026."))
    payload["guidance"] = {"url": payload["guidance_url"],
                           "sentences": ["Applications will be accepted through March 27, 2026, 5:00 p.m."]}
    p = m.normalize(RawRecord(source_connector="ok_commerce", source_id=sid, payload=payload), date(2026, 11, 25))
    assert (p.status, p.closes_at, p.closes_at_text) == ("open", date(2026, 12, 15), "Applications are due December 15, 2026.")


def test_fetch_reads_each_pdf_and_keeps_the_stored_sentences_when_one_fails(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    monkeypatch.setattr(hl, "get", lambda c, url: (FIX / f"{next(s for s, p in m.PAGES.items() if url == m.BASE + p)}.html")
                        .read_text(encoding="utf-8"))
    excerpts = {PDFS["cdbg#community-revitalization"]: "community-revitalization.pdf", PDFS["cdbg#edif"]: "edif.pdf"}

    def pdfs(client, url):
        name = url.rsplit("/", 1)[1]
        if name not in excerpts:
            raise httpx.HTTPStatusError("404", request=httpx.Request("GET", url), response=httpx.Response(404))
        return (GUIDE / excerpts[name]).read_bytes()

    monkeypatch.setattr(m, "get_pdf", pdfs)
    records = {r.source_id: r.payload for r in m.fetch()}
    assert records["cdbg#community-revitalization"]["guidance"]["sentences"][0].endswith("March 27, 2026, 5:00 p.m.")
    assert records["cdbg#edif"]["guidance"]["sentences"] == []
    assert "guidance" not in records["cdbg#reap"]   # its PDF failed and nothing was stored
    assert "guidance" not in records["odmrmf"]
    # a later run whose PDF fails keeps the stored sentences of the same file, never another file's
    prior = {**records, "cdbg#reap": {**records["cdbg#reap"], "guidance": {"url": records["cdbg#reap"]["guidance_url"],
                                                                           "sentences": ["kept"]}},
             "cdbg": {**records["cdbg"], "guidance": {"url": "https://www.okcommerce.gov/wp-content/uploads/2025-old.pdf",
                                                      "sentences": ["old"]}}}
    monkeypatch.setattr(m, "get_pdf", no_pdf)
    again = {r.source_id: r.payload for r in m.fetch(prior=prior)}
    assert again["cdbg#reap"]["guidance"]["sentences"] == ["kept"]
    assert "guidance" not in again["cdbg"]
    assert again["cdbg#community-revitalization"]["guidance"] == records["cdbg#community-revitalization"]["guidance"]


def test_get_pdf_tries_a_transport_error_once_more_never_a_status(monkeypatch):
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    calls: list[str] = []

    class Client:
        def __init__(self, fail):
            self.fail = list(fail)

        def get(self, url):
            calls.append(url)
            if self.fail:
                raise self.fail.pop(0)
            return httpx.Response(200, content=b"%PDF", request=httpx.Request("GET", url))

    assert m.get_pdf(Client([httpx.ReadError("cut")]), "u") == b"%PDF" and len(calls) == 2
    calls.clear()
    try:
        m.get_pdf(Client([httpx.ReadError("cut"), httpx.ReadError("cut")]), "u")
        raise AssertionError("a second transport error is not retried")
    except httpx.ReadError:
        assert len(calls) == 2
    calls.clear()

    class Refused(Client):
        def get(self, url):
            calls.append(url)
            return httpx.Response(403, request=httpx.Request("GET", url))

    try:
        m.get_pdf(Refused([]), "https://www.okcommerce.gov/x.pdf")
        raise AssertionError("a status is raised")
    except httpx.HTTPStatusError:
        assert len(calls) == 1
