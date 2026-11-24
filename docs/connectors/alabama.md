# Alabama's agency pages: survey (12.9, 2026-11-24)

Alabama has no public state index of funding programs (`docs/surveys/state_portals.md`). Surveyed read-only with the
connectors' User-Agent, 3 s apart, pages saved and read from disk.

**ADECA is not read.** The Department of Economic and Community Affairs (`adeca.alabama.gov`) holds Alabama's municipal core:
CDBG, the Land and Water Conservation Fund, the Recreational Trails Program, the energy and law-enforcement grants. Its
`robots.txt` disallows `ClaudeBot`, and Saj's decision (2026-11-24) is that ADECA is never fetched; Alabama's other agencies
are read where their own `robots.txt` allows. No request was made to that host. So Alabama's records are the environment
and transportation programs only, and the state page will lack CDBG until ADECA gives permission.

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Economic and Community Affairs (ADECA: CDBG, LWCF, RTP) | `adeca.alabama.gov` | not fetched | **`ClaudeBot` disallowed** | **not read** (Saj, 2026-11-24) |
| Environmental Management (ADEM) | `adem.alabama.gov` | Drupal | the stock Drupal file, no `ClaudeBot` rule, no `Crawl-delay` | **readable**, built: `al_adem` |
| Transportation (ALDOT) | `www.dot.state.al.us` | static pages (Dreamweaver templates, IIS) | none: `/robots.txt` redirects to the not-found page | **readable**, built: `al_dot` |
| Emergency Management (AEMA) | `ema.alabama.gov` | WordPress | allows all but `/wp-admin/` | readable, **nothing to read**: no grant program page (see Gaps) |

## What the two agencies give

**ADEM.** The home page's "Grants and Funding" menu lists nine links. Three are programs a town applies to, each on a page
of its own text: the State Revolving Fund (`/water/state-revolving-fund-srf`), the Alabama Recycling Fund grants (a section
of `/waste/recycling-program`) and the Section 319(h) nonpoint source grant
(`/water/nonpoint-source-pollution-program/section-319-grant-resources`).

**ALDOT.** `/programs.html` lists some forty programs; under "Local Transportation" sit the ones a city or county applies
to. Each page is a heading, one or two paragraphs and a list of the year's documents (guidelines, application, FAQ, awarded
projects): the round's dates are in the PDFs, not on the page.

## Scope, one record per program

`al_adem`, three records:

- **State Revolving Fund (SRF)**: one record for the Clean Water and Drinking Water funds, because the page describes them
  together (one eligibility paragraph, one "How to Apply"). `/water/guidance-srf-applicants` has a section for each fund
  (Form 370 for public water systems, Form 340 for public bodies): the split into two records is a follow-up.
- **Alabama Recycling Fund Grants**: the page's "Recycling Grants" section only. The rest of the page (facility
  registration, reporting) is regulation and is cut away as tails of the split; the "Recycling Announcements" list at the
  top of the page is kept with the record because it dates the round.
- **NPS Section 319(h) Grant**.

Left out of `al_adem`: the Scrap Tire Program page (ADEM awards cleanup contracts to contractors from a ranked site list;
no grant a town applies for is described); Brownfields and the Boating Infrastructure Grant (both link to
`storymaps.arcgis.com`, another host and a script-rendered story); the Storage Tank Trust Fund (tank owners); Groundwater
Festivals, the Coastal Program and Remediation and Cleanup (not funding programs); the ARPA/SRF updates and dashboard
(awards made).

`al_dot`, four records: the **Transportation Alternatives Program (TAP)**, **ATRIP-II**, the **Rebuild Alabama Act Annual
Grant Program** and the **Industrial Access Program** (the sponsor is a city or county). Left out: the Alabama
Transportation Infrastructure Bank (a heading and five document links, no sentence; loans), ATRIP-I (closed bond
programme), the transit pages (5310, 5311, urbanized areas: operators, not towns), HSIP and Rail-Highway (ALDOT selects the
projects), Local Public Agency Projects (the manual for a project already funded), the "Rebuild Alabama Grant ATRIP II Beta
Application" page (a heading over a script-loaded form).

## Field mapping

The agency-page table in `connectors/hand_list.py`; each module has a reader of its own.

`al_adem` (Drupal):

- **Text**: `<main>`; headings `h2` to `h4`, paragraphs and list items. An accordion's `h2` holds a `button`; its text is
  the heading. The read stops at "Technical Assistance" (SRF: needs surveys, reports, forms, the contact block) and at "EPA
  Grant Resources" (319: link lists). Contact blocks, "Helpful Links" and document links at the end are dropped.
- `name`: the page's `h1`; the recycling record takes the program's own name from the grant section's first sentence
  ("Alabama Recycling Fund Grants"), set in `SPLITS`.
- `status`, dates: the shared `round_for`. SRF states no round ("the SRF Intended Use Plan ... is updated up to 4 times per
  year"). Recycling: the announcement "March 2nd, 2026: Grant Application deadline" is a deadline with a date, past today,
  so `unknown` with the date kept; "no later than March 1st of each year" has no year. 319: "(Priority Deadline is July
  1st)" has no year: `unknown`, the line kept as `closes_at_text` (`YEARLESS_RE`).
- `eligibility_text` and applicants: the shared reader ("Any public body, including counties, ... may apply for SRF
  financing"; the three items under "Who is Eligible for Funding:"; "Grant funding is available to state agencies, ...").
- `funding_type`: SRF is a loan (`FUNDING_TYPES`; the name has no keyword).
- `funding_source`: SRF `pass_through` ("funded with a blend of state and federal capitalization funds"), 319
  `pass_through` (a Clean Water Act Section 319(h) subaward with a "non-federal match"), recycling `direct` (the state's
  solid waste disposal fee). Set per record in `FUNDING_SOURCES`: the shared rule looks for FHWA, FEMA, HUD or NPS by name.
- `match_required`: the shared rule (319: "Commit to a minimum 40% non-federal match").

`al_dot` (static pages):

- **Text**: the `div.container` that holds the `h1`. The lead-in question of the first paragraph ("What is the
  Transportation Alternatives program?", a `span` before a `br`) is removed. The read stops at "SELECTED PROJECTS"; lines
  that name staff ("For questions pertaining to ... contact ...") and "... Awarded Projects" links are dropped. The
  year's document links stay as lines ("FY 2027 TAP Guidelines"): they are all the ATRIP-II page says.
- **The Industrial Access table** (board meeting date, time, place, application deadline, twelve rows to 2029) is read into
  two lines: "Application deadlines are: Friday, January 9, 2026; Friday, April 3, 2026; ..." (the table's last column
  under its own header, in the words the shared cycle rule reads) and "Board of Directors meetings: ...". The deadline is
  the first one still ahead.
- `name`: the `h1`.
- `status`: `unknown` on TAP, ATRIP-II and the Annual Grant (no page dates a round); Industrial Access `open` to the next
  application deadline.
- Applicants: the shared reader plus two sentences this module names itself (`OWN_APPLICANT_RE`): TAP's "This program is
  application based for cities, towns, county commissions and metropolitan planning organizations" and Industrial Access's
  "The project sponsor (city or county) will assume ...". ATRIP-II and the Annual Grant name no applicant on the page: null.
- `funding_source`: TAP `pass_through` (its "Federal Highway Administration BIL TAP-Fact Sheet" line), the others `direct`.
- "Funding ratio is 80/20" is not parsed (the shared match rule needs the word "match"); it stays in the text.

## Sample of the raw data (2026-11-24)

```
ADEM, /water/state-revolving-fund-srf
h1  State Revolving Fund (SRF)
p   The Clean Water State Revolving Fund (CWSRF) and the Drinking Water State Revolving Fund (DWSRF) are low interest loan
    programs intended to finance public infrastructure improvements in Alabama. The programs are funded with a blend of
    state and federal capitalization funds. ...
h2  Entities Eligible for an SRF Loan
p   Any public body, including counties, state agencies, incorporated cities and towns, boards, and authorities, may apply
    for SRF financing. ...
h2  How to Apply
p   The first step towards receiving SRF assistance is to submit a preapplication form in order to be listed on the
    Department's Project Priority List (PPL). The PPL is a component of the SRF Intended Use Plan, which is updated up to 4
    times per year. ...
h2  Technical Assistance   (the read stops)

ADEM, /waste/recycling-program
h2  Recycling Announcements
li  March 2nd, 2026: Grant Application deadline ( AEPACS )
h2  General Overview ... Recycling Facility Regulations ... Recycling Facility Reporting Requirements   (cut away)
h2  Recycling Grants
p   Alabama Recycling Fund Grants promote local recycling efforts by providing reimbursement grants to local governments ...
p   Who is Eligible for Funding:
li  Local governments – any municipality, county, or district or authority or any agency thereof which has ...
li  Applications must be received on AEPACS no later than March 1st of each year to be considered for funding.

ALDOT, /programs/TAP.html
h1  Transportation Alternatives Program (TAP)
p   [What is the Transportation Alternatives program?]  MAP-21 established the tap program which essentially replaces the
    long standing Transportation Enhancement (TE) Program.
p   Many of the past TE activities are still eligible under TAP. This program is application based for cities, towns,
    county commissions and metropolitan planning organizations. Funding ratio is 80/20.
h2  GENERAL INFORMATION
li  Federal Highway Administration BIL TAP-Fact Sheet / FY 2027 TAP Memo / FY 2027 TAP Guidelines / FY 2027 TAP Application
p   For questions pertaining to the Transportation Alternatives Program (TAP) contact ...   (dropped)
```

## Implemented (2026-11-24)

`connectors/al_adem.py` and `connectors/al_dot.py`, each a reader of its own on `AgencyPageConnector`;
`scripts/probe_alabama.py` saved the fixtures (`tests/fixtures/al_adem/`, `tests/fixtures/al_dot/`; in the ALDOT fixtures the
staff names of the contact lines are replaced by `[name]`). `tests/test_alabama.py`: 9 tests. Not run through
`cli.py run` (the connector table in `pipeline/run.py` is added centrally): the modules were called directly, as the probe
does. The probe's lines, live, 2026-11-24:

```
== al_adem
  srf                                        unknown    open=None close=None pass_through ['municipality', 'municipality', 'county', 'state'] |
  recycling                                  unknown    open=None close=2026-03-02 direct       ['municipality', 'county', 'municipality', 'county', 'nonprofit'] | March 2nd, 2026: Grant Application deadline ( AEPACS )
  319                                        unknown    open=None close=None pass_through ['municipality', 'county', 'nonprofit', 'state', 'higher_ed'] | Grant Announcement - FY2027 Grant Request for Proposals (Priority Deadline is Ju
== al_dot
  tap                                        unknown    open=None close=None pass_through ['municipality', 'municipality', 'county'] |
  atrip-ii                                   unknown    open=None close=None direct       [] |
  raa-annual-grant                           unknown    open=None close=None direct       [] |
  industrial-access                          open       open=None close=2027-01-08 direct       ['municipality', 'county'] | Application deadlines are: Friday, January 9, 2026; Friday, April 3, 2026; Frida
```

| Connector | Record | Status on 2026-11-24 | Applicants tagged | Type, source |
|---|---|---|---|---|
| `al_adem` | State Revolving Fund (SRF) | unknown (no round stated) | municipality, county, state | loan, pass_through |
| `al_adem` | Alabama Recycling Fund Grants | unknown: "March 2nd, 2026: Grant Application deadline" (past, date kept) | municipality, county, nonprofit | grant, direct |
| `al_adem` | NPS Section 319(h) Grant | unknown: "(Priority Deadline is July 1st)" (kept, no year) | municipality, county, nonprofit, state, higher_ed | grant, pass_through |
| `al_dot` | Transportation Alternatives Program (TAP) | unknown | municipality, county | grant, pass_through (FHWA) |
| `al_dot` | Alabama Transportation Rehabilitation & Improvement Program II | unknown | none (the page names none) | grant, direct |
| `al_dot` | Rebuild Alabama Act Annual Grant Program | unknown | none (the page names none) | grant, direct |
| `al_dot` | Industrial Access Program | **open**, closes 2027-01-08 (the next application deadline in the board table) | municipality, county | grant, direct |

Requests made, survey and probe together: `adem.alabama.gov` 9 (plus the `robots.txt` read before the session),
`www.dot.state.al.us` 12, `ema.alabama.gov` 3. No `Crawl-delay` on any of them; both modules wait 3 s between GETs.

## Gaps and follow-ups

- **ADECA** (CDBG, LWCF, RTP and the rest): not read, by its `robots.txt` and Saj's decision. Ask the department; until
  then Alabama has no community development record.
- **Alabama EMA**: readable, and nothing to read. The site has no grant program page: the home page, "Agency Divisions"
  and "Resources" describe the Recovery Division's Public Assistance and Hazard Mitigation work in a sentence each and link
  the mitigation plans (PDF) and a login portal (`portal.ema.alabama.gov`, not fetched). No connector until the agency
  publishes a mitigation or preparedness grant page.
- **SRF as two records**: `/water/guidance-srf-applicants` has a "Drinking Water State Revolving Fund Program" and a "Clean
  Water State Revolving Fund Program" section (who submits which preapplication form). Splitting the SRF record in two
  needs both pages in one record, which the base's `records_for` does not do for a split.
- **Round dates in documents**: the SRF Intended Use Plans, the 319 request for proposals (an HTML file under
  `/sites/default/files/`, with the year's dates), ALDOT's TAP memo and the ATRIP-II and Annual Grant guidelines are PDFs or
  attachments and are not read. ATRIP-II and the Annual Grant therefore carry a name and nothing else.
- **ALDOT's Annual Grant page links FY 2026 documents** while TAP and ATRIP-II link FY 2027: the page is stale or the
  FY 2027 round is not announced; the record says `unknown` either way.
- **Brownfields and the Boating Infrastructure Grant** live on `storymaps.arcgis.com` (another host, script-rendered): not
  read. The **Alabama Transportation Infrastructure Bank** page states nothing but its document links: left out.
- 319's "Commit to a minimum 40% non-federal match" is not read as a match requirement and TAP's "Funding ratio is 80/20"
  is not read at all: `match_required` is null on both (see the shared-rule wishes in the session report).
