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

## Implemented, DWEE (2026-11-14)

`connectors/ne_dwee.py` (Drupal 10, its own reader in the module) follows this section. First live run on a database that
held DED: **9 added, 0 errors**; second run **0 changed**. The agency's menu is the same on every page, so one fetch of the
Aid section's three index pages (water, waste, air) listed every program. The program text sits in one of two body fields,
`field--name-body` or, on the waste pages, `field--name-field-full-width-paragraph`; the theme repeats small copies of the
first in its menus, so the reader takes the larger field. Contact lines, the footer and "Related information" are dropped.

| Record | Status on 2026-11-14 | Applicants tagged | Source |
|---|---|---|---|
| Clean Water State Revolving Loan Fund | `unknown`: the survey is "due by January 15th", no year | municipality | direct |
| Drinking Water State Revolving Loan Fund | `unknown` | none: "owners of public drinking water systems" is not a tag | pass_through (EPA) |
| Planning Grants: Drinking Water Preliminary Engineering Reports | `unknown`: the state sends applications to the communities it selects | municipality ("Any city, town, village, ... may be eligible"; privately owned systems are not) | direct |
| Nonpoint Source Water Quality Grants (Section 319) | `unknown` | municipality, county, nonprofit ("Funding is distributed to local governments, educational institutions, and nonprofit organizations") | pass_through |
| Deconstruction Grants Program | `unknown`: "Application deadlines are posted with the online application information" | municipality, county ("Cities of the first class, cities of the second class, villages and counties of 5,000 or less population") | direct |
| Illegal Dumpsite Cleanup Program | `unknown`: reimbursement, "no specific deadlines" | municipality, county ("Political subdivisions. This can include municipalities, counties, Natural Resources Districts, ...") | direct |
| Scrap Tire Management Grant Programs | `unknown` | municipality, county, nonprofit ("private entities, nonprofit organizations, and political subdivisions") | direct |
| Energy Efficiency and Conservation Block Grant | `unknown`: "The second-round application period is open through April 15, 2026" has passed; `closes_at` is the first deadline sentence, the 2023 formula award | municipality, county ("Nebraska counties and local communities are eligible to apply for subawards") | pass_through |
| Energy Efficiency Revolving Loan Fund (K-12 schools) | **open**, no dates: "Status: Program open." | school ("Nebraska K-12 public schools can now apply") | direct, loan |

### Where each `pass_through` comes from (the page's own sentence)

- DWSRF: "The Environmental Protection Agency makes the capitalization grants to states to help establish their DWSRF programs."
- Section 319: "Under Section 319 of the federal Clean Water Act, the federal government provides funding to the Nebraska Department of
  Water, Energy, and Environment (DWEE)".
- EECBG: "Counties, cities, and tribes that received direct federal EECBG funding are not eligible for subawards from DWEE."
- The CWSRF page says loans "can be combined with other federal and state funding assistance" and names no federal source of its own
  money, so it stays `direct` (the Missouri DNR precedent for the revolving-fund loans). The school energy loans say "capitalization
  grants to States" and do not say whose: `direct`, by the same rule.

### Shared changes (`connectors/hand_list.py`)

Measured together, as the DED changes were (stored database of 7,734 records, and the 116 fixture records of the other agencies):
**0 tag moves, 0 hash moves, fixtures identical.** A first version of the "can apply" phrase was measured too and moved three
records (two Missouri DED CDBG pages gained a `household` tag, Kentucky's CMAQ page changed text) because "the maximum amount any
applicant can apply for is $500,000 or $5,000 per household" is an amount limit, not an eligibility statement; the phrase is now
"can now apply" and a test pins the amount sentence as not an applicant sentence.

- `AGENCY_OPEN_RE` reads the labelled line "Status: Program open." (the energy pages).
- `ELIGIBILITY_LABEL_RE` reads "Who's Eligible" (straight or curly apostrophe: the waste pages) and "What communities are considered
  for these grants?" (the drinking water planning grants).
- `APPLICANT_SENTENCE_RE` reads "Funding ... distributed to ..." (Section 319) and "can now apply" (the school loans).
- Reader, not shared: the waste and planning pages answer "Who's Eligible" in a paragraph, so each sentence of a paragraph under an
  eligibility heading is read as one of that heading's list items (`APPLICANT_ITEM_MAX` 400).

### Scope calls (Saj to overrule; each is one line in `PAGES`)

- **In (nine pages):** the pages that name local governments or public bodies as applicants.
- **Out, applicants named are not local governments:** Litter Reduction and Recycling ("public and private entities"), the electric grid
  resilience grants (Nebraska utilities, application closed 2024-06-21, "anticipates a future application opportunity ... in 2027"),
  lead testing for schools and childcare facilities, the VW trust and Clean Diesel rebates (school buses, past rounds).
- **Out, not open for applications yet:** the State Energy Program ("Awarded-Program Under Development") and ONE RED (a $307 million
  EPA award; "DWEE is working to set up the funding programs"). ONE RED's three programs go on when a page opens a round.
- **Not read this session:** the Brownfields pages and the Dollar and Energy Saving Loans page (the school loans are read through
  the EERLF page, which says "Program open" and points to it). Either may belong on the list; read them before deciding.

### Gaps

- The two revolving funds' (CWSRF and DWSRF) rounds are the biennial Needs Survey and an annual Intended Use Plan, which the pages name
  without a year: `unknown`, nothing guessed.
- EECBG's `closes_at` is the first deadline sentence on the page (the 2023 formula award); the later rounds, to 2026-04-15, are in the
  text. Status is `unknown` either way.

## Implemented, NDOT (2026-11-14)

`connectors/ne_dot.py` (Umbraco, its own reader in the module; no `robots.txt`, so one GET a second) follows this section.
First live run on a database that held DED and DWEE: **8 added, 0 errors**; second run **0 changed**. Umbraco pages here have no
`h1`: the title is the `<title>` without " - NDOT". The text is `div#main` on the newer template and `div.mainContent` on the two
older pages (TA, HSIP); the contact block and resources sit in the footer. The transit funding page holds four programs, so it is
one record per program (`SPLITS`, the 2026-11-11 split rule).

| Record | Status on 2026-11-14 | Applicants tagged | Source |
|---|---|---|---|
| Transportation Alternatives | `unknown`: the page is the 2023 call ("Applications must be received by April 30th, 2023"), never updated | none: the page names no applicant | pass_through ("$47 million of federal TAP funds") |
| Highway Safety Improvement Program | `unknown`: "HSIP applications received by January 31 st each year" has no year; the sentence is kept | none: "local public agencies (LPA)" is not a tag (below) | pass_through ("This program provides Federal funding") |
| County Bridge Match Program | **closed**: "Applications for the 2025 funding round are closed." (it opens "every September") | county | direct |
| Economic Opportunity Program | `unknown`: awards "as it is received", no round | none | direct |
| Section 5311 Rural Public Transportation, 5311(f) Intercity Bus, 5339 Bus and Bus Facilities | `unknown` | none | pass_through ("Provides federal funding ...", "A federal grant program ...") |
| Section 5310 Enhanced Mobility | `unknown`: "Applications accepted Oct. 31 to Nov. 30", no year; the sentence is kept | none | pass_through |

**Read this one before relying on the page:** the 5310 window ("Oct. 31 to Nov. 30") would be open today (2026-11-14) if it is this
year's, and the page does not say which year. The yearless rule shows it as `unknown` with the sentence kept. That is the cost of
the rule (the same one that holds CDBG's "Sept. 15" rows).

### Shared changes: none kept

A candidate tagger rule was measured and **not kept**: `local public agencies` as municipality and county (the federal-aid highway
word for a city, county or other political subdivision, HSIP's only applicant wording). On the stored database it moved **34 tag
records and 17 other hashes, all California portal records** (Urban Streams Restoration, Baldwin Hills Conservancy, Water Recycling,
CalHome, Supervised Visitation, and others), each gaining county and municipality. Whether California means a city or county by it
is a judgment about 34 records outside this session, so it is **Saj's call**; HSIP stays untagged until then. The yearless-sentence
handling is the same module-local override DED has (a third module that needs it would move it into the agency-page table).

### Scope calls (Saj to overrule; each is one line in `PAGES`)

- **In (five pages, eight records):** the programs that take applications, from NDOT's local assistance pages and its transit funding page.
- **Out, no application:** the Federal Funds Purchase Program (an exchange of federal funds for state cash), County Soft Match (a list
  of monthly balances), the Accelerated Capital Improvement Program (NDOT's own expressway construction).
- **Out, the page carries no program text:** the Off-System Bridge Program (it announces a selection and links documents) and the State
  Recreation Road Fund (it links guidelines). The County Bridge Match page is the readable one of NDOT's bridge programs.
- **Not read this session:** the Surface Transportation Program book (`/projects/program-book-2027/`) and the other pages the
  `/projects/` index links. Read them before deciding whether any takes applications.

### Gaps

- TA's page is the 2023 call. When NDOT posts a new call, the page text changes and the status follows with no code change.
- Five of eight records name no applicant the shared tagger reads (above); they will not show on a "local governments" filter until
  the pages or the tagger do.
- NEMA is not built (deferred in the survey table): its grants page links FEMA's own pages and its Hazard Mitigation page is an
  overview with a Notice of Interest form.

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
