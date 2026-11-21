# New Mexico DFA's Grant Search Dashboard: survey (12.8, 2026-11-17)

Milestone 12.8. New Mexico was one of the "blocked ten" (502 and resets through the development proxy) that answered the
Actions runner on 2026-11-04. Every read below is from the runner (`probe-hosts` runs 5 to 9, the `NM*` keys in
`scripts/probe_hosts.py`, bodies saved with `--save` as a week-long artifact), the connectors' User-Agent, 3 s apart, about
a dozen requests in all to `platform.dfa.nm.gov`. **Not built yet**: this doc comes first (CLAUDE.md), the build is the
next session.

## The source

- `www.nmdfa.state.nm.us` (WordPress, Yoast; robots `User-agent: * / Disallow:`) links a **Grant Search Dashboard** at
  `https://platform.dfa.nm.gov/grant-search.html`, part of DFA's CAPS platform (Capital Projects System).
- The page is a Kendo grid filled by `js/grant-search.js`. **It is public by design**: `js/session.js` lists `grant-search`
  and `grant-profile` as its public pages, and the jQuery prefilter adds an `authTokenGUID` only when one is stored.
  `platform.dfa.nm.gov` serves no `robots.txt` (404).
- The grid reads plain JSON:
  - `GET /api/CAPS/SearchFundingOpportunities?page=1&pageSize=20&sortField=lastUpdatedDate&sortDir=desc&excludeClosed=1`
    (the grid's own call; more filters exist: `q`, `agencyIds`, `categoryIds`, `eligibleApplicants`, `closeDateFrom/To`,
    `isRollingOpportunity`). Answers `{"status": "ok", "data": {"data": [...], "total": N}}`. **`pageSize` is capped at 200.**
  - `GET /api/CAPS/GetFundingNavigationFormMeta`: 27 categories, 33 counties, **192 New Mexico state agencies** (id, name,
    business unit).
  - `GET /api/CAPS/GetFeaturedOpportunities`: the dashboard's featured list (7 rows on 2026-11-17).
  - A profile page per row: `grant-profile.html` (not yet read).

## What it holds (2026-11-17)

**1,450 open rows.** Most are copies of Grants.gov (`source: "grants.gov"`, `fundingSource: "Federal"`, an
`announcementUrl` on simpler.grants.gov): the first 200 by last update are all Grants.gov. Mixed in are **rows New Mexico's
own agencies post, `source: "agency"`**, with an `agencyId` from the 192. The featured list shows three:

| id | Agency | Title |
|---|---|---|
| 3496 | Economic Development Department | Healthy Food Financing Fund (HFFF) |
| 3799 | Southwest Border Region Commission | Economic and Infrastructure Development (EID) Grant Program |
| 3019 | Energy, Minerals, and Natural Resources Department | Land & Water Conservation Fund (LWCF) |

How many `source: "agency"` rows there are is the build session's first count (paging the open set is 8 requests at 200
a page; or the `agencyIds` filter with the 192 ids in one request, if the API accepts the array).

## Field mapping (draft; confirmed on the full sample before the parser)

Read only `source != "grants.gov"` rows: the Grants.gov copies are already in the registry through `grants_gov`, and a
second copy would double them.

| Program | Source field | Note |
|---|---|---|
| `source_id` | `fundingOpportunityId` | stable integer |
| `name` | `opportunityTitle` | |
| `agency` | `agencyName` (`sourceAgencyName` when null) | the Southwest Border Region Commission row has no `agencyId` |
| `source_url` | `announcementUrl`, else `https://platform.dfa.nm.gov/grant-profile.html?id=<id>` | profile URL form to confirm |
| `summary` | `description` | |
| `closes_at` | `closeDate` (epoch milliseconds) | |
| `closes_at_text` | `closeDateDescription` | free text ("Forecasted", rounds) |
| `rolling` | `isRollingOpportunity` | 0/1 |
| `status` | `closeDate` ahead: `open`; `closeDateDescription` "Forecasted": `forecasted`; rolling: `open`; else `unknown` | the shared status rules; `excludeClosed=1` lists only rows the dashboard calls open |
| `applicant_types` | `eligibleApplicants` (a JSON string list) through `portal_applicant` in `connectors/text.py` | labels: Local Government, State Agency, Tribes Pueblos Nations, Non-profit, Higher Education, Business / For-profit, Unrestricted / Any Applicant, Other / See Eligibility Text: one table entry each, added once |
| `eligibility_text` | `eligibleApplicantsOther` | |
| `categories` | `fundingActivityCategoryNames` through `portal_categories` | 27 portal categories, a label each |
| `funding_type` | `fundingInstrumentTypes` | Grant, Loan, Cooperative Agreement |
| `funding_source` | `fundingSource` ("Federal": `pass_through`) | to confirm on agency rows (null on the featured list) |
| `amount_min`, `amount_max` | `awardFloor`, `awardCeiling` | 0 means not stated: null |
| `match_required` | `costSharingRequired` | "Yes" / "No" |
| geography | `geographicRestrictionType`, `restrictedCounties` | kept in the payload; no field yet |

`programOfficerName`, `programOfficerEmail` and `programOfficerPhone` are not stored (a person's contact details).

## Sample (a Grants.gov copy, trimmed)

```json
{"fundingOpportunityId": 1690, "agencyId": null, "source": "grants.gov",
 "sourceAgencyName": "Department of Health and Human Services",
 "opportunityTitle": "Notice of Intent to Publish a Funding Opportunity Announcement for NIEHS Worker Training ...",
 "postedDate": 1748390400000, "lastUpdatedDate": 1794929466835, "closeDate": null, "isRollingOpportunity": 0,
 "closeDateDescription": "Forecasted", "awardCeiling": 0, "awardFloor": 0, "estimatedTotalFunding": 6000000,
 "fundingSource": "Federal", "costSharingRequired": "No",
 "eligibleApplicants": "[\"Tribes, Pueblos, Nations\",\"Higher Education\",\"Non-profit\"]",
 "fundingInstrumentTypes": ["Cooperative Agreement"], "fundingActivityCategoryNames": ["Health"],
 "geographicRestrictionType": "Statewide", "restrictedCounties": [],
 "announcementUrl": "https://simpler.grants.gov/opportunity/fef48e8c-..."}
```

## Build (12.8b, 2026-11-20)

**Read from this session's proxy this time**: `platform.dfa.nm.gov` answered the development proxy on 2026-11-20 (it had
walled it on 2026-11-17), so the survey reads below are direct, with the connectors' User-Agent, 3 s apart: 8 list pages,
the form metadata, the featured list, one profile script and one record. 11 requests.

**The count.** 1,428 open rows (`total`, read in 8 pages of 200, every id unique): **1,370 Grants.gov copies and 58 rows
New Mexico's agencies post** (`source: "agency"`). 44 of the 58 list `Local Government` among their applicants; most of the
rest name counties, municipalities or school districts in `eligibleApplicantsOther`. Agencies: Transportation 16,
Environment 10, NMFA 8, DFA 5, Public School Facilities Authority 4, USDA 3, Economic Development 3, Housing New Mexico 2,
Tourism 2, and one each from Agriculture, Cultural Affairs, EMNRD, the Interstate Stream Commission and the Southwest
Border Region Commission.

**What the 58 say.** 27 rolling (`isRollingOpportunity` 1), 24 `Forecasted`, 7 with a close date. `closeDate` is a plain
`YYYY-MM-DD` string on these rows (epoch milliseconds on Grants.gov copies); `fundingSource` is `State` (32) or `Federal`
(26), never null here; amounts are integers, 0 meaning not stated (33 state no ceiling); no HTML in `description`; every
row has an `announcementUrl` on the agency's own site, so the profile page is never the link.

**The single-record call.** `grant-profile.html?grantId=N` (not `?id=`) reads `GET /api/CAPS/GetFundingOpportunity?
fundingOpportunityId=N`: the list row's fields plus view counts, `data: null` when there is no such row. `resolve_missing`
uses it: one request per program that left the open list.

### Mapping (confirmed on the 58)

| Program | Source | Rule |
|---|---|---|
| `source_id` | `fundingOpportunityId` | |
| `source_url` | `announcementUrl` | the profile URL when it is empty (none today) |
| `name`, `summary` | `opportunityTitle`, `description` | |
| `administering_agency` | `agencyName`, else `sourceAgencyName` | |
| `status` | `closeDate` today or later: `open`; earlier: `closed`; else `Forecasted`: `forecasted`; else rolling: `open`; else `unknown` | the source's own words and dates only |
| `closes_at`, `closes_at_text`, `rolling` | `closeDate`, `closeDateDescription`, `isRollingOpportunity` | |
| `funding_type` | first of `fundingInstrumentTypes` (Grant, Loan, Cooperative Agreement, Other) | else the name keyword |
| `funding_source` | `Federal`: `pass_through`; else `direct` | |
| `amount_min`, `amount_max` | `awardFloor`, `awardCeiling` | 0 is null |
| `match_required` | `costSharingRequired` Yes/No | |
| `applicant_types` | the `eligibleApplicants` labels and `eligibleApplicantsOther`, through the shared tagger | `Higher Education` added to the portal table once (measured) |
| `categories` | `fundingActivityCategoryNames` through `portal_categories` | the clear labels added once (measured); the rest `other` |
| `eligibility_text` | `eligibleApplicantsOther`, else the labels joined | |
| `eligibility_structured` | the labels, the geography (`geographicRestrictionDisplay`), `estimatedTotalFunding`, `expectedAwardCount` | |

Not stored, in the payload or anywhere: `programOfficerName`, `programOfficerEmail`, `programOfficerPhone`, `createdBy`,
`updatedBy`, `featuredByUserId` (people's details and staff ids). The connector drops them before the record is saved,
because `atlas.db` is published.

### Scope calls (mine, each one line to overrule in `FEDERAL_HOSTS`)

- **Rows whose program page is on a federal site are left out** (`usda.gov`, `sbrc.gov`: 5 rows, USDA Rural
  Development's Community Facilities and Water & Waste Disposal programs, its predevelopment planning grants, NRCS's
  Agricultural Land Easement Program, the Southwest Border Region Commission's EID grants). They are federal programs the
  dashboard lists for New Mexico; on the state page they would read as state programs. The dashboard's own agency flag
  (`sourceType: external`) was not used for this because it also marks Housing New Mexico, a New Mexico public body.
- **The Grants.gov copies are left out** (`source: "grants.gov"`): `grants_gov` already reads them.

So `nm_dfa` holds **53 programs** on 2026-11-20.

**Links.** EDD's Targeted Federal Match link arrives with Mailchimp's `mc_cid` and `mc_eid` (the second identifies one
subscriber). `clean_url` drops mail-campaign and analytics parameters (`mc_*`, `utm_*`, `fbclid`, `gclid`) from the stored
link and from the saved payload; the rest of the address is kept.

**First run (2026-11-20, local copy of the database):** 8 requests, 24 s; 53 programs from 11 agencies, 30 open and 23
forecasted; 46 on New Mexico's page for local governments (40 likely fit, 6 may fit); the other 7 name schools, charter
schools, nonprofits and businesses, or tribal transit only. Category and applicant labels added to `connectors/text.py`
(`Higher Education`; eight category labels) moved 0 of 7,810 stored records and match no agency-page label or fixture
heading.
## Plan as surveyed (12.8a, kept for the record)

1. Count and save the `source: "agency"` rows (fixtures), confirm the mapping above on them, and read one
   `grant-profile.html` for the profile URL and any field the list lacks.
2. Build `nm_dfa` on the portal pattern (`ky_dlg`, `tx_egrants`): `fetch` pages the open set at 200 a page, 3 s apart, and
   keeps the agency rows; `resolve_missing` for a row that leaves the open set (`unknown`, the WebGrants rule, until it
   says otherwise).
3. Portal labels into `connectors/text.py` once each, measured on every stored record and fixture.
