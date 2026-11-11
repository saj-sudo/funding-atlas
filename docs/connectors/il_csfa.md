# Illinois CSFA connector (`il_csfa`): source, raw data and field mapping

Milestone 9, connector 4. Written 2026-10-28 from the 50-state census (`docs/surveys/state_portals.md`), before the
parser. The first state index where "listed" is the status: the page lists rounds that are posted now, and a round
that ends leaves the list.

## Implemented (2026-10-28, same day)

`connectors/il_csfa.py` follows this doc. First live run on a fresh database: 119 records added in 27 seconds (all
open; 83 rolling; 9 pass-through; 35 native with eligibility and 84 GMS from the list alone), 0 errors. Second run: 0
changed, 0 missing. On the Illinois page: 11 open municipal rows (all likely, from 16 agencies) and 0 between rounds,
because nothing has left the list since the first read. Spot-checked that the municipal tags come from the source's own
eligibility text (Small Business Development Centers: "Local counties or municipalities with established
community/economic development departments"; Aviation Fuel Tax: "Units of local government that are public airport
owners").

## Implemented, second pass (2026-11-03): AmpliFund pages and NOFO quotes

Saj's call on both open items. The 88 GMS rows' AmpliFund pages are read every run (decision 1 superseded), and six
native rounds whose program text said `N/A` or `SEE NOFO` carry eligibility sentences quoted from their NOFO PDFs
(decision 6). Run on the published database: 100 records changed (every GMS row gained a CSFA number, a description,
its funding source, labelled eligibility and, where the page has prose, applicant tags; 7 native rounds gained NOFO
quotes), then 5 more once the shared negation rule stopped reading "not-for-profit" as a negation (decision 7). The
Illinois page went from 11 to **38 open municipal rows**: 24 GMS (the eight DNR Coastal Management rounds, the three
Aging Pathways rounds, SCIP, the EOC and Homeland Security rounds, Sharps, Unsewered Communities, two Climate Pollution
Reduction rounds, Law Enforcement Camera, Local Food Infrastructure, Deflection, Radiological Preparedness) and 17
native (Lead Service Line Inventory, Federal Grant Support, two Grocery Initiative rounds and Transportation
Alternatives among them, by their NOFOs). 8 of 60 DNR rows name a municipality; 15 GMS rows name no applicant at all;
8 native `Government Organizations` rounds still carry no municipal tag (down from 14), because neither their program
text nor their NOFO names one. Found on the way: the shared `NEGATION_RE` matched `not-for-profit` and had been
dropping sentences that name not-for-profits as applicants, in Illinois (the two Tourism rounds, four DCEO rounds)
and in Maryland (one Commerce record); fixed in the shared rule and measured on every stored record.

## The source

The Catalog of State Financial Assistance (CSFA) belongs to the Grant Accountability and Transparency Act (GATA) office
in the Governor's Office of Management and Budget. `https://gata.illinois.gov/grants/csfa.html` is a frame around the
state-run ASP.NET application at `https://omb.illinois.gov/public/gata/csfa/`. Pages used:

| Page | What | Fetches per run |
|---|---|---|
| `OpportunityList.aspx` | one static HTML table, `tblList`: title, agency, application date range, award range | 1 |
| `Opportunity.aspx?nofo=<n>` | one native opportunity: 18 labelled fields, 5 KB | 35 |
| `Program.aspx?csfa=<n>` | the program an opportunity belongs to: eligibility, description, subject area | 33 (two opportunities share one program) |
| `AgencyList.aspx` | agency number to full name, 31 agencies | 1 |
| `https://il.amplifund.com/Public/Opportunities/Details/<guid>` | one GMS row's AmpliFund page (since 2026-11-03) | 88 |

About 160 requests a run, 0.3 s apart, about 80 seconds. No JavaScript, no session, no query form; the ViewState fields
are never posted. The pages do not carry a last-modified signal, so every page is read every run (the pa_grants rule).

`robots.txt`: `gata.illinois.gov` allows every agent not on its block list and disallows only `/cgi-bin/` for `*`; the
connector's agent (`funding-atlas/0.1`) is on no block list. `omb.illinois.gov/robots.txt` answers a BIG-IP logout
page with no rules, so there is nothing restricting the application.

### The list (2026-10-28)

119 rows, every one open on its own dates (none ended, none future). Date range is `MM/DD/YYYY - MM/DD/YYYY` or
`MM/DD/YYYY - No end date` (83 rows). Award range is `$min - $max` or `Not Applicable` (8 rows).

Two row shapes:

```html
<td><a href='Opportunity.aspx?nofo=2023'>Business Attraction Prime Sites</a></td><td>DCEO (420)</td>
<td>09/20/2021 - 06/30/2027</td><td>$250000 - $25000000</td>

<td><i Class='gms'>GMS</i>&nbsp;<a href='GMS.aspx?url=https%3a%2f%2fil.amplifund.com%2fPublic%2fOpportunities%2fDetails%2fc828f2fd-...&title=APS_FY27+Pathways+Program' target='_blank'>APS_FY27 Pathways Program</a></td>
<td>AGE (402)</td><td>08/20/2026 - No end date</td><td>$15000 - $75000</td>
```

| | Rows | Agencies |
|---|---|---|
| native (`Opportunity.aspx?nofo=`) | 35 | DCEO 23, EPA 4, DOT 3, DHS 2, IAC, IEMAOHS, ISBE 1 each |
| GMS (a link out to AmpliFund, `il.amplifund.com`) | 84 | DNR 60, IEMAOHS 8, AGE 3, ICCB 3, EPA 2, IFA 2, SBEL 2, and one each for BHE, ICJIA, LETSB, OSFM |

`nofo` numbers are unique (35 of 35). The GMS rows have no CSFA identifier on the list; the AmpliFund GUID in the link
is their key.

### A native opportunity page

```
Awarding Agency Name        Commerce And Econ Opp
Type of Assistance Instrument  Grant
CSFA_Number                 420-45-2608
Agency Funding Program      Business Attraction Prime Sites
Anticipated Number of Awards   130
Estimated Total Program Funding  120000000.00
Single Award Range          $250000 - $25000000
Source of Funding           State
Cost Sharing or Matching Requirements  Yes
Posted Date                 09/20/2021
Application Date Range      09/20/2021 - 06/30/2027 : 11:59pm
Grant Application Link      https://dceo.illinois.gov/aboutdceo/grantopportunities/2608-2023.html
Attachments                 Opportunity.pdf (FileView.aspx?nofo=2023)
```

Fields are `<div id="div_...">` inside a two-column table (`div_CSFA_Number`, `div_Funding_Source`,
`div_Cost_Sharing_Match_Required`, `div_Assistance_Type`, `div_Application_Range`,
`div_Grant_Application_URL`). The breadcrumb links to the program (`Program.aspx?csfa=2608`). On the 35: assistance type
is Grant for all; source of funding State 26, Federal 8, Federal and State 1. For rounds with no due date the detail page
says "General announcement open for a period of time with no specific due dates for applications." where the list says
`No end date`.

### A program page

`<div id="div_...">` blocks again. Used: `div_Program_Name`, `div_CSFA`, `div_Short_Desc`, `div_Objective`,
`div_Eligible_Applicants` (a `;`-list), `div_Applicant_Eligibility` (free text), `div_Subject_Area`,
`div_Program_Website`. The eligible-applicant vocabulary across the 33 programs: Government Organizations 23, Nonprofit
Organizations 19, For-Profit Organizations 12, Education Organizations 8, Small Businesses 7, Other 4, Public Housing
Organizations 3, Individuals 3. Subject Area has six values: Economic Development 20, Government Services 5, Public
Safety 4, Quality of Natural, Cultural, and Environmental Resources 2, Education 1, Human Services 1.

Where a town would look, `Applicant Eligibility` is the useful text. Community Development Block Grant Disaster
Response: "Only units of general local government (i.e., cities, villages, townships and counties) that have received a
Gubernatorial Disaster Declaration may apply for funding."

### Behind the GMS links

`GMS.aspx?url=...` is an interstitial that tells the reader a login is needed to apply and links on to
`https://il.amplifund.com/Public/Opportunities/Details/<guid>`. That page (Euna Grants, 22 to 47 KB) is public and
server-rendered; the AmpliFund host serves no `robots.txt` (the path 302s to an error page). Since 2026-11-03 the
connector reads it (decision 1). Every value sits in a `div.display-group` as a `display-label` and a `display-field`;
dates are written by script (`$('#postedDate').html(...getDateString('9/21/2021 ...'))`) and read as empty. The
labels used, and what the 88 pages held on 2026-11-03:

| Label | Values |
|---|---|
| `CSFA Number` | `422-30-0103`; on 85 of 88 |
| `Description` | prose on 84 |
| `Funding Sources` | `Federal Or Federal Pass Through` 67, `State` 21 |
| `Eligible Applicants` | comma-joined: the CSFA labels (`Government Organizations` on 75, `Nonprofit Organizations` 53, `Education Organizations` 45, `For-Profit Organizations` 20, `Others` 4, `Individuals`, `Small Businesses`) and, on a few, the Grants.gov vocabulary (`State Governments`, `County Governments`, `City or township governments`, `Special District Governments`, `Native American tribal governments (Federally recognized)`, `Nonprofits with 501(c)(3) status (excludes institutions of higher education)`, `Public and State controlled institutions of higher education`); absent on 4 |
| `Applicant Eligibility Information`, `Additional Eligibility Information` | prose on 21 and 35; `N/A` on some; DNR's Coastal rounds: "Eligible applicants include units of local government (e.g., municipalities, park districts, school districts, forest preserve districts), universities, and non-profit organizations" |
| `Fund Activity Categories` | the Grants.gov list, joined with `, ` although the names contain commas (`Education Employment, Labor, and Training`); `Natural Resources` on 21, empty on 41 |
| `Matching Requirement` | `Yes` on 27, absent on 61 |
| `Award Type`, `Submission Timeline Type`, `Opportunity Funding`, `Capital Grant` | `Non Competitive` 25 / `Competitive` 21; `Rolling` 61 / `One Time` 19; a dollar figure on most |
| `Agency Contact Name` / `Phone` / `Email`, `Opportunity Manager`, `Additional Users`, `State Awarding Agency Contacts` | named people: never read |

## Field mapping (Program model in `pipeline/models.py`)

Native rows are the list row plus the opportunity page plus the program page; GMS rows are the list row plus the
AmpliFund page (the list row alone when that page cannot be read and no copy is stored).

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `il_csfa` |
| source_id | link | native `nofo-<n>`; GMS `gms-<guid>` |
| source_url | link | native `Opportunity.aspx?nofo=<n>` on the CSFA host; GMS the AmpliFund link the state itself shows (extracted from the `url` parameter, never fetched) |
| external_number | `CSFA_Number`; AmpliFund `CSFA Number` | `420-45-2608`; null when neither has it |
| name | list title | whitespace collapsed |
| level / jurisdiction | constant | `state` / `IL` |
| administering_agency | list agency number | the full name from `AgencyList.aspx` without its number (`Department Of Natural Resources`); the list's own text if the number is not on the table |
| agency_code | list agency | `IL-` plus the list abbreviation (`IL-DCEO`) |
| funding_type | `Type of Assistance Instrument` | Grant → grant; GMS rows by the shared title keyword `funding_type_for`; else null |
| funding_source | `Source of Funding`; AmpliFund `Funding Sources` | contains `Federal` → `pass_through`; else `direct` |
| amount_min / amount_max | list award range | `$min - $max` as stated (`$0` and `$1` kept); `Not Applicable` → null |
| match_required | `Cost Sharing or Matching Requirements`; AmpliFund `Matching Requirement` | Yes → True, No → False; null when absent |
| match_pct | none | null |
| status | list date range | see status rules |
| opens_at / closes_at | list date range | start; end, null for `No end date` |
| closes_at_text | list date range | `No end date` verbatim when the end is open; else null |
| rolling | list date range | `No end date` → True; else null |
| summary | program `Short Description`, else `Objective`; AmpliFund `Description` | whichever the row has |
| eligibility_text | program page; AmpliFund page; NOFO quotes | `Eligible applicants: <labels>`, then `Applicant eligibility: <text>` (and `Additional eligibility: <text>` from AmpliFund), then `NOFO (read <date>): <quoted sentences>` for the native rounds in `NOFO_QUOTES` |
| eligibility_structured | program page; AmpliFund page | `{"eligible_applicants": [...], "subject_area": "..."}`; for GMS `fund_activity_categories`, `opportunity_funding`, `award_type`, `submission_timeline` when present |
| applicant_types | labels, free text, NOFO quotes | see decisions 2, 6 and 7 |
| categories | program `Subject Area`; AmpliFund `Fund Activity Categories` | see decision 3; the AmpliFund string is split into the known Grants.gov names (longest first) and each goes through the shared table (`Law, Justice, and Legal Services` → public_safety, `Community Development` → infrastructure, `Employment, Labor, and Training` → workforce, `Housing`, `Energy`; `Natural Resources`, `Environment`, `Education` and the rest → other) |
| alns | none | always empty |

### Status rules

In order; the first that applies wins. Anything the list shows is, in the state's words, an active opportunity.

| The list says | Status |
|---|---|
| start date after today | forecasted |
| end date before today | closed |
| otherwise (start on or before today, end ahead or open) | open |

All 119 were open on the day.

### What happens when a round leaves the list

`resolve_missing(source_id)`: the list is the only place a round is posted, and a round that ends is dropped, so
leaving the list is not a closure the source stated. The result is `unknown` (the wv_grants rule), with one exception
that costs nothing: a native round's `Opportunity.aspx?nofo=<n>` page is re-read if the process has no list; if it still
answers with a date range whose end has passed, the status is `closed` with that end date. GMS rows (whose AmpliFund
page writes its close date by script only) and unreadable pages: `unknown`. A round that comes back resumes with its
dates.

### Change detection

The hash is over the Program. Nothing volatile is stored: the pages carry a posted date but no modified stamp, and the
posted date is not mapped. Attachments and contact names stay in the payload.

## Decisions (defaults; override at review)

1. **The GMS rows read their AmpliFund page** (Saj, 2026-11-03; until then the list alone, "thin but honest"). The host
   serves no robots rules, the page is public and server-rendered, and it carries the same kinds of fields the native
   program page does, so a GMS row and a native row now have one shape. A page that cannot be read falls back to the
   stored copy, as the native pages do. The daily run is about 80 seconds longer.
2. **`Government Organizations` and `Education Organizations` and `Other` tag nothing; the free text decides.** The
   pa_grants and ca_grants rule: `Government Organizations` covers state agencies, local governments, tribes and
   districts alike (23 of 33 programs carry it). `Nonprofit Organizations` → nonprofit, `For-Profit Organizations` and
   `Small Businesses` → business, `Individuals` → individual, `Public Housing Organizations` → housing_authority.
   `Applicant Eligibility` goes through the shared keyword tagger in `connectors/text.py`, which knows `city`, `village`,
   `township`, `borough` and `local jurisdiction` since 2026-10-28. The label table is shared with pa.gov and California.
3. **Subject Area maps by the portal's word, once per program.** Economic Development → infrastructure (the pa.gov
   "Community & Economic Development" rule), Public Safety → public_safety, Human Services → health; Government
   Services, Education, and "Quality of Natural, Cultural, and Environmental Resources" (a mix of parks, water and arts)
   → other. The portal's text is the `source_code`.
4. **`No end date` is rolling and keeps its words in `closes_at_text`.** The state's "General announcement open for a
   period of time" is the same claim; it lands in the between-rounds group only if the round leaves and comes back.
5. **Superseded by decision 1** (was: native detail pages are fetched, GMS pages are not).
6. **A native round's NOFO is quoted by hand, not read by the run.** For a round whose program text names no applicant
   (`N/A`, `SEE NOFO`, a reference to the NOFO), the PDF at `FileView.aspx?nofo=<n>` was read once with `pdftotext` and
   the sentences that say who may apply are kept in `NOFO_QUOTES`, keyed by nofo number with the date read, and fed to
   the shared tagger and into `eligibility_text` as `NOFO (read <date>): ...`. The source's own words, nothing
   paraphrased; a NOFO is a fixed document for its nofo number, and a new round gets a new number and no quote until a
   person reads it. Building PDF reading into the daily run (a new dependency or `poppler` on the runner) waits for
   the third state that needs it. Read on 2026-11-03: 1998 Redeploy Illinois (county units of government), 2725 Lead
   Service Line Inventory (a county, municipality, township, ...), 3149 Federal Grant Support (local governments),
   4240 and 4335 Grocery Initiative (units of local government; Local Government Entity), 4356 Transportation
   Alternatives (city or township governments, county governments). Not quoted: 2004 (the attachment is a one-page
   summary with no eligibility), 2990 and 4342 (nonprofits), 3159 (names no applicant type), 4334 (grocers only), 4348
   (a nonprofit with a university), 4360 (EMS resource hospitals), 4338 (the attachment is deleted on the host).
7. **Free text is read sentence by sentence and a negated sentence tags nothing**, the Texas and WebGrants rule, now
   for both row kinds: DNR's Wildlife Restoration page says "not open to Forest Preserve Districts or local units of
   government". The shared `NEGATION_RE` no longer fires on `not-for-profit`, which it had been doing since 10.1.

## Known gaps (the source's wording, not the parser's)

- 15 of 88 GMS rows name no applicant on their AmpliFund page (labels absent or `Others`, no prose); 52 of DNR's 60
  rows carry only the broad labels, so 8 DNR rows reach the municipal page (the Coastal Management rounds).
- 8 native `Government Organizations` rounds still carry no municipal tag after their NOFOs were read (decision 6):
  the source does not say. Downstate Transit Improvement Fund is among them (its attachment is deleted on the host).
- The NOFO quotes are a hand-read table (decision 6); a new round's NOFO is unread until someone runs `pdftotext` on it.
  Read 2026-11-11 (roadmap 10.6): 4359 Oral Health Wellness lists "Corporation – For Profit, Corporation - Not for
  Profit, Tax Exempt, Government Entity, University / Community College, School District"; not quoted, because
  "Government Entity" is a broad label that tags nothing and the row would not reach a page. Of the 70 open GMS rows with
  no local tag, most are DNR, aging and adult-education subawards; IEMA's BRIC 2023 and FMA 2022 say "Applicants
  have been predetermined by the Federal Emergency Management Agency (FEMA) via the FEMA GO application system", so no
  town applies there. The Illinois State Police NG9-1-1 Expenses round says "9-1-1
  Authorities ... shall be eligible to apply" (a county or municipal emergency telephone system board); since
  2026-11-11 "9-1-1 authorities" tags `special_district` (Saj's call), and the round gains it, the only stored record
  that moves. It stays in the possible tier: the tier reads local-government wording, not tags.
- The tagger reads `Baltimore City` and `City of Philadelphia` as named places, not as "cities may apply".

## Out of scope

- The program list (`ProgramList.aspx`, 1,562 programs) and the awards: programs are the catalog (ALN's analogue), not
  rounds. A later session may read them like the SAM catalog.
- Attachments (`FileView.aspx`) as a thing the run reads (decision 6 quotes six of them by hand) and the mailing list.

## Verification

- `tests/test_il_csfa.py` against `tests/fixtures/il_csfa/` (the list trimmed to a dozen rows, three opportunity pages,
  two program pages and the agency table, saved by `scripts/probe_il_csfa.py`): both row shapes, `No end date`, award
  range and `Not Applicable`, the eligibility maps, the agency lookup, status by date, `resolve_missing`.
- Two live runs: all added, then 0 changed.
