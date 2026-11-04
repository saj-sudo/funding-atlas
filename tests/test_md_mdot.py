"""Maryland MDOT connector tests, against the three saved pages (never the network) and small inline pages for the
rules: comments are not read, the round sentence order, the eligibility label, the hand quote."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from connectors import hand_list as hl
from connectors import md_mdot as md
from pipeline.models import RawRecord

FIX = Path(__file__).parent / "fixtures" / "md_mdot"
TODAY = date(2026, 11, 3)


def read(slug: str) -> str:
    return (FIX / f"{slug}.html").read_text(encoding="utf-8")


def normalize(slug: str, today: date = TODAY, html: str | None = None):
    page_id, section = md.PAGES[slug]
    page = md.parse_page(html if html is not None else read(slug))
    return md.normalize(RawRecord(source_connector=md.CONNECTOR, source_id=slug,
                                  payload={"page_id": page_id, "section": section, "page": page}), today)


def page(body: str, h1: str = "Some Program") -> str:
    return f'<html><body><main class="mdgov-main"><h1>{h1}</h1>{body}</main></body></html>'


def test_fixtures_carry_no_scripts_or_contacts():
    for path in FIX.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text and "<!--" not in text and "email-protection" not in text and "@mdot" not in text
        assert "Kurtz" not in text and "Stockdale" not in text


def test_commented_out_banners_are_not_read():
    html = page("<!-- <p>Applications are OPEN for Bikeways FY27 funding! Submit before May 31, 2027.</p> -->"
                "<p>FY 2027 awards have now been announced!</p>")
    p = normalize("bikeways", html=html)
    assert p.status == "closed" and p.closes_at_text == "FY 2027 awards have now been announced!"
    assert "OPEN" not in " ".join(t for _, t in md.parse_page(html)["blocks"])


def test_nested_paragraphs_contribute_their_own_text_once():
    html = page('<p>Outer banner. <div class="row"><div class="col"><p>Inner paragraph about the program.</p></div></div></p>')
    blocks = md.parse_page(html)["blocks"]
    assert blocks == [("p", "Outer banner."), ("p", "Inner paragraph about the program.")]


def test_bikeways_awards_announced_is_closed_with_who_can_apply_tags_and_match():
    p = normalize("bikeways")
    assert p.name == "Kim Lamphier Bikeways Network Program" and p.agency_code == "MD-MDOT" and p.jurisdiction == "MD"
    assert p.status == "closed" and p.closes_at is None and p.rolling is None
    assert p.closes_at_text == "FY 2027 awards have now been announced!"
    lines = p.eligibility_text.split("\n")
    assert "Who Can Apply" in lines and "Maryland State Agencies" in lines and "Non-profit organizations" in lines
    assert "Eligible Projects" not in lines and not any("universities" in ln for ln in lines)   # project criteria are not applicants
    assert {t.value for t in p.applicant_types} == {"municipality", "county", "state", "nonprofit"}
    assert p.match_required is True and p.funding_type == "grant" and p.funding_source == "direct"
    assert p.category_pairs() == [("transportation", "Active Transportation")]
    assert p.summary.startswith("Established in 2012")                                           # not the banner


def test_urban_tree_year_round_rolling_with_the_dated_quote():
    p = normalize("urban-tree")
    assert p.status == "open" and p.rolling is True and p.closes_at is None
    assert p.closes_at_text.startswith("Applications are accepted year-round")
    assert "UTP How to Apply FY27 (PDF, last update 4.15.2026), read 2026-11-03: Eligible Applicants:" in p.eligibility_text
    tags = {t.value for t in p.applicant_types}
    assert {"municipality", "county", "nonprofit", "school", "business", "higher_ed"} <= tags
    assert "household" not in tags                                                                # "homeowner associations"
    assert p.funding_type == "grant"


def test_tod_open_through_november_20_grant_not_loan():
    p = normalize("tod")
    assert p.status == "open" and p.closes_at == date(2026, 11, 20) and p.rolling is None
    assert p.closes_at_text == "MDOT's TOD Capital Grant Fund is now accepting applications for funding through November 20, 2026."
    assert p.funding_type == "grant"                                                              # override: the name says Loan Fund
    assert {t.value for t in p.applicant_types} == {"municipality", "county"}                     # "local jurisdictions"
    assert p.match_required is None                                                               # the 10% match card is a comment
    assert p.category_pairs() == [("transportation", "Transit Oriented Development")]
    assert p.source_url == "https://www.mdot.maryland.gov/tso/pages/Index.aspx?PageId=217"
    assert normalize("tod", today=date(2026, 12, 1)).status == "unknown"                          # past date kept, DelDOT rule


@pytest.mark.parametrize("body, expected", [
    ("<p>MDOT is now accepting applications through November 20, 2026.</p>", ("open", date(2026, 11, 20), None)),
    ("<p>MDOT is currently accepting grant applications.</p><p>The Fund is accepting applications through November 20, 2026.</p>",
     ("open", date(2026, 11, 20), None)),                                                         # the dated sentence wins
    ("<p>Applications are accepted year-round, with determinations twice a year.</p>", ("open", None, True)),
    ("<p>FY 2027 awards have now been announced!</p>", ("closed", None, None)),
    ("<p>MDOT's TOD Fund is currently closed for applications.</p>", ("closed", None, None)),
    ("<p>MDOT is not accepting applications at this time.</p>", ("unknown", None, None)),
    ("<p>A program description with no round wording.</p>", ("unknown", None, None)),
])
def test_round_sentence_order(body, expected):
    p = normalize("bikeways", html=page(body))
    assert (p.status, p.closes_at, p.rolling) == expected


def test_eligibility_label_is_who_can_apply_not_eligible_projects():
    html = page('<div class="card"><div class="card-header">Eligible Projects</div><div class="card-body"><ul><li>Access to universities</li></ul></div></div>'
                '<div class="card"><div class="card-header">Who Can Apply</div><div class="card-body"><ul><li>Maryland local governments</li></ul></div></div>')
    p = normalize("bikeways", html=html)
    assert p.eligibility_text == "Who Can Apply\nMaryland local governments"
    assert {t.value for t in p.applicant_types} == {"municipality", "county"}


def test_contact_lines_are_dropped():
    html = page("<p>Eligible applicants may apply.</p><p>If you have any questions, please reach out to Pat Example at [email protected].</p>")
    assert all("reach out" not in t for _, t in md.parse_page(html)["blocks"])


class _Pages:
    def __init__(self, broken=()):
        self.broken, self.calls = set(broken), []

    def __call__(self, client, url):
        self.calls.append(url)
        if url in self.broken:
            raise httpx.ConnectError("down")
        for slug, (page_id, _) in md.PAGES.items():
            if url == md.URL.format(n=page_id):
                return read(slug)
        raise AssertionError(url)


def test_fetch_reads_three_pages_and_falls_back_to_prior(monkeypatch):
    monkeypatch.setattr(hl.time, "sleep", lambda s: None)
    monkeypatch.setattr(hl, "get", _Pages())
    records = md.fetch()
    assert [r.source_id for r in records] == ["bikeways", "urban-tree", "tod"]
    assert records[2].payload["page_id"] == 217 and records[2].payload["section"] == "Transit Oriented Development"
    prior = {r.source_id: r.payload for r in records}
    monkeypatch.setattr(hl, "get", _Pages(broken={md.URL.format(n=28)}))
    assert {r.source_id: r.payload for r in md.fetch(prior=prior)}["bikeways"] == prior["bikeways"]
    assert [r.source_id for r in md.fetch()] == ["urban-tree", "tod"]
    monkeypatch.setattr(hl, "get", _Pages())
    assert len(md.fetch(limit=1)) == 1
    assert md.resolve_missing("tod") == {"status": "unknown"}
