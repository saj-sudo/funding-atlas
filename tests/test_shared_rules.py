"""The rules lifted into the shared base from the 12.9 states (12.10): each one where it came from and where it stops."""

from __future__ import annotations

from datetime import date

from connectors import hand_list as hl
from connectors.maryland_drupal import sentences

TODAY = date(2026, 11, 24)


def test_rolling_wording_is_open_and_rolling_only_when_nothing_else_times_the_page():
    rolling = [("p", "Requests for Inclusion can be submitted any time during the year.")]
    out = hl.rolling_round(rolling, hl.round_for(rolling, TODAY))
    assert (out["status"], out["rolling"], out["closes_at"]) == ("open", True, None)
    assert hl.rolling_round([("p", "Applications are accepted on a continuous basis.")],
                            hl.round_for([], TODAY))["status"] == "open"
    # a cycle sentence already kept (a yearless round) is not overridden by another program's rolling sentence
    kept = {"status": "unknown", "opens_at": None, "closes_at": None, "closes_at_text": "considered on a quarterly basis",
            "rolling": None}
    assert hl.rolling_round(rolling, kept) == kept
    noi = [("p", "NOIs can be submitted at any time and are kept on file for two years.")]
    assert hl.rolling_round(noi, hl.round_for(noi, TODAY))["status"] == "unknown"
    dated = [("p", "Applications are due March 22, 2027."), ("p", "Emergency requests may be submitted at any time.")]
    assert hl.rolling_round(dated, hl.round_for(dated, TODAY))["rolling"] is None


def test_a_cdbg_name_is_a_pass_through_but_a_cdbg_mention_is_not():
    blocks = [("p", "Grants for rural communities.")]
    assert hl.funding_source_for(blocks, "Grants for rural communities.", "CDBG Planning Grants") == "pass_through"
    text = "Entitlement communities that receive CDBG funds directly are not eligible."
    assert hl.funding_source_for([("p", text)], text, "Stellar Pathways Program") == "direct"
    assert hl.FEDERAL_RE.search("The CDBG Program is a federally-funded grant for states")


def test_loans_name_an_applicant():
    assert hl.APPLICANT_SENTENCE_RE.search("CAP provides loans to municipalities and counties for public infrastructure.")
    assert hl.APPLICANT_SENTENCE_RE.search("Loans are made available to public water and sewer systems.")
    assert not hl.APPLICANT_SENTENCE_RE.search("A loan interest rate lower than the bond rate available to AAA rated issuers.")


def test_an_application_window_with_a_comma_but_not_one_in_parentheses():
    lgap = ["The LGAP application period is open from November 2, 2026, through February 26, 2027."]
    assert hl.application_range(lgap)[1:] == (date(2026, 11, 2), date(2027, 2, 26))
    bus = ["Applications must be submitted by May 14, 2027, for trips in the school year (July 1, 2026, to June 30, 2027)."]
    assert hl.application_range(bus) is None


def test_no_matching_funds_required_leaves_match_unknown():
    assert hl.MATCH_NOT_RE.search("Grants up to $500,000 - no matching funds required.")


def test_meridiem_ends_a_sentence_only_before_what_is_not_a_month_or_zone():
    assert sentences("Applications are due Dec. 13, by 11:59 p.m. ET via eGMS. Late ones are not read.") == [
        "Applications are due Dec. 13, by 11:59 p.m. ET via eGMS.", "Late ones are not read."]
    assert sentences("Application deadline: 5 p.m. Oct. 30, 2026") == ["Application deadline: 5 p.m. Oct. 30, 2026"]
    assert sentences("Due by June 30, 2027, at 5 p.m. If a project is selected, it is notified.") == [
        "Due by June 30, 2027, at 5 p.m.", "If a project is selected, it is notified."]
