# New York SFS Grant Opportunity Portal connector (`ny_sfs`): source, raw data and field mapping

Milestone 9, connector 8. Written 2026-11-03 from the 50-state census (`docs/surveys/state_portals.md`), which had recorded
the portal as "a JS shell; deeper look", before the parser. The deeper look found that the portal renders its whole
search grid and every abstract page server-side: no JavaScript has to run, only ordinary HTTP form posts, so the stop rule
in CLAUDE.md does not apply and the census entry is corrected below.

## Implemented (2026-11-03, same day)

`connectors/ny_sfs.py` follows this doc. First live run on a fresh database: 257 records added in 54 seconds (32 open,
225 closed; 256 grants, 1 loan by title keyword), 0 errors; 66 requests. Second run: 0 changed, 0 missing. Third run,
after Saj chose the profile reading of `Governmental Entity` (decision 2): 7 changed (`applicant_types` only), and **the
New York page shows 4 open municipal rows, all `likely`** (Farmland Protection Implementation Grants round 20, ERPO
Infrastructure and Implementation, Municipal Waste Reduction and Recycling 2024, Drinking Water Fluoridation) and 0
between rounds. 31 of the 32 open rows carry an applicant tag; the profile reading added municipality to 4 rows, county to
3 (one of them `2027 TYCLF`, from "County and Local Fairs") and school to 1. Fourth reading (10.3, the same day): a
profile with no sentence in it is a title and tags nothing, so `2027 TYCLF` loses its wrong county, Regional School
Food Infrastructure its school and Municipal Waste Reduction and Recycling 2024 its municipal: **3 open municipal rows**
(Farmland Protection, ERPO, Drinking Water Fluoridation). 20 of 32 open rows link to an agency announcement page, 12 to the
portal. 43 of the 225 closed rows have no agency name (12 codes never seen on an open abstract). Found while writing it:
the closed grid lists the Department of Labor's `OSH TE` three times (the 2025-2026, 2026-2027 and a second 2026-2027
round) under one Event ID, so the key keeps the first in grid order and two closed rounds are not recorded (decision 9).

## The source

New York's grants page, `https://grantsmanagement.ny.gov/search-funding-sfs`, says: "Anyone can access the Grant
Opportunity Portal. A username and password are not necessary to view anticipated and available grant opportunities."
Its "Find Grant Opportunities" button leads to one PeopleSoft component on the Statewide Financial System (SFS) supplier
portal:

```
https://esupplier.sfs.ny.gov/psp/fscm/SUPPLIER/ERP/c/NY_SUPPUB_FL.AUC_RESP_INQ_AUC.GBL     (the framed page the state links)
https://esupplier.sfs.ny.gov/psc/fscm/SUPPLIER/ERP/c/NY_SUPPUB_FL.AUC_RESP_INQ_AUC.GBL     (the content frame; what the connector reads)
```

A plain GET of the `psc` URL creates an anonymous session (cookies, no login) and answers the search page with the
default search already run: **Status = "Anticipated and Available"**, every agency, every eligibility, every service
area. On 2026-11-03 that was 32 rows, all in the HTML (`1-32 of 32`, one page). `robots.txt` on `esupplier.sfs.ny.gov`
is a 404 (no restrictions); on `grantsmanagement.ny.gov` it is the standard Drupal file.

Everything after the first GET is a PeopleSoft form submit: the page's `<form name='win0'>` posted back to the same URL
with `ICAction` naming the control that was "clicked", plus the page's `ICSID` (session id) and `ICStateNum` (a counter
that each response advances). The browser's JavaScript does nothing but fill those fields; the connector fills them
itself. Three actions are used:

| Action | What it does | Answer |
|---|---|---|
| `AUC_NAME_LNK$<n>` | opens row `n`'s abstract ("Grant Abstract" page) | a full HTML page |
| `NY_GG_SRCH_WRK_RETURN_PB` | "Return to Search", back to the same result grid | an XML partial response, the grid inside `<![CDATA[ ]]>` |
| `RESP_INQA_WK_INQ_AUC_GO_PB` with `NY_AUC_INQ_WRK_NY_GG_PORT_STATUS=C` | the Search button with Status = Closed | a full HTML page: 227 rows on 2026-11-03, one page |

Either answer shape carries the next `ICStateNum` (as a hidden input, or as `ICStateNum.value=<n>` in the onload
script) and the grid rows use the same ids, so the connector unwraps the CDATA sections of an XML answer and parses the
result as HTML. A run is: 1 GET, then 2 posts per open row (abstract, return), then 1 post for the closed search: about
66 requests, 0.3 s apart, under a minute.

Not read: the "View Grant Opportunity" button (it opens either the announcement link below or a session-signed PDF of
the RFP on the SFS host, in a new window; the PDF's URL is not stable), the Funding Agency lookup prompt, the email
notification sign-up, the "Log into SFS and Apply" button.

### The grid

Every row is a `<tr>` whose cells carry fixed element ids with the row number after `$`. Row 0 on 2026-11-03:

```html
<span id='AUC_ID_COL$span$0' class='PSHYPERLINKDISABLED' title='Event ID'>AFTYP3</span>
<span class='PSEDITBOX_DISPONLY' id='NY_AUC_INQ1_WRK_BUSINESS_UNIT$0'>AGM01</span>
<a name='AUC_NAME_LNK$0' id='AUC_NAME_LNK$0' href="javascript:submitAction_win0(document.win0,'AUC_NAME_LNK$0');">2027 TYCLF</a>
<span class='PSDROPDOWNLIST_DISPONLY' id='NY_AUC_INQ1_WRK_NY_GG_PORT_STATUS$0'>Available</span>
<span class='PSLONGEDITBOX' id='NY_AUC_INQ1_WRK_FIELDLIST$0'>Governmental Entity, Not-For-Profit, Tribal Organization</span>
<span class='PSEDITBOX_DISPONLY' id='RESP_INQA1_WK_AUC_DTTM_PREVIEW$0'>10/02/26 10:10AM</span>      <!-- Availability Date -->
<span class='PSEDITBOX_DISPONLY' id='RESP_INQA1_WK_AUC_DTTM_START$0'>10/08/26 10:10AM</span>        <!-- Anticipated Release Date -->
<span class='PSEDITBOX_DISPONLY' id='RESP_INQA1_WK_AUC_DTTM_FINISH$0'>12/01/2026&nbsp; 4:00PM EST</span>  <!-- Due Date -->
```

Column headers: Event ID, Funding Agency (a five-character business-unit code), Grant Opportunity, Status, Eligibility,
Availability Date, Anticipated Release Date, Due Date. The Grant Opportunity cell is a link (`<a name='AUC_NAME_LNK$n'>`)
on every open row and on 9 of the 227 closed rows; the other closed rows show the title in a disabled span, and there
is no abstract to open for them. **The Event ID is not unique across agencies** (`EVT0000010` is a DCJS round and an
OASAS round), so the record key is the agency code plus the Event ID. One Event ID repeats inside one agency (`DOL01` /
`OSH TE`, three closed rounds of one program); the first row in grid order is kept (decision 9).

What the grids held on 2026-11-03:

| | Open search (default) | Closed search |
|---|---|---|
| rows | 32 | 227 |
| Status values | `Available` 25, `Advertised Only - Not in SFS` 7 (no `Anticipated` row that day) | `Closed` 227 |
| agencies | 10 codes | 22 codes |
| Eligibility | `Governmental Entity, Not-For-Profit, Tribal Organization` 15; `Not-For-Profit` 7; `For Profit, Governmental Entity, Not-For-Profit` 4; `Governmental Entity, Not-For-Profit` 3; `Governmental Entity` 2; `Governmental Entity, Tribal Organization` 1 | 61 `Governmental Entity, Not-For-Profit`, 59 with Tribal Organization added, 53 `Not-For-Profit`, 14 `Governmental Entity`, the rest mixes of the five labels including `Individual` |
| dates | every row has all three; Availability and Release as `MM/DD/YY H:MMAM`, Due as `MM/DD/YYYY H:MMPM EST` | the same; due dates from 2024-03 to 2026-10 |
| title length | 4 at the 50-character limit (`Grief Support Toolkit for People with Developmenta`) | 32 at the limit |

The five eligibility labels are the portal's own search vocabulary: Not-For-Profit, For Profit, Governmental Entity,
Tribal Organization, Individual. A row says no more about who may apply than those words.

### The abstract

`AUC_NAME_LNK$n` answers the "Grant Abstract" page. Values sit in spans with fixed ids; labels are spans beside them.
Row 0 on 2026-11-03 (contact name and email elided):

| Label | Element id | Value |
|---|---|---|
| Grant Opportunity ID | `NY_GG_ABSTRT_VW_AUC_ID` | `AFTYP3` |
| Agency | `NY_GG_ABSTRT_VW_DESCR1` | `AGRICULTURE & MARKETS` |
| Grant Opportunity | `NY_GG_ABSTRT_VW_AUC_NAME` | `2027 TYCLF` |
| Contact Name / Contact Email | `NY_GG_ABSTRT_VW_OPRID`, a `mailto:` link | a named person; not stored |
| Solicitation Profile | `NY_GG_ABSTRT_VW_DESCRLONG2` | `2027 Transportation for Youth to County and Local Fairs` |
| Announcement Link | the `<a href>` before the label | `https://agriculture.ny.gov/funding-opportunities` |
| Applications Due (Date / Time) | `NY_GG_ABSTRT_VW_DATETIMESTRING` | `December 1, 2026 / 04:00 PM` |
| Bidder's Conference(s)/Application Workshop(s) | `NY_GG_ABSTRT_VW_DESCR254` | free text; a URL, a date, `N/A` or empty |
| Anticipated Award Date | `NY_GG_ABSTRT_VW_DATE_STRING2` | `Monday, March 01, 2027` (empty on 11 of 32) |
| Anticipated Initial Contract Length | `NY_GG_ABSTRT_VW_STRING_TEXT` | `0 Month(s)` to `60 Month(s)` |
| Total Funding Available | `NY_GG_ABSTRT_VW_FUNDED_AMT` | `$475,000.000` (three decimals, on all 32) |
| Letter of Intent Narrative / Due | `NY_GG_ABSTRT_VW_DESCRLONG` | `N/A` on 27 of 32 |
| Questions Due Date | `NY_GG_ABSTRT_VW_DATE_STRING1` | `Wednesday, November 04, 2026` |
| Questions and Answers Narrative / Posting Type / Posting Date / Link | `..._DESCRLONG1`, `..._NY_GG_POST_TYPE`, `..._DATE_STRING`, an `<a href>` | free text; `Link` 18, `Upload` 12, empty 2 |
| Eligible Applicants | `NY_GG_SRCH_WRK_LONGVALUE` | the same labels as the grid |
| Service Areas(s) | `NY_GG_SRCH_WRK_DESCRLONG` | `Agricultural Supports, Education Supports, Family Supports, Public Transportation Services` |

The Solicitation Profile is the only prose: 28 to 4,564 characters, a full title on the short ones and a description
on the long ones. The service areas are the portal's twelve labels (Agricultural, Education, Environmental, Family,
Government, Health, Housing and Shelter, Justice, Public Safety, Public Transportation, Workforce). Agency names are
PeopleSoft short descriptions (`Off of Children & Family Serv`, `St Cncl on Development Dsblty`) and are the only place
the portal names an agency; the grid shows the code.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `ny_sfs` |
| source_id | grid Funding Agency + Event ID | `<code>-<event id>`, whitespace in the Event ID replaced by `-` (`AGM01-AFTYP3`, `CFS01-RFA-1278`); the raw parts stay in the payload |
| source_url | abstract Announcement Link | the link when it is an `http(s)` URL with a host; else the portal page the state links (the `psp` URL above). Decision 3 |
| external_number | grid Event ID | verbatim (`RFA 1278`) |
| name | grid Grant Opportunity | the link text, whitespace collapsed; at most 50 characters because the source truncates there |
| level / jurisdiction | constant | `state` / `NY` |
| administering_agency | abstract Agency | the short description; for a closed row (no abstract) the name recorded for that code from the abstracts read this run, then from the table in the connector (the ten codes seen on 2026-11-03); else null |
| agency_code | grid Funding Agency | `AGM01` |
| funding_type | name, then constant | the shared `funding_type_for` keyword; else `grant`. Decision 5 |
| funding_source | none | `direct`: the portal makes no claim about whose money it is |
| amount_min / amount_max | none | null: Total Funding Available is a program total |
| match_required / match_pct | none | null |
| status | grid Status | see status rules |
| opens_at | grid Anticipated Release Date | the date part |
| closes_at | grid Due Date | the date part |
| closes_at_text | a date cell that is not a date | verbatim; none seen |
| rolling | none | null: every row has a due date |
| summary | abstract Solicitation Profile | whole text, whitespace collapsed; null for a closed row |
| eligibility_text | grid Eligibility | the labels as written |
| eligibility_structured | grid and abstract | `portal_status` (the grid's word, always), `posted_at` (Availability Date), `total_funding`, `contract_length`, `anticipated_award_date`, `questions_due` (dates ISO when they parse, else verbatim); keys only when the source has a value |
| applicant_types | grid Eligibility, then the abstract Solicitation Profile | each label through the shared `portal_applicant` table: Not-For-Profit → nonprofit, For Profit → business, Tribal Organization → tribe, Individual → individual, Governmental Entity → nothing by itself; **a row labelled Governmental Entity also has its Solicitation Profile read sentence by sentence** (negated sentences dropped) through the shared tagger, keeping only the governmental kinds (municipality, county, state, school, special_district, housing_authority, higher_ed), the matched phrase as source_code. Decision 2 |
| categories | abstract Service Areas | each label through the shared `portal_categories` table (Health Services → health, Housing and Shelter Services → housing, Workforce Development → workforce, Public Safety Supports and Justice Services → public_safety, Public Transportation Services → transportation; the other six → other), the label kept as source_code; none for a closed row |
| alns | none | always empty |

### Status rules

The grid labels every row. The label is the status; dates are not consulted.

| Grid Status | Status |
|---|---|
| `Available` | open |
| `Advertised Only - Not in SFS` | open (the round is open; applications go to the agency, not through SFS; the word is kept in `eligibility_structured.portal_status`) |
| `Anticipated` | forecasted |
| `Closed` | closed |
| anything else | unknown |

The open views already drop a row whose `closes_at` has passed (SPEC, status semantics), so an `Available` row the agency
forgot to close falls off the open page on its own.

### What happens when a round leaves

Both grids are read in full every run, so a round that closes is seen again as `Closed` and updated in the ordinary way.
`resolve_missing(source_id)` returns `unknown` without a request: a key on neither grid was taken down, which the source
does not state as a closure, and there is no per-record URL to read back.

### Change detection

The hash is over the Program. The grid carries no modified stamp; the abstract of every open row is read every run.

## Decisions (defaults; override at review)

1. **This is not a browser workaround.** The page's JavaScript only fills `ICAction`, `ICSID` and `ICStateNum` into a form
   and submits it; the connector sends the same form. Nothing is executed, no headless browser is involved, and the
   state says the portal is public. The census is corrected from "JS shell" to "server-rendered behind form posts".
2. **`Governmental Entity` tags nothing by itself; a row that carries it has its Solicitation Profile read for the
   governmental applicants it names** (Saj's decision, 2026-11-03, after the first build tagged nothing). The label is
   the same breadth as pa.gov's `Public Agency`, California's `Other Legal Entity` and Illinois's `Government
   Organizations` (decision 2026-10-28): state departments, authorities, school districts, counties and towns alike, and
   the portal has no eligibility prose to settle it; the profile is the only prose it has. So the Texas rule runs on the
   profile, sentence by sentence with negated sentences dropped, but only for rows the portal itself says are open to a
   governmental entity, and only for the governmental kinds the label can mean: a `residents` or `individuals` found in
   a description is a beneficiary, and nonprofit, business and tribe are the portal's own labels to give. The reading
   was rejected for WebGrants (descriptions tag incidental text); it is accepted here because the scope is narrow and
   every tag names its phrase. What it does on 2026-11-03: 7 of the 25 labelled rows gain a governmental tag, 4 of them
   municipality; the other 18 (the DEC forest and river rounds, the CDD rounds, the OMH crisis programs) have profiles
   that name no applicant and stay off the municipal page. A profile with no sentence in it is the round's title
   ("2027 Transportation for Youth to County and Local Fairs", "Municipal Waste Reduction and Recycling Program 2024")
   and tags nothing (10.3): a name says what the money is for, not who applies, and the county fair is not a county.
   The cost is Municipal Waste Reduction and Recycling 2024, a municipal program by its name that the labels and the
   profile never state, off the municipal page. Read the `Governmental Entity` rows that gained nothing before trusting
   a town's page.
3. **The announcement link is the record's URL.** The portal has no per-record address (every page is one PeopleSoft
   URL plus session state), and the Announcement Link is the agency's own page for the round, the thing a reader opens
   next. 20 of 32 abstracts carry a usable one; the rest, and every closed row, link to the portal search page. A link
   that is not a URL (`https://https://cdd.ny.gov/...` on one abstract) is left out and the portal page used.
4. **The contact name and email are dropped before the payload is stored**, as `webgrants` and `nj_dca_sage` do: the
   database is published, and the abstract names a person.
5. **Every row is a grant unless its title says otherwise.** The portal is the Grant Opportunity Portal and the state's
   page calls its rows "grant funding opportunities"; the shared title keyword still wins where it fires (`loan`, `tax
   credit`, `voucher`).
6. **Total Funding Available is kept as the source's words** (`$67,000,000.000`), never read as an award: the Texas rule.
7. **A failure anywhere aborts the run.** A list page without the search form, a closed search with no rows, an abstract
   whose Grant Opportunity ID is not the row's Event ID, or a request that fails after three tries on a dropped
   connection (an HTTP error status is not retried). A partial read would mark every unread round `unknown` or flip
   summaries to null; the safe direction is no run at all. Under `--limit` the closed search is skipped (the missing
   check is skipped too).
8. **Closed rows are read from the grid alone and kept.** 9 of 227 have an abstract link and the rest none; reading
   none keeps every closed record the same shape. They are the between-rounds history (the same DEC, DOH and OTDA
   rounds recur), and it is one request.
9. **The key is the agency code plus the Event ID, and a repeated key keeps the first row.** The Event ID alone repeats
   across agencies; inside one agency it repeated once on the survey day (DOL's `OSH TE`, three closed rounds), which
   costs two closed rows of one program. A due-date suffix would make every such key depend on grid order; not worth it
   for one case. Revisit if a second agency does the same.

## Known gaps (the source's wording, not the parser's)

- 18 of the 25 open rows labelled `Governmental Entity` have a Solicitation Profile that names no applicant, so they
  carry no governmental tag and stay off the municipal page (decision 2); a title-only profile tags nothing, which keeps
  Municipal Waste Reduction and Recycling 2024 off it too.
- Titles are cut at 50 characters by the source (`Municipal Waste Reduction and Rcycling. Prgrm. 24`); the Solicitation
  Profile often carries the full name, but it is a description on other rows, so the name stays the grid's.
- Closed rows have no agency name unless the code was seen on an open abstract (10 of 22 codes on 2026-11-03), no
  summary and no service areas.
- `Environmental Supports`, `Agricultural Supports`, `Education Supports`, `Family Supports` and `Government Supports`
  map to `other`: none names one of our categories.
- No `Anticipated` row was listed on the survey day, so the forecasted branch is exercised by the fixture only.
- Two of DOL's three closed `OSH TE` rounds are not recorded (decision 9).

## Out of scope

The RFP documents behind "View Grant Opportunity"; the agency lookup prompt (agency names come from the abstracts); the
email notification service; the 212 closed rows' abstracts; the per-agency funding pages the announcement links lead to.

## Verification

- `tests/test_ny_sfs.py` against `tests/fixtures/ny_sfs/` (a trimmed search page, a trimmed XML return answer, a
  trimmed closed page and four abstracts, written by `scripts/probe_ny_sfs.py`; scripts removed, session ids and the
  contact name and email replaced by placeholders): grid parsing from HTML and from CDATA, state tracking, abstract
  parsing, every status label, the applicant and category tables, the key, the URL rule, structured fields, `fetch`
  through a stub post (the id check, the abort rules, `limit`), `resolve_missing`.
- Two live runs: all added, then 0 changed.
