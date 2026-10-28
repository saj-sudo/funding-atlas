"""The text rules every connector shares: the applicant tagger, the funding-type keyword and the portal vocabularies."""

from __future__ import annotations

import pytest

from connectors.text import (
    applicant_types_for,
    funding_type_for,
    portal_applicant,
    portal_categories,
    portal_label,
)


def values(text: str | list[str]) -> set[str]:
    return {t.value for t in applicant_types_for(text)}


# ---------- applicant tagger ----------

@pytest.mark.parametrize("text, expected", [
    ("Public agencies (any city, county, special district, joint powers authority)", {"municipality", "county"}),
    ("Cities, villages, townships and counties", {"municipality", "county"}),
    ("Boroughs and townships may apply", {"municipality"}),
    ("Awards will be made to local jurisdictions in four categories", {"municipality", "county"}),
    ("Eligibility is limited to local governments", {"municipality", "county"}),
    ("Applicants must be a California city or county prosecuting office", {"municipality", "county"}),
])
def test_places_that_apply(text, expected):
    assert values(text) == expected


def test_source_code_is_the_matched_phrase():
    pairs = {(t.value, t.source_code) for t in applicant_types_for("Any city or township")}
    assert pairs == {("municipality", "city"), ("municipality", "township")}


@pytest.mark.parametrize("text", [
    "The owner takes the letter to the local jurisdiction to apply for the credit",
    "then 4+ weeks of performances in 4+ cities outside Maryland",
    "must be located in a designated rural county",
    "located in a village outside the district",
])
def test_places_that_do_not_apply(text):
    assert values(text) == set()


@pytest.mark.parametrize("text", [
    "County governments, including Baltimore City, are eligible to apply",
    "Nonprofit organizations, the City of Philadelphia, and the School District",
    "Entities eligible: City of Santa Clara and Contra Costa Transportation Authority",
])
def test_a_named_city_is_not_cities(text):
    assert "municipality" not in values(text)


def test_a_lower_case_city_after_a_proper_noun_is_still_a_type():
    assert values("Operated by a California city or county") == {"municipality", "county"}


def test_condition_and_negation_behaviour_is_unchanged():
    assert "individual" not in values("Individual school facilities")
    assert values(["Nonprofits and for-profit businesses"]) == {"nonprofit", "business"}


# ---------- funding type ----------

@pytest.mark.parametrize("name, expected", [
    ("Clean Water Loan Fund", "loan"), ("Historic Tax Credit", "tax_credit"), ("Community Grant", "grant"),
    ("Main Street Program", None),
])
def test_funding_type_for(name, expected):
    assert funding_type_for(name) == expected


# ---------- portal vocabularies ----------

def test_portal_label_ignores_case_commas_and_ampersands():
    assert portal_label("Employment, Labor, & Training") == portal_label("employment, labor & training")
    assert portal_label("Law, Justice, & Legal Services") == portal_label("Law, Justice, and Legal Services")


@pytest.mark.parametrize("label, expected", [
    ("Nonprofit", "nonprofit"), ("Nonprofit organizations", "nonprofit"), ("For-Profit Organizations", "business"),
    ("Small Businesses", "business"), ("Individuals", "individual"), ("Tribal Government", "tribe"),
    ("Native American Tribal Organization or Government", "tribe"), ("Public Housing Organizations", "housing_authority"),
    ("Municipality", "municipality"), ("School", "school"),
])
def test_portal_applicant_maps(label, expected):
    assert portal_applicant(label) == expected


@pytest.mark.parametrize("label", [
    "Public Agency", "Other Legal Entity", "Government Organizations", "Education Organizations", "Other", "",
])
def test_broad_portal_applicant_labels_tag_nothing(label):
    assert portal_applicant(label) is None


@pytest.mark.parametrize("label, expected", [
    ("Environment & Water", ("water",)),
    ("Employment, Labor, & Training", ("workforce",)),
    ("Employment, Labor & Training", ("workforce",)),
    ("Law, Justice, & Legal Services", ("public_safety",)),
    ("Disaster Prevention & Relief", ("public_safety",)),
    ("Community & Economic Development", ("infrastructure",)),
    ("Economic Development", ("infrastructure",)),
    ("Housing, Community and Economic Development", ("housing", "infrastructure")),
    ("Human Services", ("health",)),
    ("Agriculture", ("other",)),
    ("Quality of Natural, Cultural, and Environmental Resources", ("other",)),
])
def test_portal_categories(label, expected):
    assert portal_categories(label) == expected


def test_economic_development_means_the_same_thing_in_every_state():
    """pa.gov, Illinois and California name it differently; all three read as infrastructure."""
    for label in ("Community & Economic Development", "Economic Development", "Housing, Community and Economic Development"):
        assert "infrastructure" in portal_categories(label)


@pytest.mark.parametrize("label, expected", [
    ("Community Development", ("infrastructure",)),
    ("Disaster Assistance", ("public_safety",)),
    ("Disaster Preparedness", ("public_safety",)),
    ("Child Health", ("health",)),
    ("Health", ("health",)),
    ("Prevention/Treatment", ("health",)),
    ("Historic Preservation", ("other",)),
])
def test_webgrants_storefront_categories(label, expected):
    assert portal_categories(label) == expected
