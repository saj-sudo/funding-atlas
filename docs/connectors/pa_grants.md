# pa.gov grants index connector (`pa_grants`): source, raw data and field mapping

Milestone 9, connector 1. Written 2026-10-17 from the Mid-Atlantic survey (`docs/surveys/mid_atlantic.md`), before the
parser, per CLAUDE.md: URL, a sample of the raw data, the field mapping. The first state connector outside Maryland
and the first fed by a search index rather than by agency pages.

## Implemented (2026-10-17, same day)

`connectors/pa_grants.py` follows this doc. First live run on a fresh database: 377 records added in 9 m 33 s (84 open,
2 forecasted, 291 closed; 314 grants, 20 loans, 16 tax credits, 13 other, 14 with no stated type; 82 pass-through), 0
errors, every detail page readable. The second run, ten minutes later: 0 changed, 0 missing. On the Pennsylvania page
(`v_navigator_program WHERE state='PA'`): 29 open rows (26 likely, 3 possible), every open municipality-tagged record,
and 68 between rounds. The predicted 22 became 29 because the free-text applicant line tags municipalities the
category field does not (`Municipalities` in `applicantType` on records whose `applicantCategory` says only `Public
Agency`).

Known gaps, because the record does not say it: 83 records carry no applicant tag at all (`applicantCategory` is
`Public Agency`, `Other Legal Entity` or empty, and the free-text line names nothing in the keyword map); 14 records
have no funding type; 17 of the 29 open municipal rows close on a placeholder date (`2035-12-31`, `2999-07-01`) and
read as "closes 2035" on the page, which is the source's wording for no deadline. A display rule for placeholder dates
is a navigator decision, not a connector one.

## The source

Pennsylvania's "Discover State Grants" portal, `https://www.pa.gov/grants`, is an Adobe Experience Manager site whose
grant list is a **Coveo** search index: organization `commonwealthofpennsylvaniaproductiono8jd9ckm`, search hub
`All Grants`, 377 grants from 17 agencies on the survey date. Each grant has a page at
`https://www.pa.gov/grants/search/grant-details/<agency>/<n>` (`pema/10`, `penndot/25`, `dced/51`) that embeds the
whole record as HTML-escaped JSON in `<div id="pageApiData" data-page-api-data="…">` and fills the visible template
(`${closeDate}`, `${eligibility}`) client-side. The connector reads the attribute, never the rendered text.

Applications go to `https://grants.pa.gov/` (the Commonwealth's Enterprise eGrants System, Keystone Login). That is a
login page and not read.

robots: `https://www.pa.gov/robots.txt` disallows three unrelated paths and states no crawl delay. The connector waits
0.3 s between detail pages (about 377 requests; the pages take about a second each, so a run is around ten minutes) and
0.5 s between search pages (four).

### Enumeration

```
POST https://platform.cloud.coveo.com/rest/search/v2
Authorization: Bearer <search key>
{"q": "", "searchHub": "All Grants", "numberOfResults": 100, "firstResult": 0, "sortCriteria": "copapwpclosedate ascending"}
```

`totalCount` is 377; paging by `firstResult` works (300 → 77 results). The search key is a public token that sits in
the search page's markup, `data-api-key="xx3f…"` on `https://www.pa.gov/grants/search`, and rotates when the site is
rebuilt, so it is read from that page at the start of every run and never hard-coded. If it is missing the run fails
loudly rather than guessing.

One result's `raw` fields, the part the payload keeps as `hit`:

```json
{"copapwppagetitle": "Hazard Mitigation Grant Program (HMGP)",
 "copapwpurl": "https://www.pa.gov/en/grants/search/grant-details/pema/10",
 "copapwpapplicationstatus": "Closed",
 "copapwpopendate": "1641038400000", "copapwpclosedate": "1648209600000",
 "copapwpapplicanttype": ["Municipality", " Public Agency"],
 "copapwpfundingagency": ["Emergency Management Agency"],
 "copapwpfundingtype": ["Grant"], "copapwpfundingsource": "Federal",
 "copapwpcategory": ["Community & economic development"], "copapwpgrantcycle": "Upon Disaster Declaration",
 "copapwpminimumaward": "", "copapwpmaximumaward": "",
 "copapwpshortdescription": "FEMA’s Hazard Mitigation Grant Program provides funding to state, local, tribal and territorial governments …"}
```

Facet counts on the survey date: `copapwpapplicationstatus` `Accepting applications` 84, `Closed` 293;
`copapwpapplicanttype` `Municipality` 132, `Public Agency` 81, `Nonprofit` 124, `School` 90, `Business` 98,
`Other Legal Entity` 116, `Individual` 28, `Native American Tribal Organization or Government` 20, plus a tail of
free-text strays; `copapwpfundingtype` `Grant` 315, `Loan` 22, `Tax credit` 16, `Reimbursement` 5,
`Disaster reimbursement` 3, `Fund` 2, `tax refund` 2, `Reimbursement agreement` 2, `Loan program` 1,
`Incentitive payment` 1; `copapwpfundingsource` `State` 189, `Federal` 75, `Commonwealth Financing Authority (CFA)` 21,
and nine free-text values. Over 100 sampled results `copapwpopendate`, `copapwpclosedate`, `copapwpapplicationstatus`,
`copapwpminimumaward`, `copapwpmaximumaward` were present on 100, `copapwpapplicanttype` on 71,
`copapwpmatchingrequirements` on 27.

### The detail record

`penndot/25`, open on the survey date (trimmed):

```json
{"slug": "penndot25", "last_modified": "2026-10-16T17:01:25Z",
 "title": "Multimodal Transportation Fund (MTF) Program", "status": "Accepting applications",
 "category": "Transportation", "issuingAgency": "Transportation", "shortIssuingAgency": "penndot",
 "issuingAgencyGrantNumber": "25.0",
 "openDate": "2026-09-14T12:00:00-00:00", "closeDate": "2026-10-30T12:00:00-00:00", "grantCycle": "Annual",
 "applicantType": "Municipalities; Councils of governments; Businesses; Economic development organizations; Public transportation agencies; Ports and rail freight …",
 "applicantCategory": "Municipality; Public Agency",
 "populationServedType": "Municipalities, councils of governments, businesses, …", "populationServedGeography": "Statewide ",
 "eligibility": "Multimodal Transportation Fund Success Manual (pa.gov)",
 "fundingType": "Grant ", "fundingSource": "State", "matchingFundsRequirements": "30% of the amount requested ",
 "totalFundsToBeAwarded": "40000000", "minimumAward": "", "maximumAward": "3000000", "anticipatedFunding": "$1 million per awardee ",
 "linkToApply": "https://grants.pa.gov/Login.aspx", "pointOfContact": "{'name': 'Dave Bratina    dabratina@pa.gov   717-705-1230 '}",
 "processSteps": [...], "additionalResources": [...], "FAQs": []}
```

`pema/10`, closed federal pass-through: `"status": "Closed"`, `"openDate": "2022-01-01T12:00:00-00:00"`,
`"closeDate": "2022-03-25T12:00:00-00:00"`, `"grantCycle": "Upon Disaster Declaration"`,
`"applicantType": "Cities; Townships; Counties; Special district governments; State agencies. "`,
`"applicantCategory": "Municipality; Public Agency"`,
`"eligibility": "https://www.fema.gov/grants/mitigation/hazard-mitigation/before-you-apply"` (a URL, not prose),
`"matchingFundsRequirements": "75% federal share\n25% local share"`, `"fundingSource": "Federal"`,
`"issuingAgencyGrantNumber": 10.0` (a number here, a string on `penndot/25`), `"pointOfContact": {"name": "…"}` (a
dict here, a stringified dict there).

Shapes seen and handled: `fundingType` can hold two values (`Grant; grant agreement`); dates can be placeholders
(`2035-12-31`, `2035-06-30`, `2999-07-01` on loans and recurring programs); a close date can precede the open date
(`pema/14` Public Assistance DR 4408: opens 2028-11-27, closes 2018-12-27); `closeDate` can be empty on an open
record (`pccd/63`); `Closed` records can carry a future `openDate` (`dmva/1` Veterans' Trust Fund opens 2026-11-02);
the same program can appear under two agencies (Multimodal Transportation Fund: `dced/51` closed, `penndot/25` open).

## Field mapping (Program model in `pipeline/models.py`)

The record is the detail JSON; when a detail page cannot be read, the hit's `copapwp*` fields stand in for `title`,
`status`, the dates (epoch ms), `fundingType`, `fundingSource`, `category`, `applicantCategory`, `grantCycle`, the award
bounds and the description, so a record never depends on one request.

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `pa_grants` |
| source_id | `copapwpurl` tail | `<agency>/<n>` with the number as an integer: `pema/10`, `dced/51` |
| source_url | constant + source_id | `https://www.pa.gov/grants/search/grant-details/<source_id>` |
| external_number | none | null (`issuingAgencyGrantNumber` is the portal's own index and already in `source_id`) |
| name | `title` | whitespace collapsed (`\xa0` included) |
| level / jurisdiction | constant | `state` / `PA` |
| administering_agency | `issuingAgency` | as the source says it ("Emergency Management Agency"); no "Pennsylvania" prefix is invented |
| agency_code | `shortIssuingAgency` | `PA-` + upper-case (`PA-PEMA`, `PA-DCED`) |
| funding_type | first `;`-separated token of `fundingType`, lower-cased | `grant` → grant; `loan`, `loan program` → loan; `tax credit`, `tax refund` → tax_credit; `reimbursement`, `reimbursement agreement`, `disaster reimbursement`, `fund`, `incentitive payment`, `incentive payment` → other; empty or unmapped → null |
| funding_source | `fundingSource` | contains `federal` (any case) → `pass_through`, else `direct` |
| alns | none | always empty: the record never names an Assistance Listing |
| amount_min / amount_max | `minimumAward` / `maximumAward` | `parse_int` (digits only; empty → null) |
| match_required | `matchingFundsRequirements` | empty, `N/A`, `None`, `No`, `Not applicable` → null; text saying `no match`, `not required` or `no cost share` → False; any other text → True |
| match_pct | same text | the one percentage when the text holds exactly one `N%`; two or more (`75% federal share / 25% local share`) → null |
| status | `status`, `openDate`, `closeDate` | see status rules |
| opens_at / closes_at | `openDate` / `closeDate` | ISO or epoch ms → date; placeholders kept as stated |
| closes_at_text | `grantCycle` | verbatim (`Annual`, `Upon Disaster Declaration`, `Revolving Loan Fund`); empty → null. This is the cycle wording the between-rounds view shows |
| rolling | `grantCycle` | matches `continuous`, `rolling`, `reoccurring` / `re-occurring`, `revolving` → True; else null |
| summary | `overview`, else `shortDescription` | HTML stripped |
| eligibility_text | `eligibility`, `applicantType`, `populationServedType` | the non-empty ones, verbatim, each on its own line as `Eligibility: …`, `Applicant type: …`, `Population served: …` |
| eligibility_structured | none | null |
| applicant_types | `applicantCategory` split on `;`, then `applicantType` | category map: `Municipality` → municipality, `Nonprofit` → nonprofit, `School` → school, `Business` → business, `Individual` → individual, `Native American Tribal Organization or Government` → tribe; `Public Agency` and `Other Legal Entity` produce no tag. Then the shared keyword tagger (`connectors.maryland_drupal.applicant_types_for`) over the free-text `applicantType` line adds what the categories cannot say (`Counties` → county, `State agencies` → state, `Townships` is not in the map). `source_code` is the category value or the matched phrase; a type already tagged is not tagged twice |
| categories | `category` (split on `;`) | `Transportation` → transportation, `Energy` → energy, `Environment & water` → water, `Housing` → housing, `Parks & recreation` → parks, `Health & human services` → health, `Employment, labor, & training` → workforce, `Law, justice, & legal services` → public_safety, `Community & economic development` → infrastructure (the Grants.gov `CD` precedent); `Agriculture`, `Creative industry`, `Education`, `Science, technology, and r&d`, `Veterans & military` and anything new → other. `source_code` is the text |

### Status rules

| Record says | Status |
|---|---|
| `Accepting applications` | open (even when `closeDate` has passed: the views drop it, the record says what the source said) |
| `Closed`, `openDate` after today, and `closeDate` empty or not before `openDate` | forecasted (`dmva/1` opens 2026-11-02; `dced/39` opens 2026-12-01) |
| `Closed` otherwise | closed (`pema/14`'s 2028 open date with a 2018 close date is an inconsistent record, kept as closed) |
| anything else, or no status | unknown |

`resolve_missing(source_id)` reads the detail page: readable → the rules above with `closes_at`; 404 or no
`pageApiData` → `unknown` (a vanished page is not a closure); network failure → `None`, which the pipeline records as
`unknown`.

### Change detection

The Coveo hit carries only the indexer's dates, so every run fetches every detail page (about 377 requests, around ten
minutes). The detail JSON's `last_modified` is stored in the payload and is not part of the record hash; it is the gate
to use when the run gets too slow. The payload is `{"hit": <copapwp* fields>, "detail": <page JSON>}`.

## Decisions (defaults; override at review)

1. **The search key is read from the page each run.** It is public and it rotates; a hard-coded key is a connector that
   silently returns nothing one day.
2. **`Public Agency` and `Other Legal Entity` tag nothing.** `Public Agency` covers counties, state agencies, authorities
   and special districts at once; tagging all four would invent eligibility. The free-text line names the real ones and
   the shared keyword tagger reads it. Third reuse of `applicant_types_for` (Drupal, SharePoint, now this); still no
   `connectors/text.py`.
3. **Placeholder dates are kept.** `2035-12-31` and `2999-07-01` are how the portal says "no deadline"; the record keeps
   them and `rolling` comes from `grantCycle`, never from the distance of a date.
4. **`Federal` money is `pass_through` with no ALN.** The record never names a listing; the ALN column stays empty
   rather than guessed from the program name.
5. **Only `applicantType` is scanned for applicant keywords**, not `populationServedType`: the population served is who
   benefits ("low-income residents"), not who applies.
6. **Duplicates across agencies stay.** Two Multimodal Transportation Fund rows are two agencies' rounds with different
   statuses and dates.
7. **Fixtures**: `search_page1.json` (one Coveo page trimmed), and one payload each for `pema/10` (closed, federal, two
   percentages, URL eligibility), `penndot/25` (open, award range, 30 % match), `dced/51` (closed, CFA money, the
   duplicate), `dced/2` (Act 47, `Reoccurring`, 2035 placeholder), `dmva/1` (closed with a future open date →
   forecasted), `pema/14` (inconsistent dates → closed), `dced/57` (tax credit), `dep/31` (federal loan, `Revolving
   Loan Fund`, 2999 placeholder), `pccd/63` (open, no close date).

## Out of scope

- `processSteps`, `additionalResources`, `FAQs`, `pointOfContact`, `linkToApply`, `totalFundsToBeAwarded`,
  `anticipatedFunding`, `decisionDate`, `reportingMonitoring`: stored in the payload, not mapped. Contacts and
  process steps may become columns when a second source has them.
- DCED's own WordPress program pages (`dced.pa.gov/programs/`, 144 programs, prose, no status field) are the fallback
  if a DCED program is missing from the portal, not a connector.
- `grants.pa.gov` (eGrants) is a login and is not read.

## Verification

1. `uv run ruff check .` and `uv run pytest -q` green against fixtures only.
2. On a scratch database: `cli.py run pa_grants --limit 20`, then a full run: about 377 added, about 84 open, the run
   row `ok`. A second run immediately: 0 changed, 0 missing.
3. `SELECT name, status, opens_at, closes_at, closes_at_text, rolling FROM program WHERE source_connector='pa_grants'
   ORDER BY status, closes_at;` eyeballed against `penndot/25`, `pema/10`, `dced/51`, `dced/2`, `dmva/1`.
4. `SELECT COUNT(*) FROM v_navigator_program WHERE state='PA';` near the 22 open-to-municipalities records of the
   survey date, less what the relevance tiers drop; `cli.py export` lists a PA row count and `site/pa/` shows them.
