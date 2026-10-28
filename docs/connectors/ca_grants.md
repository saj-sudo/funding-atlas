# California Grants Portal connector (`ca_grants`): source, raw data and field mapping

Milestone 9, connector 3. Written 2026-10-27 from the 50-state census (`docs/surveys/state_portals.md`), before the
parser. The first source that is a file: one CSV, no HTML, no API.

## Implemented (2026-10-27, same day)

`connectors/ca_grants.py` follows this doc. First live run on a fresh database: 2,025 records added in five seconds
(164 open, 3 forecasted, 1,858 closed; 127 rolling; 1,949 grants and 76 loans; 466 pass-through), 0 errors. Second
run: 0 changed, 0 missing. On the California page: 28 open municipal rows (all likely tier) from 73 agencies, and 52
between rounds. Spot-checked against the agencies' pages: the LWCF deadline (2027-01-14, parks.ca.gov) and the Trade
Corridor Enhancement Program deadline (2026-11-20, catc.ca.gov) match.

## The source

The California Grants Portal (`https://www.grants.ca.gov/`, WordPress) is run by the State Library under the Grant
Information Act of 2018 (AB 2252): every state agency posts its competitive grants there. The portal publishes its whole
catalog as an open-data CSV on the state's CKAN, dataset `california-grants-portal`, resource "California Grants Portal -
Updated Daily CSV" (id `111c8c88-21f6-453c-ae2c-b4785a0624f5`). The CKAN record said `last_modified
2026-10-27T08:01:34`; the file is rebuilt every morning.

Download URL, the one the connector uses:

```
https://data.ca.gov/dataset/california-grants-portal/resource/111c8c88-21f6-453c-ae2c-b4785a0624f5/download/california-grants-portal-data.csv
```

It answers 302 to a signed Cloudflare R2 URL that expires in 60 seconds; `httpx` follows it. 6.6 MB, one request a
run.

`robots.txt`: `data.ca.gov` disallows `/api/`, `/search?`, `/datastore/` and `/user/`, and allows the rest; so the
connector does **not** look the resource up through `package_show` each run (the plan's first idea) and uses the
dataset download path, which is allowed. `www.grants.ca.gov` allows everything (Yoast default). `publish.data.ca.gov`
disallows `/api/` too.

The resource id is fixed in the code. If the state ever replaces the resource, the download answers 404 and the run
fails loudly; that beats a quiet lookup through a disallowed path.

### Shape

2,025 rows on 2026-10-27, 36 columns, UTF-8 with a byte-order mark on the first header (`﻿PortalID`; read with
`utf-8-sig`). Multi-valued cells are `; `-separated. Dates are `YYYY-MM-DD HH:MM:SS` in Pacific time, or text.

`PortalID, GrantID, Status, LastUpdated, ChangeNotes, AgencyDept, Title, Type, LOI, Categories, CategorySuggestion,
Purpose, Description, ApplicantType, ApplicantTypeNotes, Geography, FundingSource, FundingSourceNotes, MatchingFunds,
MatchingFundsNotes, EstAvailFunds, EstAwards, EstAmounts, FundingMethod, FundingMethodNotes, OpenDate,
ApplicationDeadline, AwardPeriod, ExpAwardDate, ElecSubmission, GrantURL, AgencyURL, AgencySubscribeURL,
GrantEventsURL, ContactInfo, AwardStats`

### One row (trimmed)

```
PortalID: 194175
GrantID: (empty)
Status: active
LastUpdated: 2026-10-23 23:05:13
ChangeNotes: Made minor revisions to spacing.
AgencyDept: Department of Parks and Recreation
Title: Land and Water Conservation Fund (LWCF)
Type: Grant
Categories: Parks & Recreation
Purpose: The Land and Water Conservation Fund (LWCF) was established by Congress in 1964 ...
Description: Eligible Local and Non-State Agencies: · Cities and counties · Federally recognized Native American tribes ...
ApplicantType: Public Agency; Tribal Government
ApplicantTypeNotes: Cities & counties Federally recognized Native American tribes Joint Powers Authorities (JPA) where all members are public agencies. ...
FundingSource: Federal
MatchingFunds: 50%
EstAvailFunds: $27,500,000.00
EstAmounts: Dependant on number of submissions received, application process, etc.
FundingMethod: Reimbursement(s)
OpenDate: 2026-10-23 22:31:00
ApplicationDeadline: 2027-01-14 23:59:00
GrantURL: https://www.parks.ca.gov/?page_id=21360
ContactInfo: email: localservices@parks.ca.gov; tel: 1-916-653-7423;
```

### What the file held on 2026-10-27

| Column | Values |
|---|---|
| `Status` | closed 1,858, active 164, forecasted 3 |
| `PortalID` | 2,025 distinct, never empty: the record key |
| `GrantID` | empty on 1,551; otherwise an agency label (`CEG`, `CA Department of Food and Agriculture`) shared across rounds, not a number |
| `Type` | Grant 1,900, Loan 76, `Grant; Loan` 49 |
| `ApplicantType` | Public Agency 1,600, Nonprofit 1,341, Tribal Government 982, Business 487, Individual 374, Other Legal Entity 152 (rows can carry several) |
| `ApplicantTypeNotes` | free text naming the real applicants; empty on 56 of the 164 active rows |
| `FundingSource` | State 1,489, Federal 382, Federal and State 84, Other 68 |
| `MatchingFunds` | Not Required 1,563, otherwise one percentage (`25%`, `50%`, ...) |
| `EstAmounts` | `Dependant on number of submissions received, ...` 1,213; `Between $X and $Y` 658; one amount 154 |
| `OpenDate` | a timestamp, except on the three forecasted rows: `Fall 2026`, `2027`, `October 2026` |
| `ApplicationDeadline` | a timestamp; `Ongoing` on 127 rows, all of them active; empty on 3 |
| `Categories` | 18 values: Environment & Water 771, Disadvantaged Communities 689, Education 456, Health & Human Services 425, Housing, Community and Economic Development 327, Parks & Recreation 276, Employment, Labor & Training 253, Agriculture 235, Energy 208, Science, Technology, and Research & Development 195, Disaster Prevention & Relief 179, Law, Justice, and Legal Services 164, Libraries and Arts 135, Transportation 127, Food & Nutrition 114, Consumer Protection 50, Animal Services 25, Veterans & Military 20 |
| `GrantURL` | present on every row |

No active row has a deadline in the past: the portal closes rounds itself.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `ca_grants` |
| source_id | `PortalID` | as a string |
| source_url | `GrantURL` | verbatim (the agency's page for the grant) |
| external_number | `GrantID` | when present, else null |
| name | `Title` | whitespace collapsed |
| level / jurisdiction | constant | `state` / `CA` |
| administering_agency | `AgencyDept` | verbatim |
| agency_code | none | null |
| funding_type | `Type` | first `;` token: `Grant` → grant, `Loan` → loan (the pa_grants rule); else null |
| funding_source | `FundingSource` | contains `Federal` → `pass_through`; else `direct` (the pa_grants rule) |
| amount_min / amount_max | `EstAmounts` | `Between $X and $Y` → X and Y; one amount → both; the "Dependant on ..." text → null |
| match_required / match_pct | `MatchingFunds` | `Not Required` → False; one percentage → True and the number; else null |
| status | `Status` | see status rules |
| opens_at / closes_at | `OpenDate` / `ApplicationDeadline` | the date part of the timestamp; text → null |
| closes_at_text | `ApplicationDeadline`, `OpenDate` | deadline text that is not a date (`Ongoing`) verbatim; open-date text that is not a date as `Opens: Fall 2026`; both joined with `; `; else null |
| rolling | `ApplicationDeadline` | `Ongoing` (or rolling / continuous) → True; else null |
| summary | `Purpose`, else `Description` | HTML stripped, whitespace collapsed |
| eligibility_text | `ApplicantType`, `ApplicantTypeNotes`, `Geography` | one labelled line each when present (`Applicant type: ...`), the pa_grants shape |
| eligibility_structured | `LOI`, `FundingMethod` | `{"loi_required": true, "funding_method": "Reimbursement(s)"}`, keys only when the cell is non-empty |
| applicant_types | `ApplicantType`, `ApplicantTypeNotes` | see decision 2 |
| categories | `Categories` | per token, see decision 4; `source_code` = the portal's category |
| alns | none | always empty (the CSV carries no ALN) |

### Status rules

| `Status` | Status | Note |
|---|---|---|
| `active` | open | the portal's own label |
| `forecasted` | forecasted | |
| `closed` | closed | |
| anything else | unknown | none on the day |

No date overrides. The portal closes rounds itself and no active row was past its deadline on the day; the pa_grants
"closed with a future open date" rule has nothing to act on because forecasted is labelled here.

### Change detection

The hash is over the Program, so `LastUpdated`, `ChangeNotes`, `ContactInfo`, the URLs other than `GrantURL` and the
award statistics live in the stored payload and never count as a change. `ChangeNotes` is often "Made minor revisions
to spacing", which is why.

`resolve_missing`: a row is missing only if it left the file, and closed rounds stay in the file (1,858 of them), so
leaving it is a removal the source did not explain: `unknown`, the wv_grants rule. The file fetched in the same run is
reused; if the process has none, the connector reads the file once more.

## Decisions (defaults; override at review)

1. **The download path, not the CKAN API.** `data.ca.gov/robots.txt` disallows `/api/`; the dataset download path is
   allowed and stable. The resource id is a constant.
2. **`Public Agency` and `Other Legal Entity` tag nothing; the notes decide.** The pa_grants decision 2 rule: Public
   Agency covers state departments, special districts, JPAs, cities and counties alike, and 149 of the 164 active rows
   carry it. `Nonprofit` → nonprofit, `Tribal Government` → tribe, `Business` → business, `Individual` → individual;
   `ApplicantTypeNotes` goes through the shared keyword tagger (`connectors/text.py`). On the day that tags 28 of the 164 active rows `municipality` and 40 `county`. Not `Description`: it mixes
   eligibility with project rules and place names, and the tagger is built for who-may-apply lines.
3. **One estimated amount is both the minimum and the maximum.** `EstAmounts` is the estimated award size; a single
   figure is the source's one number for it, not a ceiling. Total funds (`EstAvailFunds`) are not an award size and
   stay in the payload.
4. **Categories by the portal's own vocabulary.** Environment & Water → water; Energy → energy; Transportation →
   transportation; Parks & Recreation → parks; Health & Human Services → health; Employment, Labor & Training →
   workforce; Housing, Community and Economic Development → **housing and infrastructure** (changed 2026-10-28: the label
   names two topics, and pa.gov's "Community & Economic Development" and Illinois's "Economic Development" are
   infrastructure; the table is shared in `connectors/text.py`); Law, Justice, and Legal Services and Disaster
   Prevention & Relief → public_safety; everything else (Disadvantaged Communities, Education, Agriculture, Libraries
   and Arts, ...) → other, with the portal's word as `source_code` so SQL can redo the map.
5. **Forecasted open text is kept as text.** `Fall 2026` is not a date; it goes to `closes_at_text` as `Opens: Fall
   2026` and `opens_at` stays null. The status is the portal's label, not derived from the text.

## Known gaps (the source's wording, not the parser's)

- 56 active rows have no `ApplicantTypeNotes`; when their `ApplicantType` is only Public Agency they carry no applicant
  tag and stay off the municipal views, by decision 2.
- Fixed 2026-10-28: the shared tagger now matches `city`, `village`, `township`, `borough` and `local jurisdiction`
  ("a city, county, or city and county" tagged `county` only before). On the stored file that moved 378 California
  records (73 from the tagger, the rest from the housing and infrastructure label) and lifted the California page's open
  municipal rows from 28 to 39.

## Out of scope

- The award datasets (`california-grants-portal-grant-awards-*`, one per fiscal year): recipients, not programs.
- `CategorySuggestion`, `AwardStats`, `ElecSubmission`, `AgencySubscribeURL`, `GrantEventsURL`: stored, not mapped.

## Verification

- `tests/test_ca_grants.py` against `tests/fixtures/ca_grants/grants_sample.csv` (rows chosen by
  `scripts/probe_ca_grants.py`): BOM header, each status, `Ongoing`, a forecasted text open date, a range, a single
  amount, a match percentage, the Public Agency rule, the notes tagger, the category map, `resolve_missing`.
- Two live runs: all added, then 0 changed.
