# South Carolina's agency pages: survey and two connectors (12.9, 2026-11-24)

South Carolina has no public state grants index (`docs/surveys/state_portals.md`). Breadth first: the CDBG agency
(Commerce), then the Rural Infrastructure Authority, the state's water and sewer funder. Surveyed read-only with the
connectors' User-Agent, 3 s between requests to a host, pages saved to disk and read from the saved copy.

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Department of Commerce (CDBG, ARC, SCRC, Rural Development) | `www.sccommerce.com` | Drupal (Layout Builder) | stock Drupal file: `User-agent: *` with the core/admin/search disallows, **no `Crawl-delay`**, no `ClaudeBot` rule | **readable**, built: `sc_commerce` |
| Rural Infrastructure Authority (state grants, SRF loans) | `ria.sc.gov` | WordPress (a Foundation theme), nginx | `/robots.txt` answers 404: no restriction | **readable**, built: `sc_ria` |

Every page asked for answered 200; no challenge, no script shell (the program text is in the HTML).

## What Commerce gives (`sc_commerce`)

The site was rebuilt: the old one-page-per-CDBG-program pages (Community Infrastructure, Community Enrichment, Special
Projects, Neighborhood Revitalization, Business Development) no longer exist. `/incentives-grants/grants` now links one CDBG
page, its "How to apply" page, and one page each for ARC, SCRC and the Rural Development Initiative.

- **CDBG** (`/incentives-grants/grants/community-development-block-grant-cdbg` plus `.../community-development-block-grant/how-apply`).
  The program page says who may apply and what CDBG supports; it names no funding category. The how-to-apply page names
  the five categories of the 2026 program year and gives each its round:
  Community Infrastructure (spring round), Community Enrichment and Local Priorities (fall round), Business Development
  and Ready to Go ("may be submitted at any time").
- **ARC** (`.../appalachian-regional-commission-arc`): two programs under two `h2`s, the Area Development program
  (competitive, "timelines and deadlines vary by funding cycle") and the Local Access Road program ("LAR applications may be
  submitted anytime throughout the year").
- **SCRC** (`.../southeast-crescent-regional-commission-scrc`): the SEID grant program; "There is no open SCRC funding
  opportunity at this time."
- **RDI** (`.../rural-development-initiative-rdi`): an annual competitive grant to county and municipal governments, with a
  dated 2026 timeline.

### Scope calls

- **CDBG is five records, one per funding category the how-to-apply page names** (a page that holds several programs is one
  record per program). Each record is the program page's text (summary, who can apply, what CDBG supports) followed by the
  round section of the how-to-apply page that names the category. Community Infrastructure keeps the page's `source_id`
  (`cdbg`); the others are `cdbg#community-enrichment`, `cdbg#local-priorities`, `cdbg#business-development`,
  `cdbg#ready-to-go`. "Special Projects" and "Neighborhood Revitalization" are not named on the 2026 pages and are not
  invented; "Local Priorities" and "Ready to Go" are what the page names instead.
- **The application request is the deadline that governs** (the Vermont pre-application rule): a town that has not sent
  the request by "Application request deadline: March 20, 2026" cannot apply on April 20. So `closes_at` is the request
  deadline (the list's first dated line).
- ARC is two records (Area Development keeps `arc`, the road program is `arc#local-access-road`).
- **Out**: SC Export Incentives (STEP and SCOPE: businesses), the Relentless Challenge Grant (organizations that support
  small businesses and entrepreneurs; not a local-government program), the SC Fraunhofer USA Alliance grants (research),
  every page under `/incentives-grants/incentives` (business tax incentives), the CDBG documents page (manuals and forms).
  CDBG-DR and mitigation are the Office of Resilience's (another host, not read; out by the brief in any case).

## What RIA gives (`sc_ria`)

- **State Grants** (`/grants/` plus `/grants/how-to-apply/`): four programs in four titled boxes, Basic Infrastructure,
  Economic Infrastructure/Jobs, Emergencies and Regional Planning. The how-to-apply page carries what the boxes do not:
  the FY27 deadlines, who may apply, and the match rules (per program, in lines that start with the program's name).
- **Loans** (`/loans/`): the Clean Water and Drinking Water State Revolving Funds, "jointly administered by the SC Rural
  Infrastructure Authority (RIA) and the South Carolina Department of Environmental Services". On this host, so read.
- **Viability Improvement Program** (`/utility-viability/vip/`): technical assistance with "the possibility of grant
  funding" for small utilities; it has an "Eligible Applicants" section and an application.

### Scope calls

- State Grants is four records (Basic Infrastructure keeps `grants`; `grants#economic-infrastructure`,
  `grants#emergencies`, `grants#regional-planning`). Each is its box, then the grants page's introduction and the
  how-to-apply page's deadline, eligibility and match sections. A how-to-apply line that starts with another program's name
  ("Regional Planning Grant : No match required.") is kept only on that program's record.
- **Emergencies does not get the FY27 deadlines**: its own box says such projects "may be submitted at any time for Tier 3
  & 4 counties", so the deadline paragraph is left off that record and it reads as rolling.
- The loans page is one record, named "State Revolving Fund (SRF) Loans" (the page's `h2` is just "Loans"; the name is the
  page's own first sentence, "The State Revolving Funds (SRF) are federally capitalized loan programs"). Clean Water and
  Drinking Water are not split: the page describes them together and gives them one process.
- **Out**: SCIIP (`/sciip/`, `/apply-for-a-sciip-grant/`: the one-time ARPA program, "The SCIIP Grant Application deadline
  is now closed", all $1.369 billion awarded; the South Dakota closed-one-time rule), project management, case studies, the
  viability toolkit and technical assistance pages (no application).

## Sample of the raw data (2026-11-24)

Commerce, how to apply (`main#main`):

```
h2  2026 funding deadlines
h3  Spring funding round
p   Community Infrastructure
li  Application request deadline: March 20, 2026, by 5 p.m.
li  Application deadline: April 20, 2026, by 5p.m.
h3  Fall funding round
p   Community Enrichment and Local Priorities
li  Application request deadline: August 21, 2026, by 5 p.m.
li  Application deadline: September 21, 2026, by 5 p.m.
h3  Rolling applications
p   Application requests for Business Development and Ready to Go Program funding may be submitted at any time.
h2  Why is an application request required?      (the read stops)
```

RIA, the grants page and its how-to-apply page:

```
div.titleCell    Basic Infrastructure
div.contentCell  p  The Basic Infrastructure program is designed to assist communities in complying with environmental
                    quality standards, ...
h2  Apply For a State Grant
p   The application deadlines for RIA grants in FY27 are:
p   September 14, 2026 and March 22, 2027 .
h2  Eligibility
p   Local governments, special purpose and public service districts, and public works commissions may apply for RIA grants.
p   Not-for-profit water/sewer companies are not eligible applicants, but may be assisted with RIA funds if ...
h2  Match Requirements
p   Regional Planning Grant : No match required.
```

## Field mapping

Both modules sit on the agency-page table in `connectors/hand_list.py` (`AgencyPageConnector`), each with a reader of its
own (Drupal and WordPress; no other South Carolina agency is read).

`sc_commerce`:

- **Text**: `<main>`; `h2`/`h3`/`h4`, `p`, `li`. The read stops at the first heading among "National objectives" (the CDBG
  page: objectives, hearings, documents), "Why is an application request required?", "Partner programs & contacts",
  "... documents & resources", "Questions about ...", "Do you have questions ...", "Need help ...", "Find incentives ...".
  Lines with a phone number or an e-mail address are dropped. ARC's funding-limit table is not read (the amount parser is
  deferred).
- `name`: the `h1`'s `<strong>` (the rest of the `h1` is a tagline), plus ": category" for a split record.
- A paragraph that only introduces a list of applicants ("Eligible applicants include:") is read as a label, so the list
  under it is the eligibility.
- `status`: the shared `round_for`, with three rules of this module's own, each the page's words: "may be submitted at any
  time" / "anytime throughout the year" is `open` and rolling; "There is no open ... funding opportunity at this time" is
  `closed`; "timelines and deadlines vary by funding cycle" stays `unknown` with the sentence kept.
- Applicants: the shared reader plus one sentence form of this module's own, "Applicants are limited to governmental
  entities" (ARC's road program).
- `funding_source`: `pass_through` for CDBG (the page names HUD); ARC and SCRC are federal commissions the shared rule does
  not know, set by hand to `pass_through`; RDI is state money (`direct`).

`sc_ria`:

- **Text**: the page body, with each `div.titleCell` read as a heading. The read stops at "Program Strategy", "Application
  Process", "Interest Rates", "Program Description", "Featured Case Study". Lines with a phone number or an e-mail address
  (VIP names a staff member) are dropped.
- The deadline paragraph and the paragraph after it are joined ("The application deadlines for RIA grants in FY27 are:
  September 14, 2026 and March 22, 2027."), so the shared cycle rule reads the cycle still ahead.
- `status`: `round_for`; "may be submitted at any time" is `open` and rolling (Emergencies, the SRF loans).
- `funding_type`: `loan` for the SRF record. `funding_source`: the grants are state funds (`direct`); the SRF page says
  "federally capitalized" (`pass_through`, set by hand: the shared rule looks for an agency's name).
- Categories: `water` for every record (water, sewer and storm drainage are all RIA funds).

## Implemented (2026-11-24)

`connectors/sc_commerce.py` and `connectors/sc_ria.py`; `scripts/probe_south_carolina.py` saved the fixtures
(`tests/fixtures/sc_commerce/`, `tests/fixtures/sc_ria/`; a slug read from two pages is `<slug>.html` and `<slug>.2.html`;
contact lines are taken out of the fixtures as well as out of the records). `tests/test_south_carolina.py`: 11 tests.
The probe ran live once, 2026-11-24 (its lines are below). Its scrub was then tightened (contact lines matched by the
probe's own pattern, `mailto:` links removed last) and the breadcrumb `nav` dropped in the Commerce reader; **the fixtures
on disk were rewritten with that final scrub from the copies of the same nine pages saved during the survey minutes
earlier, without asking the sites again**, and each parses to exactly the blocks of its raw page. The records did not
change. The probe's live run:

```
== sc_commerce
  cdbg                           unknown    open=None close=2026-03-20 rolling=None pass_through ['county', 'municipality'] | Application request deadline: March 20, 2026, by 5 p.m.
  cdbg#community-enrichment      unknown    open=None close=2026-08-21 rolling=None pass_through ['county', 'municipality'] | Application request deadline: August 21, 2026, by 5 p.m.
  cdbg#local-priorities          unknown    open=None close=2026-08-21 rolling=None pass_through ['county', 'municipality'] | Application request deadline: August 21, 2026, by 5 p.m.
  cdbg#business-development      open       open=None close=None rolling=True pass_through ['county', 'municipality'] | Application requests for Business Development and Ready to Go Program funding may be submi
  cdbg#ready-to-go               open       open=None close=None rolling=True pass_through ['county', 'municipality'] | Application requests for Business Development and Ready to Go Program funding may be submi
  arc                            unknown    open=None close=None rolling=None pass_through ['nonprofit'] | Application timelines and deadlines vary by funding cycle.
  arc#local-access-road          open       open=None close=None rolling=True pass_through [] | LAR applications may be submitted anytime throughout the year
  scrc                           closed     open=None close=None rolling=None pass_through ['county', 'municipality', 'nonprofit', 'state', 'tribe'] | There is no open SCRC funding opportunity at this time.
  rdi                            unknown    open=None close=2026-10-30 rolling=None direct       ['county', 'municipality'] | Application deadline: 5 pm Oct. 30, 2026
== sc_ria
  grants                         open       open=None close=2027-03-22 rolling=None direct       ['county', 'municipality'] | The application deadlines for RIA grants in FY27 are: September 14, 2026 and March 22, 202
  grants#economic-infrastructure open       open=None close=2027-03-22 rolling=None direct       ['county', 'municipality'] | The application deadlines for RIA grants in FY27 are: September 14, 2026 and March 22, 202
  grants#emergencies             open       open=None close=None rolling=True direct       ['county', 'municipality'] | Projects that require an urgent response to resolve a documented emergency may be submitte
  grants#regional-planning       open       open=None close=2027-03-22 rolling=None direct       ['county', 'municipality'] | The application deadlines for RIA grants in FY27 are: September 14, 2026 and March 22, 202
  loans                          open       open=None close=None rolling=True pass_through ['county', 'municipality', 'special_district'] | Project requests may be submitted at any time using the appropriate project questionnaire
  vip                            unknown    open=None close=None rolling=None direct       ['county', 'municipality'] |
```

| Record | Name | Status on 2026-11-24 | `closes_at` |
|---|---|---|---|
| `sc_commerce` `cdbg` | Community Development Block Grant (CDBG): Community Infrastructure | unknown (2026 spring round past) | 2026-03-20 |
| `cdbg#community-enrichment` | ... : Community Enrichment | unknown (2026 fall round past) | 2026-08-21 |
| `cdbg#local-priorities` | ... : Local Priorities | unknown (2026 fall round past) | 2026-08-21 |
| `cdbg#business-development` | ... : Business Development | open, rolling | none |
| `cdbg#ready-to-go` | ... : Ready to Go | open, rolling | none |
| `arc` | Appalachian Regional Commission (ARC): Area Development Program | unknown ("deadlines vary by funding cycle") | none |
| `arc#local-access-road` | Appalachian Regional Commission (ARC): Local Access Road Program (LAR) | open, rolling | none |
| `scrc` | Southeast Crescent Regional Commission (SCRC) | closed ("no open SCRC funding opportunity at this time") | none |
| `rdi` | Rural Development Initiative (RDI) | unknown (the heading still says "Applications are now open"; the deadline is past) | 2026-10-30 |
| `sc_ria` `grants` | RIA State Grants: Basic Infrastructure | open | 2027-03-22 |
| `grants#economic-infrastructure` | RIA State Grants: Economic Infrastructure/Jobs | open | 2027-03-22 |
| `grants#emergencies` | RIA State Grants: Emergencies | open, rolling (Tier 3 and 4 counties) | none |
| `grants#regional-planning` | RIA State Grants: Regional Planning | open | 2027-03-22 |
| `loans` | State Revolving Fund (SRF) Loans | open, rolling | none |
| `vip` | Viability Improvement Program | unknown (no round stated) | none |

Not run through `pipeline/run.py` or against the database in this session (the runner's registry is edited centrally): the
modules were imported and `SITE.fetch` / `normalize` exercised directly, in the probe and in the tests.

### Gaps and follow-ups

- **Tagger** (`connectors/text.py`, not changed here): ARC's applicant lists say "State and local agencies", "Government
  entities", "Local governing boards" and "Applicants are limited to governmental entities"; none is tagged, so the two ARC
  records carry no municipality or county tag (Area Development is tagged `nonprofit` only). RIA's "special purpose and
  public service districts, and public works commissions" is tagged as local governments but not `special_district` (the
  SRF page's "special purpose districts" is).
- **Shared status rules this module carries on its own** and a third state may want in `hand_list.py`: "may be submitted at
  any time" / "anytime throughout the year" as open and rolling; "There is no open ... funding opportunity at this time" as
  closed; a sentence split at "5 p.m. Oct. 30, 2026" (folded to "5 pm" in this reader).
- **Shared applicant sentences** the reader did not know: "loans are made available to municipalities, counties and special
  purpose districts", "Eligible candidates for assistance will be ...", "Applicants are limited to ...".
- CDBG's categories are read from the 2026 how-to-apply page; when the 2027 program year is posted the category list
  (`CDBG_CATEGORIES`) should be checked against it. A category the page stops naming keeps its record, without a round.
- ARC's funding limits are a table and are not read (amount parser deferred). RDI's "Up to $500,000 / 10% required match"
  tiles are in the stored text only.
- RIA's SRF page is one record; the Clean Water and Drinking Water funds' Intended Use Plans and project questionnaires
  are PDFs. SCIIP is out while it stays closed.
- Not surveyed (other hosts, none on this session's allowlist, none requested): SCDOT (Transportation Alternatives, C
  Program), SC Parks, Recreation and Tourism (PARD, LWCF, RTP), SC Emergency Management (FEMA pass-throughs), the Office of
  Resilience (CDBG-DR and mitigation), SC Department of Environmental Services.
