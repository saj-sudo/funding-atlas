# Missouri's agency pages (`mo_ded`, `mo_dnr`, `mo_modot`, `mo_sema`): source, raw data and field mapping

Milestone 12.6e, the fifth agency state in the 12.6 cost ranking (after Vermont, Connecticut, North Dakota and Kentucky).
Written 2026-11-11 from a read-only survey of the candidate agencies' hosts and pages, before the parser. The agencies
are built one at a time, each its own commit; this doc grows with them.

## Survey (2026-11-11, the connectors' own User-Agent, one GET per page, 1.5 s apart)

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Economic Development (DED) | `ded.mo.gov` | Drupal 10, Layout Builder (`.node__content`) | allows all | **built** (this doc) |
| Transportation (MoDOT) | `www.modot.org` (the apex redirects) | Drupal 10 | blocks only `/media/oembed` | **built** (below), two pages |
| State Parks and Historic Preservation | `mostateparks.com` (DNR's LWCF, Recreational Trails, Historic Preservation Fund and Certified Local Government pages live here) | not surveyed | not surveyed | **next session**, its own module |
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

**The Mitigation page is one record, not three** (a deviation from Saj's one-record-per-program rule of 2026-11-11, for
Saj to overrule). Its sections interleave: HMGP's process is described in two places, with shared "Eligible Subapplicants",
"Eligible Activities" and planning-requirement blocks between them and the FMA process, and BRIC has no section of its own.
`split_sections` cuts one contiguous section per program, so a split would give HMGP two records or FMA the HMGP text. A
reader of the page gets one row that says what the three are. If SEMA reorganises the page by program, it becomes a
`SPLITS` entry.

Shared change (`APPLICANT_SENTENCE_RE`): `provides (aid|resources) to` (ND DES had `aid`), which reads EMPG's sentence.

## Shared changes in this session, measured together

All of the changes to `connectors/hand_list.py` in the DED, DNR and SEMA commits were measured on the 7,630 stored records
restored from `gh-pages` (39 connectors) with `scripts/measure_tagger.py`, against a snapshot taken before any of them:
**0 tag moves, 0 hash moves**, after the first change and again after the last. Vermont, Connecticut, North Dakota and
Kentucky are therefore untouched. The full suite is 1,065 tests, green.

## The Missouri state page

Built from a scratch database holding all four connectors' records (`cli.py export`): **5 open municipal rows**: CDBG
Downtown Revitalization, CDBG Emergency, DWSRF Lead Service Line, Flood Resiliency Improvement Grants and Section 319. A row
that names no local-government applicant (CDBG Water/Wastewater and Industrial Infrastructure, the Well Plugging Grant,
which names nonprofits) is open but not on the municipal page, by the navigator's existing rule; the rest are `unknown` or
closed and sit in "between rounds" or "everything".

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
- Missouri's own `mostateparks.com` (LWCF, Recreational Trails, Historic Preservation Fund, Certified Local Government) is
  not read yet, nor are Housing (MHDC) and Conservation (MDC, blocked by robots).
