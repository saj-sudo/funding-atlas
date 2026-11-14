# Nebraska's agency pages: survey, scope and field mapping

Milestone 12.6g, the sixth agency state in the 12.6 cost ranking (after Vermont, Connecticut, North Dakota, Kentucky and
Missouri). Written 2026-11-14 from a read-only survey of the candidate agencies' hosts and pages, before any parser.
Nebraska has no state index: its AmpliFund host is a login redirect (`docs/surveys/state_portals.md`), so this is an
agency state. Agencies are built one at a time, each its own commit; this doc grows with them.

## Survey (2026-11-14, the connectors' own User-Agent, one GET per page, 3 s apart)

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Economic Development (DED) | `opportunity.nebraska.gov` | WordPress 7.1, program text in `div.entry-content` | `User-agent: *`; disallows `/calendar/action*`, `/events/action*` and any URL with a query string (`/*?`); `Crawl-delay: 3` | **build first**: plain paths only, 3 s between GETs |
| Water, Energy and Environment (DWEE, the merged NDEE and DNR) | `dwee.nebraska.gov` (`dee.nebraska.gov` and `dnr.nebraska.gov` redirect to it; `dee.ne.gov` fails TLS name check and is not used) | Drupal 10 | stock Drupal file: blocks `/search/`, `/admin/`, `/node/add/`, user pages | **build**: the same Drupal 10 shape as Missouri's agencies, so probably a small reader |
| Transportation (NDOT) | `dot.nebraska.gov` | Umbraco | no `robots.txt` (404) | **build**: Transportation Alternatives, HSIP, Off-System Bridge, County Bridge Match and the other local programs each have a page |
| Emergency Management (NEMA) | `nema.nebraska.gov` | not a CMS generator I can name: `.php` pages, Bootstrap, no generator tag | no `robots.txt` (404) | **defer**: its grants page links FEMA's own pages (EMPG, HSGP) and the Hazard Mitigation page is a program overview with a Notice of Interest form, not a round; revisit when the 2024/2025 BRIC round text is read |
| Game and Parks | `outdoornebraska.gov` | not surveyed further | `*` allows everything, but **`ClaudeBot` is `Disallow: /`** (with a list of AI crawlers) | **Saj's call**, the ADECA precedent (decision 2026-10-18): not read until decided |
| NIFA (housing finance) | `www.nifa.org` | not surveyed further | **`ClaudeBot` is `Disallow: /`**; `*` blocks `/archive/*` | **Saj's call**, same rule; mostly developer tax credits |
| Natural Resources (DNR) | now `dwee.nebraska.gov` | | | covered by DWEE |

Four agencies, three or four platforms: there is no Nebraska base, each agency's reader is its own (the third-case rule
holds: nothing is extracted until a second agency on one platform forces it). `uv run` made a throwaway `.venv`; nothing
else was written to the repository during the survey.

## Candidate programs (what the index pages list on 2026-11-14)

**DED** (`/programs/`, five sections: Community, Housing, Business, Incentives, Economic Recovery):

- Community (seven): CDBG (one page, six funding opportunities under it: Economic Development, Public Works -
  Infrastructure, Planning, Tourism Development, Public Works - Facilities, Downtown Revitalization), CDBG-DR, Civic and Community Center Financing Fund (CCCFF), Community Development Assistance
  Act (a tax credit), Enterprise Zones (tax), Economic Development Certified Community and Leadership Certified Community
  (designations), LB840 (a local-option statute, not a program).
- Housing (eight): HOME, HOME-ARP, the Middle Income Workforce Housing Investment Fund, the National Housing Trust Fund, the
  Nebraska Affordable Housing Trust Fund, the Rural Community Recovery Program and the Rural Workforce Housing Fund.
- Business and Incentives: mostly firms, not towns; Site and Building Development Fund and the Municipal Inland Port Authority
  Act are the two that can name a municipality. To read before deciding.
- Economic Recovery (ARPA): about twenty pages, most of them closed one-time programs (Multi-Purpose Community Facilities, QCT
  Recovery, RDI and others); stored as `closed` or `unknown` per what each page says, only if the page still reads as a
  program with applicants.

**DWEE** (`/aid/...`): Clean Water State Revolving Loan Fund, Deconstruction Grants, Source Water Protection (the grant's yearly
project-description pages are past-award lists and are not read), Dollar & Energy Saving Loans (households; likely out), the
Brownfields pages (assessments are services, not grants; decide per page), Air Loans, Grants & Rebates. The Drinking Water SRF
page is not in the first-level links; find it from the water section before writing the module.

**NDOT** (`/projects/` and `/business-center/local-public-assistance/projects/...`): Transportation Alternatives, HSIP,
Bridge Replacement and Rehabilitation (the Off-System Bridge Program), County Bridge Match, County Soft Match, Federal Funds
Purchase Program, State Recreational Road, Economic Opportunity Program, Accelerated Capital Improvement Program, and
public-transit "Funding and Applications". Several of these are allocations to counties or MPOs without an application (the
Missouri MoDOT rule: formula money is left out).

## Sample of the raw data

DED's CDBG page (`/programs/community/cdbg/`), under the heading "CDBG Funding Opportunities & Application Deadlines", one
`h2` per opportunity, a one-line description, and either a deadline or a window:

```
h2  Economic Development
p   Loans to businesses or infrastructure construction projects undertaken for economic development purposes.
p   Application Period: July 1, 2026 to June 30, 2027
h2  Public Works - Infrastructure
p   Sewer and water systems, drainage improvements, streets, sidewalks, ...
p   Application Deadline: Sept. 15
h2  Planning
p   ... Application Deadline: Sept. 15
h2  Tourism Development        (Application Period: July 1, 2026 to June 30, 2027)
h2  Public Works - Facilities  (Application Deadline: Sept. 15)
h2  Downtown Revitalization    (Application Deadline: Sept. 15)
```

Applicants are one paragraph above that heading: "Every Nebraska county or incorporated municipality not designated as a CDBG
Entitlement Community is eligible to apply for funding through DED" (the entitlement cities are named in the next sentence
and must not be tagged: the shared negation guard has to be checked on it).

## Implemented, DED (2026-11-14)

`connectors/ne_ded.py` (its own WordPress reader in the module: no second Nebraska agency on WordPress, so no base) follows
this section. First live run on an empty database: **10 added, 0 errors**, 13 seconds (three seconds between GETs, the robots
file's `Crawl-delay: 3`); second run **0 changed**. The reader takes `div.entry-content`, the body's first `h1` (CCCFF's
photo captions are `h1`s too), drops the breadcrumb line, stops at "Program Resources", "Grant Management Resources" and
"Press Releases" (their dates would read as rounds) and treats a short paragraph ending in a colon as a label (NAHTF's "Who is
eligible to apply? Eligible applicants include:").

| Record | Status on 2026-11-14 | Applicants tagged | Source |
|---|---|---|---|
| CDBG Economic Development | open, 2026-07-01 to 2027-06-30 | municipality, county | pass_through |
| CDBG Tourism Development | open, 2026-07-01 to 2027-06-30 | municipality, county | pass_through |
| CDBG Public Works - Infrastructure, Planning, Public Works - Facilities, Downtown Revitalization | `unknown`: "Application Deadline: Sept. 15", no year | municipality, county | pass_through |
| Civic and Community Center Financing Fund | `forecasted`, opens 2027-01-01, pre-application due 2027-01-15 (the full application closes 2027-02-15, in the text) | municipality, tribe | direct |
| Nebraska Affordable Housing Trust Fund | `unknown`: the application dates sit in AmpliFund "Apply Now" buttons, not in the page's text | municipality, county, housing authority | direct |
| Rural Community Recovery Program | `unknown`: "Application Period:" is empty on the page | municipality, county | pass_through (ARPA) |
| Site and Building Development Fund | `unknown`: "Deadlines depend on funding availability" | municipality, county, nonprofit | direct |

The "Sept. 15" rows keep that sentence in `closes_at_text` and store no date: a month and day with no year is not a date,
and the page does not say which year. The window rule reads "July 1, 2026 to June 30, 2027" as open to its end.

### Shared changes (`connectors/hand_list.py`, `connectors/text.py`)

Each change was measured on its own: the database restored from `gh-pages` (7,734 stored records) re-normalized through
`scripts/measure_tagger.py` before and after, and the 116 fixture records of every other agency-page connector (Vermont,
Connecticut, North Dakota, Kentucky, Missouri) compared by `record_hash`. **Every change: 0 tag moves, 0 hash moves, 116 of
116 fixtures identical.**

- `DELAY_S` is a class attribute (read as `self.DELAY_S` in `fetch`), so an agency whose robots ask for a longer delay sets
  its own (DED: 3 s). Default unchanged.
- `NOT_DESIGNATED_RE`, cut before tagging: CDBG's "Every Nebraska county or incorporated municipality not designated as a
  CDBG Entitlement Community is eligible to apply" lost the whole sentence to the negation guard. The stored text keeps the
  carve-out; the four entitlement cities (Lincoln, Omaha, Bellevue, Grand Island) are named in the next sentence and are not
  tagged.
- `APPLICANT_SENTENCE_RE`: a sentence that names a kind of local government and ends on "are eligible" (SBDF's "Local
  governments and Nebraska nonprofits are eligible.").
- `text.py`: "local and governmental subdivisions" tags municipality and county (NAHTF's first applicant), beside "political
  subdivisions".
- `DUE_RE` reads "Closes:" and "Close Date:", `OPENS_RE` reads "Period Opens" and "Open Date", and `opening()` takes the date
  between the opening word and the deadline word when one sentence holds both ("Opens: 1/1/2027 ... Closes: 1/15/2027").
- `deadline()` tries a date after the deadline word before one before it. Without it CCCFF's closing date was its opening
  date (the opening comes first in the sentence).

### Scope calls (Saj to overrule; each is one line in `PAGES`)

- **In (five pages, ten records):** the pages that name local governments as applicants: CDBG, CCCFF, NAHTF, RCRP, SBDF.
- **Out, applicants are nonprofits, developers or CHDOs:** HOME, the Housing Trust Fund, the Rural Workforce Housing Fund and
  the Middle Income Workforce Housing Fund. The Housing Trust Fund also lists public housing authorities; with NIFA's
  `ClaudeBot` disallow (above) its CRANE category is NIFA's to describe.
- **Out, not a program that takes applications:** the Municipal Inland Port Authority Act (a statute that lets towns create
  authorities; its money is an SBDF subaccount, already read through SBDF), CDAA, Enterprise Zones, EDCC, LCC, LB840.
- **Out, one-time ARPA pages that accept "public and private entities" with no local government named:** Multi-Purpose
  Community Facilities (closed 2023-12-22), QCT Recovery, EDA Tourism, RDI (nonprofits and community colleges). RCRP is in
  because it names political subdivisions.
- **RCRP is `pass_through`:** its page says it is established "pursuant to the American Rescue Plan Act of 2021 (ARPA)".

### Gaps

- NAHTF's and RCRP's application windows are not in the page text (AmpliFund buttons and an empty paragraph), and AmpliFund has
  no public list (12.2): both stay `unknown` until DED prints dates.
- CDBG's "Application Deadline: Sept. 15" rows stay `unknown` year-round by this rule. If Saj prefers "the next September 15",
  that is one rule, and a guess.
- The CDBG page's "Announcements" and "Recent Updates" blocks follow every CDBG record as shared text; none carries a date the
  reader takes, checked on the 2026-11-14 page.

## Decisions on the way in

1. **"Sept. 15" has no year.** Four of CDBG's six opportunities state a deadline with no year. The status rule is "what the source
   says on the run date": a date with no year is not a date, so those rows are `unknown` with the sentence kept, not a guess
   at 2026 or 2027. A "July 1, 2026 to June 30, 2027" window is read as open (the window rule from Kentucky's CDBG pages).
   If Saj prefers the next occurrence of September 15, that is a one-line rule, but it is the kind of guess the repository
   avoids.
2. **CDBG's one page is six records** through `SPLITS` (the 2026-11-11 split rule), the same as Kentucky's EEC index.
3. **Designations, tax credits and statutes are not programs that take applications** (CDAA, Enterprise Zones, EDCC, LCC,
   LB840): left out, as Connecticut's formula entitlements were.
4. **Game and Parks and NIFA** wait for Saj (`ClaudeBot` disallow, see the table).
5. **Crawl delay**: DED's robots ask for 3 s; the DED module sets its delay to 3 s (the base default is 0.3 s) and reads no
   URL with a query string.
