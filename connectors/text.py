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
    (r"local governments?", ("municipality", "county")),
    # Not "the local jurisdiction": that is a specific counterparty ("takes the letter to the local jurisdiction to
    # apply for the credit"), not the applicant.
    (r"(?<!the )local jurisdictions?", ("municipality", "county")),
    (r"municipalit\w*", ("municipality",)),
    (r"\bmunicipal\b", ("municipality",)),           # "municipal governments", "municipal corporations" (MEA, DNR)
    (r"\bcit(?:y|ies)\b", ("municipality",)),
    (r"\b(?:towns?|villages?|townships?|boroughs?)\b", ("municipality",)),
    (r"\bcount(?:y|ies)\b", ("county",)),
    (r"\bnon-?profits?\b", ("nonprofit",)),
    (r"\bnot-for-profits?\b", ("nonprofit",)),
    (r"501\s?\(c\)\s?\(3\)", ("nonprofit",)),
    (r"(?<!not-)\bfor-profits?\b", ("business",)),
    (r"\bbusiness(?:es)?\b", ("business",)),
    (r"\bretailers?\b", ("business",)),
    (r"\bdevelopers?\b", ("business",)),
    (r"\bhomeowners?\b", ("household",)),
    (r"\bhouseholds?\b", ("household",)),
    (r"\bresidents?\b", ("household",)),
    (r"\brenters?\b", ("household",)),
    # The noun only: plural always, singular when a function word or punctuation follows ("any individual who",
    # "an individual may apply"). The adjective ("individual school facilities") never tags.
    (r"\bindividuals\b|\bindividual\b(?=\s*(?:$|[,.;:)]|(?:and|or|who|that|which|may|can|must|is|are|applying|seeking)\b))",
     ("individual",)),
    (r"housing authorit\w*", ("housing_authority",)),
    (r"\bschools?\b", ("school",)),
    (r"local education agenc\w*", ("school",)),
    (r"\btrib(?:al|es?)\b", ("tribe",)),
    (r"\bstate (?:government )?agenc\w*", ("state",)),
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


def applicant_types_for(applicant_text: str | list[str] | None) -> list[ApplicantTag]:
    """Keyword tags over applicant lines. The first match of each phrase that is not in a location
    context wins; the matched phrase is the tag's source_code."""
    lines = [applicant_text] if isinstance(applicant_text, str) else list(applicant_text or [])
    tags: list[ApplicantTag] = []
    for pattern, values in APPLICANT_KEYWORDS:
        phrase = next(
            (m.group(0).lower() for line in lines for m in re.finditer(pattern, line, re.I)
             if not LOCATION_CONTEXT_RE.search(line[max(0, m.start() - 60):m.start()]) and not _named_city(line, m)),
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
}


def portal_applicant(label: str) -> str | None:
    return PORTAL_APPLICANTS.get(portal_label(label))


def portal_categories(label: str) -> tuple[str, ...]:
    return PORTAL_CATEGORIES.get(portal_label(label), ("other",))
