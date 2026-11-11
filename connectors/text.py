"""Text rules shared by every connector: who the applicant is, and what kind of money it is.

Moved out of connectors/maryland_drupal.py when the fourth connector outside Maryland (pa_grants, wv_grants,
ca_grants, il_csfa) was importing it from a Maryland module. The Maryland modules import these names back, so
nothing that imported them from there changes. Rules here are rules for every state: a phrase that is wrong for one
source is wrong for all and gets fixed here (see docs/ROADMAP.md, decisions log 2026-10-28).
"""

from __future__ import annotations

import re

from pipeline.models import ApplicantTag

# Phrase regex -> applicant types, scanned over the who-may-apply sections only, never the whole page.
# The matched phrase is stored as source_code so the inference is auditable in SQL. Shared by all three
# agencies; a phrase that is wrong for one of them is wrong for all and gets fixed here.
APPLICANT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"units? of (?:general )?local government", ("municipality", "county")),
    (r"local units? of (?:general )?government", ("municipality", "county")),   # Iowa's word order
    (r"local governments?", ("municipality", "county")),
    # 12.6d: Kentucky CMAQ, "Local and state government agencies are eligible to apply" (the state half tags itself).
    # Agencies only: North Dakota DES's "beyond local and state government recovery capability" names no applicant.
    (r"\blocal and state government agenc\w*", ("municipality", "county")),
    # Missouri State Parks (12.6f): RTP grants "are available to local and state governments, school districts ...": the plural
    # names both kinds of entity, unlike the singular "local and state government recovery capability" above.
    (r"\blocal and state governments\b", ("municipality", "county")),
    # "political subdivisions" is the statutory word for a state's local governments (North Dakota's FIND and its
    # revolving funds: "loans to political subdivisions"); the same two tags as "local governments".
    (r"\bpolitical subdivisions?\b", ("municipality", "county")),
    # Not "the local jurisdiction": that is a specific counterparty ("takes the letter to the local jurisdiction to
    # apply for the credit"), not the applicant.
    (r"(?<!the )local jurisdictions?", ("municipality", "county")),
    (r"\blocalit(?:y|ies)\b", ("municipality", "county")),   # Virginia's word for a city, county or town
    (r"municipalit\w*", ("municipality",)),
    (r"\bmunicipal\b", ("municipality",)),           # "municipal governments", "municipal corporations" (MEA, DNR)
    (r"\bcit(?:y|ies)\b", ("municipality",)),
    (r"\b(?:towns?|villages?|townships?|boroughs?)\b", ("municipality",)),
    # A county as an adjective is a statistic or a place, not the applicant: "150 percent of the state or county average
    # wage" (Oregon BEP), "30% of the county's median farm size" (Oregon Aggie Bond). 10.6.
    (r"\bcount(?:y|ies)\b(?!(?:['’]s)?\s+(?:average|median)\b)", ("county",)),
    (r"\bnon-?profits?\b", ("nonprofit",)),
    (r"\bnot-for[- ]profits?\b", ("nonprofit",)),   # "not-for profit" with a space too (ND HMGP, 10.6)
    (r"501\s?\(c\)\s?\(3\)", ("nonprofit",)),
    (r"(?<!not-)\bfor-profits?\b", ("business",)),
    (r"\bbusiness(?:es)?\b", ("business",)),
    (r"\bretailers?\b", ("business",)),
    (r"\bdevelopers?\b", ("business",)),
    # "homeowner associations" (MDOT's Urban Tree eligibility list) is an organization, not a household.
    (r"\bhomeowners?\b(?!['’]?\s+associations?\b)", ("household",)),
    (r"\bhouseholds?\b", ("household",)),
    # "residents of Iowa", "residents of a Priority Funding Area" is a population served, not the applicant; a bare
    # "residents" or "Maryland residents" still is.
    (r"\bresidents?\b(?!\s+of\b)", ("household",)),
    (r"\brenters?\b", ("household",)),
    # The noun only: plural always, singular when a function word or punctuation follows ("any individual who",
    # "an individual may apply"). The adjective ("individual school facilities") never tags.
    (r"\bindividuals\b|\bindividual\b(?=\s*(?:$|[,.;:)]|(?:and|or|who|that|which|may|can|must|is|are|applying|seeking)\b))",
     ("individual",)),
    # An artist named as the applicant ("Any artist who is 18 years of age or older", "Individual artists" in a
    # list of who may apply) is an individual. A bare "artists" is not: "representing disabled artists", "grant
    # payments to artists" and "the interests of artists" name the people served.
    (r"\b(?:any|individual) artists?\b", ("individual",)),
    (r"housing authorit\w*", ("housing_authority",)),
    (r"\bschools?\b", ("school",)),
    (r"local education agenc\w*", ("school",)),
    (r"\btrib(?:al|es?)\b", ("tribe",)),
    (r"\bstate (?:government )?agenc\w*", ("state",)),
    # 10.6: "state governments" (West Virginia), and "State" at the head of a list of governments ("assistance to State,
    # local governments and ..." MDEM; "state, local, and Indian Tribal governments" Grants.gov). "State funds" and
    # "the State will" stay untagged: a comma and a government word must follow.
    (r"\bstate governments?\b|\bstate(?=,\s*(?:and\s+|or\s+)?(?:local|tribal|territorial|county|municipal)\b)", ("state",)),
    # Special districts: the plain word, and Kentucky's statutory name for them (KRS 65A.010, "Special Purpose
    # Governmental Entities", written "SPGEs" on the DLG Portal).
    (r"\bspecial (?:purpose )?districts?\b", ("special_district",)),
    (r"\bspecial purpose governmental entit(?:y|ies)\b|\bSPGEs?\b", ("special_district",)),
    # 10.6 (Saj's call, 2026-11-11): districts and authorities that are governments of one purpose are special
    # districts: park and water management districts (North Dakota LWCF, RTP), transit agencies, authorities and
    # entities (NDDOT TA, MDOT), development authorities (Virginia DHCD; North Dakota's job development authorities).
    # A state housing development authority is a state agency, not a district. MPOs and planning district commissions
    # are regional planning bodies with no type and stay untagged.
    (r"\b(?:park|water management)\s+districts?\b", ("special_district",)),
    (r"\btransit\s+(?:agenc\w*|authorit\w*|entit\w*|districts?)\b", ("special_district",)),
    (r"(?<!housing )\bdevelopment authorit\w*", ("special_district",)),
    # 9-1-1 authorities (Illinois NG9-1-1 Expenses: "9-1-1 Authorities outside of municipalities with a population over
    # 500,000 shall be eligible to apply"), a county or municipal emergency telephone system board: Saj's call,
    # 2026-11-11, `special_district`.
    (r"\b9-?1-?1 authorit(?:y|ies)\b", ("special_district",)),
    # 10.6: words for local governments the tagger did not read. "local political entities" (North Dakota Vibrancy),
    # "eligible jurisdictions" (North Dakota HMGP) and "local law enforcement agencies" (Virginia DCJS), a city's or
    # county's department.
    (r"\blocal political entit(?:y|ies)\b", ("municipality", "county")),
    (r"\beligible jurisdictions?\b", ("municipality", "county")),
    (r"\blocal law enforcement agenc\w*", ("municipality", "county")),
    # 10.6 (Saj's call): "communities" is a municipality only where the sentence says the communities apply or are
    # eligible ("All 78 Massachusetts coastal communities are eligible to apply", Seaport); a sentence about what the
    # money does for communities stays untagged.
    # Not "indigenous communities" or "Native American communities" (California's Explore the Coast: tribes "that are
    # not federally recognized may apply" through a nonprofit).
    (r"(?<!indigenous )(?<!american )\bcommunities\b(?=[^.;]*\b(?:(?:is|are) eligible|may apply|can apply|eligible to apply|may submit an application)\b)|\beligible communities\b",
     ("municipality",)),
    # 10.6 (Saj's call): volunteer fire companies, first aid squads and rescue squads (New Jersey Fire Safety, VESOL) are
    # nonprofit corporations; a municipal fire department tags municipality through its own words.
    (r"\bfire compan(?:y|ies)\b|\bfirst aid squads?\b|\brescue squads?\b", ("nonprofit",)),
    (r"\bcolleges?\b|\buniversit\w*|institutions? of higher education", ("higher_ed",)),
)

# Name keyword -> funding_type, first match wins.
FUNDING_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("tax credit", "tax_credit"), ("loan", "loan"), ("voucher", "voucher"), ("grant", "grant"),
)

# A place word right after a spatial preposition is a place, not an applicant: "in 4+ cities outside
# Maryland", "within a Tier 1 County", "located in a designated rural county".
LOCATION_CONTEXT_RE = re.compile(
    r"\b(?:in|within|outside|inside|into|across|throughout|near|serving|serve)\s+(?:[\w$%+,'’/()-]+\s+){0,3}$", re.I
)


def _named_city(line: str, m: re.Match[str]) -> bool:
    """`Baltimore City` and `City of Philadelphia` name one city; they do not say that cities may apply. A lower-case
    `city` after a capitalized word ("California city or county") is a type and stays."""
    if m.group(0).lower() != "city":
        return False
    if m.group(0)[0].isupper() and re.search(r"[A-Z][a-z]+\s$", line[:m.start()]):
        return True
    return bool(re.match(r"\s+of\s+[A-Z]", line[m.end():]))


# "Be an Oregon resident" (Aggie Bond's borrower conditions) is a condition on the applicant, not a household
# applying; "cooperative participation with ... local law enforcement agencies" (California ESCARS) and "a memorandum
# of understanding with a local law enforcement agency" (Texas) name a partner, not the applicant. 10.6.
RESIDENCY_CONDITION_RE = re.compile(r"\bbe (?:a|an)\s+(?:[\w.-]+\s+){0,2}$", re.I)
PARTNER_RE = re.compile(r"\bwith\b[^.;]{0,70}$", re.I)


def _condition(line: str, m: re.Match[str]) -> bool:
    phrase, before = m.group(0).lower(), line[max(0, m.start() - 80):m.start()]
    if phrase.startswith("resident"):
        return bool(RESIDENCY_CONDITION_RE.search(before[-40:]))
    if phrase.startswith("local law enforcement"):
        return bool(PARTNER_RE.search(before))
    return False


def applicant_types_for(applicant_text: str | list[str] | None) -> list[ApplicantTag]:
    """Keyword tags over applicant lines. The first match of each phrase that is not in a location
    context wins; the matched phrase is the tag's source_code."""
    lines = [applicant_text] if isinstance(applicant_text, str) else list(applicant_text or [])
    tags: list[ApplicantTag] = []
    for pattern, values in APPLICANT_KEYWORDS:
        phrase = next(
            (m.group(0).lower() for line in lines for m in re.finditer(pattern, line, re.I)
             if not LOCATION_CONTEXT_RE.search(line[max(0, m.start() - 60):m.start()]) and not _named_city(line, m)
             and not _condition(line, m)),
            None,
        )
        if phrase:
            tags += [ApplicantTag(value=v, source_code=phrase) for v in values]
    return tags


def funding_type_for(name: str) -> str | None:
    n = name.lower()
    for keyword, ft in FUNDING_TYPE_KEYWORDS:
        if keyword in n:
            return ft
    return None


# ---------- portal vocabularies ----------
#
# The state portals that label their own rows (pa.gov, the California Grants Portal, Illinois CSFA) each use
# their own words for the same few things. One table per kind, so a label means the same thing in every state.
# Labels are compared lower-cased, with "&" read as "and" and commas dropped, so "Employment, Labor, & Training"
# (pa.gov) and "Employment, Labor & Training" (California) are one entry. The portal's own word is always kept
# as the tag's source_code, so any mapping here can be redone in SQL.

def portal_label(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("&", " and ").replace(",", " ")).strip()


# Applicant label -> applicant_type. Labels that cover many kinds of body tag NOTHING on purpose: `Public Agency`
# and `Other Legal Entity` (California, pa.gov), `Government Organizations` (Illinois) take in state departments,
# special districts, tribes, cities and counties alike, and `Education Organizations` takes in K-12 and colleges.
# The free-text eligibility line names the real ones and applicant_types_for reads it.
PORTAL_APPLICANTS: dict[str, str] = {
    "municipality": "municipality", "school": "school",
    "nonprofit": "nonprofit", "nonprofit organizations": "nonprofit",
    "business": "business", "for-profit organizations": "business", "small businesses": "business",
    "individual": "individual", "individuals": "individual",
    "tribal government": "tribe", "native american tribal organization or government": "tribe",
    "public housing organizations": "housing_authority",
    # New York SFS (the portal's five eligibility labels; `Governmental Entity` is the broad one and tags nothing)
    "not-for-profit": "nonprofit", "for profit": "business", "tribal organization": "tribe",
    # Illinois AmpliFund pages, which also use the Grants.gov applicant vocabulary beside the CSFA labels
    "state governments": "state", "county governments": "county", "city or township governments": "municipality",
    "special district governments": "special_district",
    "native american tribal governments (federally recognized)": "tribe",
    "nonprofits with 501(c)(3) status (excludes institutions of higher education)": "nonprofit",
    "nonprofits without 501(c)(3) status (excludes institutions of higher education)": "nonprofit",
    "public and state controlled institutions of higher education": "higher_ed",
    "private institutions of higher education": "higher_ed",
}

# Topic label -> categories. A label that names two topics carries both (as DHCD's energy-home-repair section
# does). Economic development reads as infrastructure everywhere, as the Grants.gov community development code
# does. Anything not listed is `other`.
PORTAL_CATEGORIES: dict[str, tuple[str, ...]] = {
    "transportation": ("transportation",), "energy": ("energy",), "environment and water": ("water",),
    "housing": ("housing",), "parks and recreation": ("parks",),
    "health and human services": ("health",), "human services": ("health",),
    "employment labor and training": ("workforce",),
    "law justice and legal services": ("public_safety",), "public safety": ("public_safety",),
    "disaster prevention and relief": ("public_safety",),
    "community and economic development": ("infrastructure",), "economic development": ("infrastructure",),
    "housing community and economic development": ("housing", "infrastructure"),
    "community development": ("infrastructure",),
    "disaster assistance": ("public_safety",), "disaster preparedness": ("public_safety",),
    "health": ("health",), "child health": ("health",), "prevention/treatment": ("health",),
    # New York SFS service areas; the other six (agricultural, education, environmental, family, government supports)
    # name none of our categories and fall to `other`
    # Delaware DNREC's page tags and DEMA's accordion headings
    "clean water": ("water",), "drinking water": ("water",), "wastewater": ("water",), "stormwater": ("water",),
    "septic systems": ("water",), "non-point source": ("water",), "water quality financing": ("water",),
    "infrastructure": ("infrastructure",), "green infrastructure loans": ("infrastructure",),
    "preparedness grants": ("public_safety",), "recovery assistance": ("public_safety",),
    "health services": ("health",), "housing and shelter services": ("housing",),
    "workforce development": ("workforce",), "public safety supports": ("public_safety",),
    "justice services": ("public_safety",), "public transportation services": ("transportation",),
    # Business Oregon's topic tabs; its other seven (arts and culture, business finance, business incentives, COVID-19
    # response, global trade, innovation, other business services) name none of our categories and fall to `other`
    "infrastructure and land programs": ("infrastructure",),
    # nc.gov's grant table categories (the other six, agriculture, art and culture, community service, education,
    # environment, technology broadband and digital equity, name none of ours) and the Washington Fund Directory's
    # "Type of Program" labels (the rest, air quality, salmon recovery, conservation, broadband, education, agriculture,
    # fall to `other`)
    "disaster recovery": ("public_safety",),
    "water quality": ("water",), "pollution cleanup": ("water",), "wetlands watershed and shoreline restoration": ("water",),
    "transit and other alternative transportation": ("transportation",), "bridges roads and safety improvements": ("transportation",),
    "rail and freight": ("transportation",), "recreation": ("parks",), "outdoor recreation": ("parks",),
    "recreation and conservation": ("parks",), "recreation and culture": ("parks",),
    "emergency management": ("public_safety",), "emergency mitigation": ("public_safety",), "social services": ("health",),
}


def portal_applicant(label: str) -> str | None:
    return PORTAL_APPLICANTS.get(portal_label(label))


def portal_categories(label: str) -> tuple[str, ...]:
    return PORTAL_CATEGORIES.get(portal_label(label), ("other",))
