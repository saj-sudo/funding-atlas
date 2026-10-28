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

About 70 requests a run, 0.3 s apart, under a minute. No JavaScript, no session, no query form; the ViewState fields
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
`https://il.amplifund.com/Public/Opportunities/Details/<guid>`. That page (Euna Grants, 27 KB) is public and
server-rendered: CSFA number, description, categories, funding, a labelled eligibility block. The AmpliFund host serves
no `robots.txt` (the path 302s to an error page). **This connector does not fetch AmpliFund.** It is a second vendor
host, one more 84 requests a run, and the list already carries a title, agency, dates and award range for every GMS
row. Whether to read the 60 DNR pages is a decision for after the first Illinois page is in front of Saj (see Known
gaps).

## Field mapping (Program model in `pipeline/models.py`)

Native rows are the list row plus the opportunity page plus the program page; GMS rows are the list row alone.

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `il_csfa` |
| source_id | link | native `nofo-<n>`; GMS `gms-<guid>` |
| source_url | link | native `Opportunity.aspx?nofo=<n>` on the CSFA host; GMS the AmpliFund link the state itself shows (extracted from the `url` parameter, never fetched) |
| external_number | `CSFA_Number` | native only (`420-45-2608`); GMS null |
| name | list title | whitespace collapsed |
| level / jurisdiction | constant | `state` / `IL` |
| administering_agency | list agency number | the full name from `AgencyList.aspx` without its number (`Department Of Natural Resources`); the list's own text if the number is not on the table |
| agency_code | list agency | `IL-` plus the list abbreviation (`IL-DCEO`) |
| funding_type | `Type of Assistance Instrument` | Grant → grant; GMS rows by the shared title keyword `funding_type_for`; else null |
| funding_source | `Source of Funding` | contains `Federal` → `pass_through`; else `direct`. GMS rows: `direct` (no claim made, the wv_grants default) |
| amount_min / amount_max | list award range | `$min - $max` as stated (`$0` and `$1` kept); `Not Applicable` → null |
| match_required | `Cost Sharing or Matching Requirements` | Yes → True, No → False; GMS null |
| match_pct | none | null |
| status | list date range | see status rules |
| opens_at / closes_at | list date range | start; end, null for `No end date` |
| closes_at_text | list date range | `No end date` verbatim when the end is open; else null |
| rolling | list date range | `No end date` → True; else null |
| summary | program `Short Description`, else `Objective` | native only; GMS null |
| eligibility_text | program page | `Eligible applicants: Government Organizations; ...` then `Applicant eligibility: <text>`; native only |
| eligibility_structured | program page | `{"eligible_applicants": [...], "subject_area": "..."}` when present |
| applicant_types | program page | see decision 2 |
| categories | program `Subject Area` | see decision 3; GMS none |
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
answers with a date range whose end has passed, the status is `closed` with that end date. GMS rows and unreadable
pages: `unknown`. A round that comes back resumes with its dates.

### Change detection

The hash is over the Program. Nothing volatile is stored: the pages carry a posted date but no modified stamp, and the
posted date is not mapped. Attachments and contact names stay in the payload.

## Decisions (defaults; override at review)

1. **The GMS rows come from the list alone.** Thin but honest: a title, an agency, a date range and an award range are
   all the state's own list says. Reading the 84 AmpliFund pages is a separate vendor host (no robots rules) and 84
   more requests; revisit after the first page is read by a person.
2. **`Government Organizations` and `Education Organizations` and `Other` tag nothing; the free text decides.** The
   pa_grants and ca_grants rule: `Government Organizations` covers state agencies, local governments, tribes and
   districts alike (23 of 33 programs carry it). `Nonprofit Organizations` → nonprofit, `For-Profit Organizations` and
   `Small Businesses` → business, `Individuals` → individual, `Public Housing Organizations` → housing_authority.
   `Applicant Eligibility` goes through the shared keyword tagger (fifth reuse). The tagger does not know `villages` or
   `townships`, so "cities, villages, townships and counties" tags municipality and county from `cities` and `counties`;
   the rest rides on the data-cleanup item below.
3. **Subject Area maps by the portal's word, once per program.** Economic Development → infrastructure (the pa.gov
   "Community & Economic Development" rule), Public Safety → public_safety, Human Services → health; Government
   Services, Education, and "Quality of Natural, Cultural, and Environmental Resources" (a mix of parks, water and arts)
   → other. The portal's text is the `source_code`.
4. **`No end date` is rolling and keeps its words in `closes_at_text`.** The state's "General announcement open for a
   period of time" is the same claim; it lands in the between-rounds group only if the round leaves and comes back.
5. **Native detail pages are fetched, GMS pages are not.** One rule, one reason: the native pages are on the same host
   as the list the state publishes.

## Known gaps (the source's wording, not the parser's)

- 60 of 84 GMS rows are DNR (parks, trails, conservation); a town cannot be matched to them from the list. If DNR's
  rounds matter to the Illinois page, read the AmpliFund pages for them in a follow-up.
- `Government Organizations` alone gives a program no municipal tag. 23 of the 35 native rounds carry it; 13 of those
  get no municipal or county tag, because their free text is `N/A`, `SEE NOFO` or names no unit of government. Several
  are plausibly town programs (Downstate Transit Improvement Fund, Transportation Alternatives for large MPOs, Regional
  Site Readiness, Redeploy Illinois, Lead Service Line Inventory), and the source does not say so; they stay off the
  town view until it does (reading each round's NOFO attachment is out of scope).
- The shared tagger does not match `villages`, `townships` or `city` (the same gap as California's).

## Out of scope

- The program list (`ProgramList.aspx`, 1,562 programs) and the awards: programs are the catalog (ALN's analogue), not
  rounds. A later session may read them like the SAM catalog.
- Attachments (`FileView.aspx`) and the mailing list.

## Verification

- `tests/test_il_csfa.py` against `tests/fixtures/il_csfa/` (the list trimmed to a dozen rows, three opportunity pages,
  two program pages and the agency table, saved by `scripts/probe_il_csfa.py`): both row shapes, `No end date`, award
  range and `Not Applicable`, the eligibility maps, the agency lookup, status by date, `resolve_missing`.
- Two live runs: all added, then 0 changed.
