# Indiana's agency pages: survey (12.9, 2026-11-24)

Indiana has no public state index with structured rows (`docs/surveys/state_portals.md`). Surveyed read-only with the
connectors' User-Agent, 3 s apart, every page saved and read from the saved copy. Both agencies sit on one host,
`www.in.gov`, the state's shared CMS (dotCMS: `/dA/` document links, `/api/vtl/sitemap`). `robots.txt` is
`User-agent: *` with no `Disallow` line, a `Sitemap` and no `Crawl-delay`; the modules pause 3 s between GETs all the same.

| Agency | Path | robots | Answer | Verdict |
|---|---|---|---|---|
| Office of Community and Rural Affairs (OCRA) | `/ocra/` | allowed, no `Crawl-delay` | 200, the text is in the HTML | **readable**, built (`in_ocra`) |
| Department of Transportation (INDOT) | `/indot/` | same file | 200, the text is in the HTML | **readable**, built (`in_indot`) |

No page was a script shell, no request was refused or challenged. One guessed INDOT address answered 404 (the page is
`.../community-crossing-matching-grant-program`, "crossing" singular; found on the Local Public Agency Programs hub).

## What OCRA would give

The CDBG hub (`/ocra/cdbg/index`) links six program tiles: Planning Grants, Construction Grants, Recovery Housing Program,
Owner Occupied Rehabilitation, COVID-19 Response Program, Disaster Recovery. It also says who may apply to all of them:
"The State CDBG Program provides grants exclusively to Indiana's non-entitlement local governments. These include cities
with populations under 50,000 (excluding cities of Metropolitan Statistical Areas) and counties with populations under
200,000." The agency's menu adds Stellar Pathways, the Historic Renovation Grant Program, Building Socially Connected
Communities, Rural Empowerment and Development, the Hoosier Enduring Legacy Program, PreservINg Main Street and the
broadband pages.

## Scope (breadth first, one or two agencies a state)

Surveyed: the CDBG hub, Planning Grants, Construction Grants, Stellar Pathways, the Historic Renovation Grant Program
(OCRA); the Local Public Agency Programs hub and Community Crossings (INDOT). Built: three OCRA pages as seven records, one
INDOT page as one.

- **CDBG Construction Grants is five records, one per tab** (the split rule, 2026-11-11): Facilities, Blight Clearance,
  Stormwater Improvements, Main Street Revitalization, Wastewater/Drinking Water. Each has its own maximum award, match and
  eligible activities; the overview and the round above the tabs follow every one. Names are the tabs' own with the page's
  "CDBG" in front ("CDBG Blight Clearance Program"); "Program" is added to the three tabs that lack it, as the page's text
  under each tab says ("Stormwater Improvements Program", "Main Street Revitalization Program (MSRP)", "Wastewater and
  Drinking Water (WDW) Program"). The Facilities Program keeps the page's `source_id`.
- **CDBG Planning Grants is one record**: its nine tabs are plan types of one grant (one application, one deadline), each
  with its own maximum; they stay in the stored text under their headings.
- **Stellar Pathways: in.** A designation that brings state funding; "The lead applicant can be any county government,
  city, municipality, town, township, or a non-profit that serves the entire community".
- **Historic Renovation Grant Program: out.** "this budget does not include funding for the Historic Renovation Grant
  Program ... no additional grants from this program will be awarded" (the funds-exhausted rule).
- **Out, by the brief**: Disaster Recovery (CDBG-DR). **Out, not surveyed** (the request budget): Owner Occupied
  Rehabilitation (OCRA's home page says its 2026 Cycle 3 is open; whether the local government or the homeowner applies was
  not read), Recovery Housing, COVID-19 Response, BSCC, RED, HELP, PreservINg Main Street, the broadband programs.
- **INDOT: Community Crossings only.** The Federal Grant Opportunities page lists federal programs, not INDOT's; the
  railroad grants (Grade Crossing Fund, Crossing Closure, Industrial Rail Service) were seen in the menu and not read.

## Field mapping

The agency-page table in `connectors/hand_list.py`, each module with a reader of its own.

- **Text**: `main article`. The breadcrumb (`#subpage-breadcrumbs`) is dropped. OCRA: a tab strip (`ul.nav-tabs` of
  buttons, then `div.tab-pane`s) is read as a heading per pane, named by its button; a card list that wraps paragraphs in
  list items is read through the paragraphs, once; Stellar's read stops at "Resources" (documents, past designees,
  statistics). INDOT: the read stops at the accordion (`div.accordion-container`: FAQ, guidance, past awards, the asset
  management and Title VI requirements, a July 2025 newsletter article whose dates are a past call's, staff contacts).
- `name`: the banner's `#subpage-main-title`; Stellar's banner is an image with a placeholder `h1` ("Main Billboard"), so
  its first `h2`. "Planning Grants" is stored as "CDBG Planning Grants".
- `status`, `closes_at`: **OCRA writes a weekday, a month and a day, never a year** ("Applications are due on Sunday, July
  12", "2026 Round 2 applications are due on Sunday, Dec. 13"). A month and a day with no year is not a date (decision
  2026-11-14): `closes_at` stays null and the sentence is kept as `closes_at_text`. The Construction page also says "The
  programs listed below are now accepting applications for the 2026 Round 2.", which is `open` by the table's undated open
  wording; the module keeps the deadline sentence as the text beside it. INDOT: "awards were announced on Wednesday,
  October 28, 2026" and "INDOT plans to issue the ... call each September": `unknown`, the September sentence kept.
- `eligibility_text` and applicants: the page's applicant sentences. Planning Grants names none ("communities"), so the
  CDBG hub's two sentences are quoted by hand, dated and attributed (`HAND_QUOTES`, the MDOT precedent). Stellar's "The
  lead applicant can be ..." is not a wording the shared reader knows; the module adds it.
- `funding_source`: the CDBG pages name HUD (`pass_through`); Stellar and Community Crossings are state money (`direct`,
  set by hand: Stellar's page mentions CDBG only to exclude entitlement communities).
- `categories`: `community development`; the Stormwater and Wastewater/Drinking Water records `water`; INDOT
  `transportation`.
- Maximum awards and match percentages are not parsed (the amount parser is deferred); they stay in the stored text.
- Staff names, phone numbers and e-mail addresses are never stored: contact lines are dropped by `DROP_RE`, INDOT's
  accordion is not read, and the fixtures have every contact cut (`scripts/probe_indiana.py`).

## Sample of the raw data (CDBG Construction Grants, 2026-11-24)

```
h1  CDBG Construction Grants
h3  Overview
p   Funding for all Community Development Block Grant programs is provided by the U.S. Department of Housing and Urban
    Development and administered by the Office of Community and Rural Affairs. ...
p   The state CDBG program offers competitive grants to units of local government to support rural areas. ...
h4  Current Funding Round
p   2026 Round 2 proposals are due on Sunday, Oct. 4, by 11:59 p.m. ET and must be submitted via eGMS. ...
p   2026 Round 2 applications are due on Sunday, Dec. 13, by 11:59 p.m. ET and must be submitted via eGMS. ...
p   The programs listed below are now accepting applications for the 2026 Round 2.
ul.nav-tabs   Facilities Program | Blight Clearance Program | Stormwater Improvements | Main Street Revitalization |
              Wastewater/Drinking Water                      (buttons; each names the pane below)
div.tab-pane  The Blight Clearance Program (BCP) offers grants assistance for the acquisition, demolition, clearance or
              remediation of blighted residential and non-residential structures.
  li  The maximum grant award is $500,000, ...
  li  To be eligible for consideration, applicants must provide a local match of 10% of the total project cost.
```

Community Crossings (INDOT):

```
h1  Community Crossings Matching Grant Program
p   Launched in 2016, the Community Crossings Matching Grant (CCMG) Program provides funding to cities, towns, and
    counties across Indiana to improve local roads and bridges. ...
p   Community Crossings is open to all local government units in Indiana. Match percentages are based on population:
li  Cities and towns with populations less than 12,500: 80/20 match   (three more)
h2  Community Crossing Matching Grant Call for Projects
p   State FY 2027 Community Crossings Matching Grant awards were announced on Wednesday, October 28, 2026. ...
p   Moving forward, INDOT plans to issue the Community Crossings Matching Grant call each September on an annual basis.
accordion  Frequently Asked Questions (FAQ) ...   (not read)
```

## Implemented (2026-11-24)

`connectors/in_ocra.py` and `connectors/in_indot.py`; `scripts/probe_indiana.py` saved the fixtures
(`tests/fixtures/in_ocra/`, `tests/fixtures/in_indot/`); `tests/test_indiana.py`. Neither module is in `pipeline/run.py`
or the workflow yet (done centrally), so no run against the database has been made. The probe's live read, 2026-11-24:

```
== in_ocra
  cdbg-planning                              unknown    open=None close=None pass_through ['municipality', 'county', 'municipality', 'county'] | Applications are due on Sunday, July 12, by 11:59 p.m.
  cdbg-construction                          open       open=None close=None pass_through ['municipality', 'county', 'municipality', 'county'] | 2026 Round 2 applications are due on Sunday, Dec. 13, by 11:59 p.m.
  cdbg-construction#blight-clearance         open       open=None close=None pass_through ['municipality', 'county', 'municipality', 'county'] | 2026 Round 2 applications are due on Sunday, Dec. 13, by 11:59 p.m.
  cdbg-construction#stormwater               open       open=None close=None pass_through ['municipality', 'county', 'municipality', 'county'] | 2026 Round 2 applications are due on Sunday, Dec. 13, by 11:59 p.m.
  cdbg-construction#main-street              open       open=None close=None pass_through ['municipality', 'county', 'municipality', 'county'] | 2026 Round 2 applications are due on Sunday, Dec. 13, by 11:59 p.m.
  cdbg-construction#water                    open       open=None close=None pass_through ['municipality', 'county', 'municipality', 'county'] | 2026 Round 2 applications are due on Sunday, Dec. 13, by 11:59 p.m.
  stellar                                    unknown    open=None close=None direct       ['municipality', 'municipality', 'municipality', 'county', 'nonprofit'] | Stellar Pathways workshops will take place on Tuesday, Oct. 27, and Friday, Oct.
== in_indot
  community-crossings                        unknown    open=None close=None direct       ['municipality', 'municipality', 'county'] | Moving forward, INDOT plans to issue the Community Crossings Matching Grant call
```

| Record | Status on 2026-11-24 | Applicants tagged | Source |
|---|---|---|---|
| CDBG Planning Grants | unknown: "Applications are due on Sunday, July 12" (kept, no year) | municipality, county (the hub's sentences, quoted) | pass_through (HUD) |
| CDBG Facilities Program | open, no `closes_at`: "now accepting applications for the 2026 Round 2"; "due on Sunday, Dec. 13" kept | municipality, county | pass_through |
| CDBG Blight Clearance Program | open, as above | municipality, county | pass_through |
| CDBG Stormwater Improvements Program | open, as above | municipality, county | pass_through |
| CDBG Main Street Revitalization Program | open, as above | municipality, county | pass_through |
| CDBG Wastewater/Drinking Water Program | open, as above | municipality, county | pass_through |
| Stellar Pathways Program | unknown: the workshops sentence kept (Oct. 27 and Oct. 30, no year) | municipality, county, nonprofit | direct |
| Community Crossings Matching Grant Program (INDOT) | unknown: awards announced 2026-10-28; "call each September" kept | municipality, county | direct |

### Gaps and follow-ups

- **The five construction records are `open` with no closing date.** The page will go on saying "now accepting" until OCRA
  edits it; after December 13 the record is stale until then. A rule that would date it is described below and was not
  made here (it belongs in `hand_list.py`, and the 2026-11-14 decision says a month and a day with no year is not a date).
- **Wanted, not made (shared rules)**: (1) a weekday, month and day in a sentence that names the round's year ("2026
  Round 2 applications are due on Sunday, Dec. 13") could be dated when the weekday agrees with that year (December 13,
  2026 is a Sunday); (2) `summary_for` skips a paragraph that contains the word "due" in any sense, so the Stormwater
  record's summary is its second paragraph ("... sewer backups due to inadequate resources ..." is skipped); (3) the
  match reader does not see "applicants must provide a local match of 10%" (Blight Clearance: `match_required` null).
- Owner Occupied Rehabilitation: read its page, and add it if the local government is the applicant.
- Not surveyed: Recovery Housing, BSCC, RED, HELP, PreservINg Main Street, OCRA's broadband programs; INDOT's railroad
  grants and its Local Trax and safety programs; IFA (State Revolving Fund), DNR (LWCF, trails), IDHS (mitigation), IHCDA.
- OCRA's round dates also live in its calendar on `events.in.gov` (another host, not on the allowlist, not requested).
