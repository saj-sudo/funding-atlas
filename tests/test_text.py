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
    ("Public agencies (any city, county, special district, joint powers authority)", {"municipality", "county", "special_district"}),
    ("Cities, villages, townships and counties", {"municipality", "county"}),
    ("Boroughs and townships may apply", {"municipality"}),
    ("Awards will be made to local jurisdictions in four categories", {"municipality", "county"}),
    ("Eligibility is limited to local governments", {"municipality", "county"}),
    ("Applicants must be a California city or county prosecuting office", {"municipality", "county"}),
    ("Local units of government and state agencies", {"municipality", "county", "state"}),
    ("A locality must certify its police department", {"municipality", "county"}),
    ("State Aid to Localities with Police Departments", {"municipality", "county"}),
    ("Eligible applicants are local units of general government", {"municipality", "county"}),
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


@pytest.mark.parametrize("text, expected", [
    ("Businesses that employ residents of Iowa", {"business"}),
    ("Projects that serve residents of a Priority Funding Area", set()),
    ("Maryland residents may apply", {"household"}),
    ("Residents and homeowners", {"household"}),
    ("Residents of Iowa may apply", set()),       # the accepted cost: the phrase reads the same both ways
])
def test_residents_of_a_place_are_served_not_applying(text, expected):
    assert values(text) == expected


def test_a_lower_case_city_after_a_proper_noun_is_still_a_type():
    assert values("Operated by a California city or county") == {"municipality", "county"}


def test_not_for_profit_is_an_applicant_not_a_negation():
    from connectors.maryland_drupal import NEGATION_RE
    assert not NEGATION_RE.search("Counties, municipalities, not-for-profit organizations and for-profit businesses.")
    assert not NEGATION_RE.search("Not-for-profit organization dedicated to youth.")
    assert NEGATION_RE.search("Nonprofits are not eligible.") and NEGATION_RE.search("cannot apply")


def test_condition_and_negation_behaviour_is_unchanged():
    assert "individual" not in values("Individual school facilities")


def test_an_artist_named_as_the_applicant_is_an_individual():
    assert "individual" in values("Any artist who is 18 years of age or older, a legal resident of West Virginia")
    assert "individual" in values("● County school systems ● Individual artists ● Non-profit arts organizations")
    assert "individual" not in values("Fiscally sponsored organizations representing disabled artists")
    assert "individual" not in values("Organizations that further the interests of artists, creators, and tradition bearers")
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


def test_special_districts_and_kentucky_spges():
    def v(text):
        return {t.value for t in applicant_types_for([text])}
    assert v("Applicants must be a California-incorporated city, county, special district, or tribe") >= {"special_district"}
    assert v("special purpose districts (e.g. resource conservation districts)") == {"special_district"}
    assert v("a system of grants to Special Purpose Governmental Entities, as defined by KRS 65A.010(9)") == {"special_district"}
    assert v("distribution to local governments, public agencies, SPGEs, and other authorized recipients") >= {"special_district"}
    assert v("projects located in a special district") == set()            # a place, not an applicant
    assert v("in partnership with county governments") == set()            # partners, not grantees (RDAAP)


def test_political_subdivisions_are_local_governments():
    def v(text):
        return {t.value for t in applicant_types_for([text])}
    assert v("the FIND program allows for political subdivisions to submit one application") == {"municipality", "county"}
    assert v("provides loans to political subdivisions for eligible essential infrastructure projects") == {"municipality", "county"}
    assert v("Political subdivisions") == {"municipality", "county"}


# ---------- 10.6: the recorded gaps, every state so far ----------

def test_state_in_a_list_of_governments():
    assert "state" in values("The Public Assistance Program provides supplemental financial assistance to State, local "
                             "governments and certain private non-profit organizations")         # MDEM
    assert values("State governments in the Chesapeake Bay watershed can apply.") == {"state"}     # West Virginia
    assert "state" in values("open to state, county, or municipal forensic crime laboratories")    # PA PCCD
    assert "state" not in values("State funds are matched by local governments")
    assert "state" not in values("the State will review applications from cities")


def test_negation_exemptions():
    from connectors.maryland_drupal import NEGATION_RE
    assert not NEGATION_RE.search("Nonprofit entities not within designated urban areas")           # a place limit (MDEM NSGP)
    assert not NEGATION_RE.search("Eligible costs include, but are not limited to, equipment")    # Texas
    assert not NEGATION_RE.search("private not-for profit (PNP) entities may submit")             # ND HMGP
    assert NEGATION_RE.search("Applicants not located in Maryland are ineligible")


def test_conditions_and_statistics_are_not_applicants():
    assert values("Be an Oregon resident;") == set()                                              # Aggie Bond borrower condition
    assert values("150 percent of the state or county average wage, whichever is less") == set()  # Oregon BEP
    assert values("larger than 30% of the county's median farm size") == set()
    assert "county" in values("Lehigh County's MDIT as eligible applicants for 2026")              # a county team still applies
    assert values("Maryland residents may apply") == {"household"}


def test_communities_only_where_they_apply():
    assert values("All 78 Massachusetts coastal communities are eligible to apply.") == {"municipality"}   # Seaport
    assert values("Assistance primarily to small and disadvantaged communities for sewer infrastructure") == set()
    assert "municipality" not in values("tribes or indigenous communities that are not federally-recognized may apply")


def test_local_government_words():
    assert values("Not-for-profit community organizations are eligible to apply as are local political entities.") == {
        "nonprofit", "municipality", "county"}                                                    # ND Vibrancy
    assert values("All eligible jurisdictions and private not-for profit (PNP) entities may submit qualifying projects") == {
        "municipality", "county", "nonprofit"}                                                    # ND HMGP
    assert values("Local law enforcement agencies in Virginia are eligible to receive this funding.") == {"municipality", "county"}
    assert values("enter into a memorandum of understanding with a local law enforcement agency") == set()   # a partner (Texas)
    assert values("grants to subdivisions for flood mitigation") == {"municipality", "county"}      # MDE CFMGP


def test_single_purpose_districts_and_authorities():
    assert values("Park boards and park districts") == {"special_district"}
    assert values("Water management districts") == {"special_district"}
    assert values("Transit agencies") == {"special_district"}
    assert values("Transit entities operating in Maryland") == {"special_district"}
    assert "special_district" in values("local or regional economic or industrial development authorities may apply")
    assert "special_district" not in values("the Michigan State Housing Development Authority administers the program")
    assert values("Metropolitan Planning Organizations (MPOs)") == set()                           # no type (Saj's call)


def test_volunteer_emergency_companies_are_nonprofits():
    assert values("Fully and partially volunteer fire companies, first aid squads and rescue squads.") == {"nonprofit"}
