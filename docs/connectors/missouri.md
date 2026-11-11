# Missouri's agency pages (`mo_ded`, `mo_dnr`, `mo_modot`, `mo_sema`, `mo_parks`): source, raw data and field mapping

Milestone 12.6e, the fifth agency state in the 12.6 cost ranking (after Vermont, Connecticut, North Dakota and Kentucky).
Written 2026-11-11 from a read-only survey of the candidate agencies' hosts and pages, before the parser. The agencies
are built one at a time, each its own commit; this doc grows with them.

## Survey (2026-11-11, the connectors' own User-Agent, one GET per page, 1.5 s apart)

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Economic Development (DED) | `ded.mo.gov` | Drupal 10, Layout Builder (`.node__content`) | allows all | **built** (this doc) |
| Transportation (MoDOT) | `www.modot.org` (the apex redirects) | Drupal 10 | blocks only `/media/oembed` | **built** (below), two pages |
| State Parks and Historic Preservation | `mostateparks.com` | Drupal 10, same `.node__content` layout | `User-agent: *`, no disallows | **built** (12.6f, below) |
| Natural Resources (DNR, with Energy) | `dnr.mo.gov` (`energy.mo.gov` redirects to `/energy`) | Drupal 10 | blocks `/taxonomy/` | **built** (below) |
| Emergency Management (SEMA) | `sema.dps.mo.gov` | not Drupal, an older CMS with `.php` pages, a Bootstrap layout and the program in `#main-content` | blocks only legacy directories | **built** (below), the same base with another selector |
| Housing (MHDC) | `mhdc.com` | no generator tag | no `robots.txt` (404) | deferred: its own CMS, mostly developer tax credits |
| Conservation (MDC) | `mdc.mo.gov` | Drupal 10 | **`Disallow: /`** in at least one agent block | **stopped** on robots, as ADECA was; recorded, not read |

## Implemented, DED (2026-11-11)

`connectors/missouri_drupal.py` (the base) and `connectors/mo_ded.py` follow this doc. First live run on an empty
database: **7 added, 0 errors**; second run **0 changed**. Open: Downtown Revitalization and Industrial Infrastructure
(year-round, "until funding is exhausted"), the Emergency cycle and the Water/Wastewater program ("currently open");
closed: the Competitive Cycle's three programs ("FY26 ... Application is now closed", the FY27 date not set).
Applicants tagged: Downtown Revitalization and Emergency (`municipality`, `county`). The other five pages name no
applicant in the text the connector reads, so they carry none (see Gaps).

Shared changes (two phrasings in `connectors/hand_list.py`), measured on the database restored from `gh-pages` (7,630
stored records, 39 connectors) with `scripts/measure_tagger.py`: **0 tag moves, 0 hash moves**.

- `AGENCY_OPEN_RE` reads "is currently open" ("The Emergency Cycle is currently open."); without it both DED pages
  that say so were `unknown` while the source said open.
- `ELIGIBILITY_LABEL_RE` reads the heading "Do I Qualify?" as the eligibility section, which DED's pages use for it.

## Implemented, DNR (2026-11-11)

`connectors/mo_dnr.py` on the same base follows this section. First live run on a database that held DED: **20 added,
0 errors**; second run **0 changed**. Open: Flood Resiliency Improvement Grants, Section 319 Nonpoint Source Subgrants,
DWSRF Lead Service Line Funding and the Well Plugging Grant (each page's "Application Period is Open" heading); closed:
EECBG, Energy Loans, Energy Audit Reimbursements, Source Water Protection, Water Safety and Security and the Scrap Tire
Surface Material Grants ("Application Period is Closed"); `unknown`: the revolving-fund loans and grants with no banner
and no round sentence (CWSRF and DWSRF loans, the small borrower loan, the CWSRF engineering report, integrated
management plan and regionalization grants, the DWSRF engineering report grant), the Multipurpose Water Resource Fund,
Section 604(b) and the Emergency Energy Loans. The source states no round for them, so none is stored.

DNR's program pages share one template: an "Application Period is Open" or "... is Closed" heading, then "Who Can
Apply", "Eligible Projects and Costs", "Award Amounts and Match", "Application Process" and a closing list of past awards.
The `.node__content` element also holds the theme's footer blocks ("Popular Links", "Navigation", "Contact Information"),
so the Missouri reader stops at them and at an "Awards" heading (a list of past recipients, which would tag towns as
applicants). The five division indexes (`/water/...`, `/energy/...`, `/waste-recycling/...`, `/land-geology/...`,
`/financial-assistance-opportunities/recreation-historic-preservation`) are the lists these pages came from; the module
reads the program pages, not the indexes.

| Group | Slugs (all under `https://dnr.mo.gov`) |
|---|---|
| Water, clean water | `small-borrower-loan`, `cwsrf-engineering-report`, `cwsrf-integrated-management-plan`, `cwsrf-loan`, `cwsrf-regionalization` |
| Water, drinking water | `dwsrf-engineering-report`, `dwsrf-lead-service-line`, `dwsrf-loan`, `source-water-protection`, `water-safety-security`, `well-plugging` |
| Water, other | `flood-resiliency`, `multipurpose-water-resource`, `section-319`, `section-604b` |
| Energy | `energy-audit`, `energy-loans`, `energy-emergency-loans`, `eecbg` |
| Waste | `scrap-tire-surface` |

Left out (Saj to overrule): the CWSRF On-site Wastewater grant (a pass-through to nonprofits for homeowners), the
Operator Certification Training Voucher (individual operators), Scrap Tire Cleanup and Disposal Reimbursement
(nonprofits only), Brownfields Assessments (a service DNR performs, not funding), Solid Waste Management District Grants
(a forms page for the 20 districts, which award the money), the Grid Resilience Formula Funding subgrants (electric
utilities and grid operators, not local governments), Wood Energy Tax Credit and Low-Income Weatherization (businesses and
households), the Soil and Water Cost-Share Practices (landowners), and every tax credit and every link to another agency
(DED's CDBG is `mo_ded`; USDA and DOE pages are theirs).

### Shared changes (all in `connectors/hand_list.py`, one per Missouri page that needed it)

Measured with `scripts/measure_tagger.py` on the 7,630 stored records restored from `gh-pages`, before and after all
changes of this session: **0 tag moves, 0 hash moves**.

- `AGENCY_OPEN_RE` reads "Application Period is Open" (DNR's banner on every open program).
- `APPLICANT_SENTENCE_RE` reads "Eligible recipients" (EECBG, Energy Loans) and "eligible to submit" (the scrap tire
  grants). Without the first, the paragraph "Eligible recipients include the following:" was not an applicant sentence, so
  it ended the list under "Who Can Apply" and every item was dropped (EECBG tagged nothing).
- `AgencyPageConnector.APPLICANT_ITEM_MAX` (default 160, unchanged for every other state; Missouri sets 400): DNR writes
  each applicant list item as a whole sentence ("Municipalities, counties, public sewer or water districts, political
  subdivisions or instrumentalities of the state are eligible for wastewater and nonpoint source pollution control project
  loans"), which the 160-character limit dropped, leaving the CWSRF loan tagged `nonprofit` and nothing else.
- `clause_cut` (before tagging, the stored text keeps the clause): "that are not owned by the federal government" (the DWSRF
  loan's definition of a public body, whose "not" dropped the whole line), "provide ... to a group of households" (the DWSRF
  engineering report names who the project serves, not who applies) and "other than state agencies" (the scrap tire grants
  exclude the state; it tagged `state`).

### Funding source

`pass_through` only where the page names a federal source of the money, `direct` otherwise (loans included: the pages
call them revolving funds and name no federal source, only an EPA handbook). The sentences, verbatim:

| Slug | The page's sentence |
|---|---|
| `cwsrf-engineering-report`, `cwsrf-integrated-management-plan`, `cwsrf-regionalization`, `dwsrf-engineering-report` | "Funding is provided by the CWSRF fund, capitalization grant additional subsidization allocation." (the DWSRF page says "DWSRF fund") |
| `dwsrf-lead-service-line` | "Funding is provided by the Bipartisan Infrastructure Law, and made available through the Drinking Water State Revolving Fund." |
| `section-319` | "Funding is provided by EPA as subgrants through the department." |
| `section-604b` | "Under Section 604(b) of the federal Clean Water Act, the Missouri Department of Natural Resources offers grant sub-awards ..." |
| `source-water-protection`, `water-safety-security`, `well-plugging` | "Section 1452(g) and (k) of the federal Safe Drinking Water Act authorizes the Missouri Department of Natural Resources to distribute part of the Drinking Water State Revolving Fund(s) ..." |
| `eecbg` | "... is a formula grant offered as a part of the Bipartisan Infrastructure Law (BIL) to cities and counties ..." |

### Gaps (DNR, recorded, not hidden)

- `section-604b` (regional planning commissions and councils of government) and `source-water-protection` (community
  public water systems) name applicants the shared tagger has no word for, so they carry none. Not a rule change for two
  records; a tagger session can add `special_district`-style words when a third case appears.
- `well-plugging` tags `nonprofit` from "Community and not-for-profit noncommunity public water systems", which is a type of
  public water system; the applicants are public water systems.
- `energy-loans` and `energy-emergency-loans` are open to businesses and agricultural entities as well as public bodies; the
  record is one program with the applicant types the page lists.
- Ten of twenty records are `unknown` because the page states no round. The revolving-fund loans are year-round by nature,
  but the pages do not say "year-round", and the rule is the source's words.

## Implemented, MoDOT (2026-11-11)

`connectors/mo_modot.py` follows this section. First live run **2 added, 0 errors**; second run **0 changed**. Both are
`unknown`: the Transportation Alternatives Program's last call ("Notice of 2025 Statewide Call for Rural Projects -
Applications due July 11, 2025") is past and the page says it funds "every two years (even years)" without naming a 2026
call, and Partnership Development states no round. TAP is `pass_through` ("Federal TAP funds are provided through the
FHWA") with a 20% match ("The LPA is required to match the project with a minimum of 20%"); Partnership Development is
`direct`. Neither page names an applicant in a word the tagger reads (TAP says "the LPA", a local public agency).

MoDOT's `/programs` page is a list of sections, and the other pages read (Aviation, Transit, Freight, Rail, Waterways,
Highway Safety, the LPA home page) describe what the section does and name no application or round. The money MoDOT passes
to local governments (the surface transportation block grant, off-system bridges, FTA 5304 and 5310 formula funds) goes to
metropolitan planning organizations and counties by formula. So MoDOT is two records, on purpose, and a third is a
line in `PAGES` when a call page appears. Three URL guesses for Cost Share and Safe Routes to School answered 404.
`NAMES` in the base overrides a name when the page's last `h1` is not the program's (Partnership Development's is
"Partnership Development Application").

## Implemented, SEMA (2026-11-11)

`connectors/mo_sema.py` follows this section, on the same base with `BODY_SELECTOR = "#main-content"` (the page chrome and
menus sit outside it). First live run **4 added, 0 errors**; second run **0 changed**. All four are `unknown`: they are
event- or cycle-driven and state no open round.

| Record | What the page says | Applicants tagged | Funding |
|---|---|---|---|
| `mdag`, Missouri Disaster Assistance Grant | "Applications Due: 30 days from date of incident"; for "non-federally declared Stafford Act events"; 50/50 state and local, state share up to $200,000 | `municipality`, `county` ("Eligible Applicants: Political Subdivisions (city or county)") | `direct` (state) |
| `mitigation`, Hazard Mitigation Assistance Grants (HMGP, FMA, BRIC) | HMGP applications by project type, the FMA process and notice of interest, FEMA GO; subapplicants apply to SEMA as the applicant | `municipality` | `pass_through` (FEMA) |
| `public-assistance`, Public Assistance Program | "The deadline to submit an RPA is January 31, 2025" (past); 30 days from a disaster declaration | none (see Gaps) | `pass_through` ("Funding is provided through the Federal Emergency Management Agency (FEMA)") |
| `empg`, Emergency Management Performance Grant | "provides resources to the State Emergency Management Agency and local government emergency management agencies"; reimbursement up to 50% | `municipality`, `county` | `direct` (the page names no federal funder, only "all federal requirements") |

**The Mitigation page is one record, not three** (a deviation from Saj's one-record-per-program rule of 2026-11-11,
**confirmed by Saj on 2026-11-11**). Its sections interleave: HMGP's process is described in two places, with shared "Eligible Subapplicants",
"Eligible Activities" and planning-requirement blocks between them and the FMA process, and BRIC has no section of its own.
`split_sections` cuts one contiguous section per program, so a split would give HMGP two records or FMA the HMGP text. A
reader of the page gets one row that says what the three are. If SEMA reorganises the page by program, it becomes a
`SPLITS` entry.

Shared change (`APPLICANT_SENTENCE_RE`): `provides (aid|resources) to` (ND DES had `aid`), which reads EMPG's sentence.

## Shared changes in this session, measured together

All of the changes to `connectors/hand_list.py` in the DED, DNR and SEMA commits were measured on the 7,630 stored records
restored from `gh-pages` (39 connectors) with `scripts/measure_tagger.py`, against a snapshot taken before any of them:
**0 tag moves, 0 hash moves**, after the first change and again after the last. Vermont, Connecticut, North Dakota and
Kentucky are therefore untouched. (That measurement rested on the stored database, which did not hold Kentucky's records; 12.6f re-checked these changes against every fixture of the four states, 78 records, clean worktrees of `99d4c9f` and `d1c82b5`: **0 moved**.) The full suite is 1,065 tests, green.

## The Missouri state page

Built from a scratch database holding all four connectors' records (`cli.py export`): **5 open municipal rows**: CDBG
Downtown Revitalization, CDBG Emergency, DWSRF Lead Service Line, Flood Resiliency Improvement Grants and Section 319. A row
that names no local-government applicant (CDBG Water/Wastewater and Industrial Infrastructure, the Well Plugging Grant,
which names nonprofits) is open but not on the municipal page, by the navigator's existing rule; the rest are `unknown` or
closed and sit in "between rounds" or "everything".

## Implemented, State Parks (2026-11-11, 12.6f)

Written from a read-only survey before the parser. `mostateparks.com` is the Missouri Department of Natural Resources'
Division of State Parks site: Drupal 10, the same `.node__content` layout as DED and DNR, a `robots.txt` of
`User-agent: *` with no disallows. DNR's recreation page links its grants out to it. The **Grant Opportunities** page
(`/page/grant-opportunities`; `/basic-page/grant-opportunities` redirects to it) is the hub: a "Grants Currently
Accepting Applications" list, then one section per program, with a page of its own for each program but one.

| Slug | Page | The page's own words (2026-11-11) |
|---|---|---|
| `lwcf` | `/basic-page/land-and-water-conservation-fund-lwcf-grants` | "The application period for 2027 LWCF Grants is now OPEN." "Application packets must be postmarked on or before Nov. 13, 2026." "Grants can be awarded to any local government, city, county or public school district." 50% match, minimum $25,000 |
| `rtp` | `/page/recreational-trails-program-rtp-grants` | "The 2026 RTP Grant Round is currently closed. The 2027 RTP Grant Round will open in December." "available to local and state governments, school districts and nonprofit organizations"; 20% match; $250,000 maximum |
| `orlp` | a section of the hub, no page of its own | "The department is currently accepting ORLP project applications." "Project applications for the 2027 round must be submitted to the Division of Missouri State Parks by June 30, 2027, at 5 p.m." Eligible: state agencies and local governments in an urban area of 25,000 or more, and tribes; $300,000 to $15 million |
| `bus` | `/page/missouri-state-parks-bus-grant-program` | "The Bus Grant Program grant round is currently open and is accepting applications for the 2026-2027 school year." "Applications must be submitted by email or mail by May 14, 2027"; "one state-funded grant program"; schools and youth nonprofits |
| `hpf` | `/page/state-historic-preservation-office/historic-preservation-fund-grants` | "We are not accepting applications for Historic Preservation Fund grants at this time." 60/40 match; a "Who can apply:" section |

**ORLP is read from the hub** with `SPLITS` (the Kentucky EEC mechanism): its own section is the record, and two tails (the
top "Grants Currently Accepting Applications" list, and the Recreational Trails section onward) belong to no record, so
LWCF's and the bus grant's deadlines cannot reach ORLP. The federal Notice of Funding Opportunity is also on Grants.gov,
which is the `grants_gov` connector's row; the two are not merged.

Left out (Saj to overrule): the Certified Local Government page (a designation program; its money is the Historic
Preservation Fund's 10% pass-through, which `hpf` covers), Grant Workshops (an event list), and every "Past recipients" and
"Administration guide" list (towns as recipients, not applicants).

### Result (2026-11-11)

`connectors/mo_parks.py` follows this section, on the Missouri base. First live run **5 added, 0 errors**; second run
**0 changed**. Open: LWCF (to **2026-11-13**), ORLP (to 2027-06-30), the Bus Grant (to 2027-05-14); closed: RTP ("The 2026
RTP Grant Round is currently closed. The 2027 ... will open in December.": closed, not `forecasted`, because the page gives no
year or date and the rule is the source's words) and the Historic Preservation Fund. With the other four Missouri connectors
the Missouri page has **7 open municipal rows** (it had 5): LWCF and ORLP are the two new ones. The Bus Grant tags `school` and
`nonprofit` and does not appear on the municipal page.

| Record | Applicants tagged | Funding source (the sentence) |
|---|---|---|
| `lwcf` | `municipality`, `county`, `school` ("Grants can be awarded to any local government, city, county or public school district.") | `pass_through`: the page says "Federal funding available for LWCF grants"; the hub says "federally funded through the U.S. Department of the Interior, National Park Service" |
| `rtp` | `municipality`, `county`, `state`, `school`, `nonprofit` ("available to local and state governments, school districts and nonprofit organizations") | `pass_through`: the hub says RTP "is federally funded through the Department of Transportation's Federal Highway Administration"; the RTP page names no federal agency |
| `orlp` | `state`, `municipality`, `county`, `special_district`, `tribe` (the "Eligible Applicants Include:" list, an `h5`) | `pass_through`: "funded through the National Park Service" |
| `bus` | `school`, `nonprofit` ("Bus grants have been made available to Missouri schools and youth-focused nonprofit organizations") | `direct`: the hub says "one state-funded grant program" |
| `hpf` | `municipality`, `county`, `nonprofit` ("Who can apply:" Certified Local Governments, county governmental entities, municipalities, qualified nonprofits) | `pass_through`: the hub says "federally funded through the National Park Service"; the HPF page names no federal agency |

RTP and HPF are set per record (`FUNDING_SOURCES`) from the hub's sentence because their own pages name no federal agency.
RTP read `pass_through` at first only by accident, from a mention in its past-recipients tail, and went `direct` the moment the
reader stopped at that tail; a test now pins it.

### Shared changes in this session (all measured, two ways)

1. **The stored database** (7,630 records from `gh-pages`, 39 connectors), one change at a time, each snapshot diffed against the one
   before: **0 tag moves, 0 hash moves** after every change and cumulatively. This cannot see a connector that is not in that
   database yet: it holds none of Kentucky's (12.6d) or Missouri's records, and not North Dakota's part 2 when it was taken.
2. **Every fixture of every agency-page connector** (Vermont, Connecticut, North Dakota, Kentucky, Missouri: 116 records), record
   hash, status, close date and tags, before and after the shared files: **6 moved**.
   - The four State Parks records (new, expected): `lwcf` gains its close date and applicants, `orlp` its close date, `rtp` and `hpf` read
     `closed` instead of `unknown`, `rtp` gains `municipality` and `county`.
   - **`ky_tc/cmaq`: `unknown` to `closed`.** Its page says "The Office of Local Programs is not currently accepting applications for
     funding." That is the wording the new closed rule reads; it was `unknown` only because no rule read it. Judged correct (the source
     states it); `tests/test_kentucky.py` now pins `closed`. The first daily run after the merge shows it as a changed record.
   - **`mo_dnr/well-plugging`: `closes_at` none to 2026-12-31.** The page says "To receive priority funding consideration,
     applications must be submitted by Dec. 31, 2026" and "Applications received between Jan. 1, 2027, through Feb. 28, 2027, may be
     awarded on a first-come, first-serve basis if funds remain available." The date is a real, stated priority deadline but not the
     final close. Kept (the Vermont pre-application precedent): the stored `closes_at_text` is that sentence, so the page shows
     "priority funding consideration", and a test pins both. **Saj can overrule**: dropping it is a guard in `deadline()`.
   - The 33 earlier Missouri records and the 78 Vermont, Connecticut, North Dakota and Kentucky records otherwise keep identical hashes.
   - **12.6e's own shared changes, re-checked the same way** against clean worktrees of `99d4c9f` and `d1c82b5`: 78 of those fixtures
     compared, **0 moved**. (12.6e's note above rested on the stored database alone; this is the stronger check and it agrees.)

Each rule is kept because it moves a named record that a test pins.

- `AGENCY_CLOSED_RE`: "is currently closed" (RTP) and "not (currently) accepting applications" (HPF). The second matched the
  *open* regex and lost to the negation guard, which left a page that says "not accepting" as `unknown`.
- Abbreviated months, with or without the period ("Nov. 13, 2026", `Sept.`, `Dec`), in `AGENCY_DATE_RE` and `_date()`. Needs a day
  and a year, so "the Mar 2026 report" is no date.
- `DUE_RE`: "postmarked" (LWCF) and "submitted to ... by" (ORLP: "must be submitted to the Division of Missouri State Parks by
  June 30, 2027"), the second only in a sentence about applications, the existing "submitted by" guard. Before it, ORLP read
  "open" from the wrong sentence ("NPS will be accepting applications for the ORLP grant once a year") and stored no deadline.
- `APPLICANT_SENTENCE_RE`: "Grants can be awarded to" (LWCF).
- `connectors/text.py`: "local and state governments" tags `municipality` and `county` (RTP). The singular "local and state
  government recovery capability" (North Dakota DES) is untouched and still tags only `state`, as before.
- The Missouri reader (not shared): reads `h5` and `h6` headings (ORLP's applicant list is headed by an `h5`) and stops at the
  past-administration-guides, sample-projects and funded-grants lists, which name towns as recipients, not applicants.

### Gaps (State Parks, recorded, not hidden)

- LWCF names its applicants in one sentence only; the "public school district" tags `school` beside the two local-government tags.
- RTP's 2027 round "will open in December" (no year, no date). The status is `closed` and the page's sentence is stored; when the
  page announces the round, it reads open on the next run.
- ORLP's eligible applicants must be in "a qualifying area" (an urban area of 25,000 or more); the tags say who may apply, not
  whether a given town qualifies, which is the page's own limit.
- The Certified Local Government program (a designation) and its HPF set-aside are not separate records.

## The platform

DED, MoDOT and DNR run the state's Drupal 10 theme. The page's text sits in `.node__content`: an `.alert` block with the
status, then tabbed `h2` sections ("Description", "Do I Qualify?", "How Do I Apply?", "Need Help?"), all in the static
HTML. The `h1` is printed twice on DED's pages, the department's name and then the program's, so the title is the last
`h1`. `/cdbg/opportunities-to-apply` lists the CDBG pages; `/program-lookup` is a paginated Views list (10 a page) of every
DED program, most of them business tax credits and incentives, which are not read.

## The pages (DED)

| slug | path | what it is | records |
|---|---|---|---|
| `competitive-cycle` | `/programs/community/community-development-block-grants-competitive-cycle` | Community Facilities, General Infrastructure, Demolition | 3 |
| `economic-development` | `.../community-development-block-grants-economic-development` | Downtown Revitalization, Industrial Infrastructure | 2 |
| `emergency` | `.../community-development-block-grants-emergency-long-term-recovery` | the emergency cycle | 1 |
| `water-wastewater` | `.../community-development-block-grants-waterwastewater` | the Water/Wastewater program | 1 |

Left out (Saj to overrule, see Decisions): `.../community-development-block-grants-disaster-recovery`, `...-mitigation`
and `...-covid-19`, and `/programs/community/community-development-block-grants` (it redirects to `/cdbg`, which carries
public notices and no program).

## Raw samples (verbatim, 2026-11-11)

The status is the page's alert block:

```
Competitive Cycle:     <p>FY26 CDBG Competitive Cycle Application is now closed.</p>
Economic Development:  <p><strong>Currently Accepting Applications!</strong></p><p>This is an open, year-round cycle.
                       Applications will be accepted until funding is exhausted.</p>
Emergency:             The Emergency Cycle is currently open.
Water/Wastewater:      The Water/Wastewater Program is currently open. To apply, a community must go through the Missouri
                       Water Wastewater Review Committee to receive an invitation to apply for CDBG funds.
```

The applicants, where a page says who:

```
Economic Development, "Do I Qualify?", Downtown Revitalization:
  Eligible applicants include non-entitlement cities and counties. Counties may apply on behalf of no more than one
  target area within their boundaries, if applying under one application.
Emergency, "Do I Qualify?":
  The recipient is a non-Entitlement Unit of General Local Government within the State of Missouri
```

## Field mapping

The agency-page table in `connectors/hand_list.py` (`AgencyPageConnector`), with the Missouri base's page reader.

| Field | From |
|---|---|
| `source_url` | the page's URL (a page with several programs shares it) |
| `name` | the program heading for a split page ("CDBG Community Facilities"), else the page's program `h1` |
| `status`, `closes_at` | the shared round table over the page's own sentences: a deadline ahead is `open`, closed wording is `closed`, open wording with no date is `open`, nothing is `unknown` |
| `applicant_types` | the shared tagger over the "Do I Qualify?" and eligibility lists and the sentences that name an applicant |
| `funding_type`, `funding_source` | `grant`; `pass_through` for every DED record (`FUNDING_SOURCES`, see Decisions) |
| `match_required` | a "match ... required" sentence (Downtown Revitalization's 20%); null when the page says nothing |
| `categories` | `community development` through the shared portal table |
| `summary` | the first paragraph that is not a status line |

A page that names its programs twice (Competitive Cycle, Economic Development) is cut by `join_tabs` in the base: each
tab is split at the program headings on its own and a program's description and qualifying text are joined, so a record
is one program, not the first tab run into the second. The first program keeps the page's own `source_id`, the others are
`slug#program`.

## Decisions

1. **Municipal programs only.** DED's `/program-lookup` lists business tax credits, incentives and broadband programs;
   none is read. The four CDBG pages that take applications from communities are.
2. **Disaster Recovery, Mitigation and COVID-19 are left out** (the Kentucky CDBG-DR precedent, 2026-11-11). Their pages
   say "Disaster funding is exhausted", "CDBG Mitigation funds have been exhausted" and "not currently accepting
   applications": closed for good, so they would be rows that never open. Saj can overrule; adding one is a line in
   `PAGES` and a fixture.
3. **Every DED record is `pass_through`.** The CDBG State program is HUD money the state passes to non-entitlement
   communities. Only the pages that print "HUD" in the section a record owns said so, which made one HUD program read as
   two funding sources; the funding source is set per record instead of guessed from the text.
4. **Industrial Infrastructure is read as a community program**, not a business one: the page's own sentence is "The local
   government applicant must provide ...", the businesses are beneficiaries. The tagger does not read "local government
   applicant" (see Gaps), so the record names no applicant rather than naming the wrong one.
5. **`records_for` is overridden in the base, not in `hand_list.py`** (`join_tabs`): one state, one page template, and the
   repo's rule is no abstraction before a third case. If DNR or MoDOT pages turn out to use two tabs too, it moves.

## Gaps (recorded, not hidden)

- Five of seven DED records tag no applicant: Community Facilities, General Infrastructure, Demolition and Water/Wastewater
  never name one in the text read (CDBG's eligible applicants are non-entitlement cities and counties, which the
  guidelines PDFs say and these pages do not), and Industrial Infrastructure says "The local government applicant".
  A hand quote from the guidelines is possible if one is open and would put a row on a page (Saj's rule, 10.6): none was
  open on 2026-11-11 except Water/Wastewater, which is invitation-only through the Review Committee.
- The water page's "Applicants must be sure that the project beneficiaries are at least 51% low-to-moderate income
  persons." is kept as an eligibility line by the shared `applicants must be` phrasing; it states a condition, not an
  applicant, and tags nothing.
- The Competitive Cycle's FY27 date is "TBD" on the page, so no opening date is stored.

## Gaps (MoDOT and SEMA, recorded, not hidden)

- `public-assistance` tags no applicant: the page says "eligible public entities" and "eligible applicants" without a word
  the tagger maps (the public entities are local governments, private nonprofits and tribes, which FEMA defines and the page
  does not list). `tap` says "LPA" (local public agency), also not a tagger word. A vocabulary change for two records is not
  made here; a third case in another state adds it.
- `empg` is `direct` because the page never names FEMA or the Department of Homeland Security, only "all federal
  requirements"; EMPG is federal money in fact. The rule is what the page says.
- Housing (MHDC) is not read, nor is Conservation (MDC, blocked by robots). State Parks is read (12.6f, above).
