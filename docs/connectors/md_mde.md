# Maryland Department of the Environment connector (md_mde): source, raw data and field mapping

Milestone 7, item 5 (the roadmap's 2026-11-03 order: MDEM, MDOT, MDE). Live survey 2026-11-03. Fourth agency on the
`MarylandSharePointConnector` base; the "water and sewer financing rows" the roadmap names, which turned out to be a
real index: the Maryland Water Infrastructure Financing Administration (MWIFA) page lists its seven programs in one
table under one status banner.

## Implemented (2026-11-03, same day)

`connectors/md_mde.py` follows this doc on the `MarylandSharePointConnector` base. Live run on a copy of the published
database: 7 records, all `forecasted` ("Applications will reopen in December 2026"), in seven requests, as expected
below; the second run reports no changes. Five carry a municipality tag and reach the Maryland page as likely rows
(WQRLF, DWRLF, Water Supply Assistance, the Bay Restoration Fund wastewater grants, the Comprehensive Flood Management
Grant Program); Supplemental Assistance ("communities") and the Septic program (no applicant named) do not. Maryland's
open-or-forecasted municipal count went from 15 to 20, between rounds stays at 19, and the state's coverage line reads
eight agencies and 141 records after the three connectors of the day.

## Source

`https://mde.maryland.gov`, SharePoint on the state's `mdgov` theme, behind Cloudflare. `robots.txt` disallows only
`/_vti_bin/`, `/_layouts/` and `/_catalogs/`. The page skeleton is exactly MEA's and DNR's
(`#ctl00_PlaceHolderMain_RichHtmlField1__ControlWrapper_RichHtmlField`, the H1 in the edit-mode panel).

### The index

`/programs/water/WQFA/Pages/index.aspx` (H1 "Maryland Water Infrastructure Financing Administration") opens with a
status banner in an `<h2>`:

```html
<h2 style="text-align:center;"><span ...>MWIFA's funding solicitation is currently closed. Applications will reopen in December 2026.</span></h2>
```

then "MWIFA administers the loan and grant programs described below:" and a two-column table:

```html
<table border="1" ...><tbody>
<tr><th>Financial Program</th><th>Purpose</th></tr>
<tr><td><a href="/programs/water/WQFA/Pages/water_quality_fund.aspx">Water Quality Revolving Loan Program (WQRLF)</a></td>
    <td><p>Provides low-interest loans to local governments to finance wastewater treatment plant upgrades, nonpoint source pollution control projects, and other water quality and public health improvement projects.</p></td></tr>
...
<tr><td><p>Supplemental Assistance Grant Program</p></td>
    <td><p>Assistance primarily to small and disadvantaged communities for sewer infrastructure improvements. Awards require a local match and are not to exceed $1.5 million ...</p></td></tr>
```

| Row | Linked page | Purpose (abridged) |
|---|---|---|
| Water Quality Revolving Loan Program (WQRLF) | `/programs/water/WQFA/Pages/water_quality_fund.aspx` | low-interest loans to local governments: wastewater treatment, nonpoint source, water quality |
| Drinking Water Revolving Loan Program (DWRLF) | `/programs/water/WQFA/Pages/drinking_water_fund.aspx` | low-interest loans to local governments: water supply, drinking water infrastructure |
| Water Supply Assistance Grant Program | `/programs/water/WQFA/Pages/wqfa_ws.aspx` | helps communities meet water supply needs; local match; not to exceed $1.5 million |
| Bay Restoration Fund - Wastewater Grant Program | `/programs/water/WQFA/Pages/wqfa_enr.aspx` | ENR upgrades, conveyance, sewer extensions, shared septic, MS4 projects by local governments, flood mitigation |
| Supplemental Assistance Grant Program | (none) | small and disadvantaged communities, sewer infrastructure; local match; not to exceed $1.5 million |
| Bay Restoration Fund - Septic System Upgrade Program | `/programs/Water/BayRestorationFund/OnsiteDisposalSystems/Pages/index.aspx` | septic upgrades to best available technology and sewer connections |
| Comprehensive Flood Management Grant Program | `/programs/Water/StormwaterManagementProgram/Pages/floodmgmt.aspx` | grants to "subdivisions" for flood mitigation; 50% of the local match with a federal sponsor, up to 75% without |

### The program pages

Each linked page is prose. The four MWIFA pages open with a bold line "Funding Applications Accepted December thru
January Annually" (the cycle, no year) and then say who the money goes to: WQRLF "Point Source Pollution Prevention
(Public Entities/Local Governments Only)" and "Nonpoint Source Pollution Prevention Public and Private Entities";
DWRLF "available to eligible public and private community water systems"; Water Supply "financial assistance to local
governments ... 87.5% of the total eligible project cost ... 12.5% local match requirement"; BRF Wastewater a history
of the ENR policy. The index says "Both loan programs receive federal funding from the United States Environmental
Protection Agency (EPA)". The Septic page is about the technology and its priorities (property owners are served
through counties; the page names no applicant). The CFMGP page: "established to assist local jurisdictions with ...
capital projects", "the CFMGP may fund up to 75% of the cost". A phone number closes each MWIFA page.

## Enumeration and change detection

- `fetch()` GETs the index (non-200, no table or no rows aborts the run), reads the banner and each row
  (`title`, `purpose`, `href`), keys a linked row by its page's source id and the unlinked Supplemental row by the
  index page's own source id (so the base still fetches a page for it), and stamps `row: {title, purpose, banner,
  linked}` on every payload. A banner change or a reworded Purpose changes every record it touches.
- Every page every run, seven requests (the index plus six pages; the index is fetched again as the Supplemental
  row's page).
- `resolve_missing`: as the base. A row dropped from the table whose page still exists gets the page's own reading
  (`unknown`, the page states only the annual cycle).

## Field mapping

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `md_mde` |
| source_id | the row's link, or the index path for the unlinked row | lowercased path |
| name | the row's title | always the index's words (the DWRLF page's H1 is "Drinking Water Supply Assistance Program", a different name for the same fund; the Septic page's H1 is a section title) |
| level / jurisdiction | constant | `state` / `MD` |
| administering_agency / agency_code | constant | `Maryland Department of the Environment` / `MD-MDE` |
| funding_type | name keywords, one override | `loan` for the two revolving loan programs, `grant` for the four named grants, `grant` for the Septic program by override (the page calls it "the Bay Restoration Fund (BRF) Onsite Sewer Disposal System (OSDS) grant program") |
| funding_source / alns | hand map | WQRLF and DWRLF `pass_through` ("Both loan programs receive federal funding from the United States Environmental Protection Agency"); no ALN, because the page names none (the registry's Grants.gov records carry 66.458 and 66.468 for the two SRFs; the join is left to a reader). The rest `direct`. |
| amount_min / amount_max | none | null (the "$1.5 million" ceilings are per project, stated in the Purpose text) |
| match_required | match wording over the Purpose cell and the page | Water Supply and Supplemental `True` ("require a local match", "12.5% local match requirement") |
| status | the banner | see status rules |
| opens_at | none | null: "December 2026" is a month, not a date |
| closes_at | none | null |
| closes_at_text | the banner, else the page's cycle line | "MWIFA's funding solicitation is currently closed. Applications will reopen in December 2026." |
| rolling | none | null |
| summary | the row's Purpose cell | the agency's one-paragraph description of the program |
| eligibility_text | the Purpose cell, then the page's applicant sentences | what the tagger read |
| applicant_types | shared tagger over the same lines | WQRLF, DWRLF, Water Supply, BRF Wastewater, CFMGP: `municipality`, `county` ("local governments", "local jurisdictions"); Supplemental and Septic: none (the words are "communities" and "septic systems") |
| categories | constant | `water`, source_code `mwifa` |

### Status rules

1. The banner says closed and names a month still ahead ("reopen in December 2026") → `forecasted` (DHCD's and DNR's
   month rule: compared by month, no date invented); the banner is `closes_at_text`.
2. The banner says closed and names no future month, or a month that has passed → `closed`.
3. The banner says open or accepting; a full date in it is `closes_at` → `open`.
4. No banner: the page's own cycle line ("Funding Applications Accepted December thru January Annually") is kept as
   `closes_at_text` and the status is `unknown` (a cycle with no year is not a round).

Expected on 2026-11-03: all seven `forecasted`.

## Decisions

1. **The index banner sets every row's status.** The seven programs share one solicitation ("MWIFA's funding
   solicitation"); the agency states the status once, above the table. A page's own cycle line never contradicts it.
2. **A Purpose cell is applicant text.** The Purpose column is the agency's own statement of who the money is for
   ("loans to local governments"), the VDOT card-blurb precedent (11.4). The page's applicant sentences add to it;
   for the unlinked Supplemental row the Purpose is the only text read, because its "page" is the index and the
   index's sentences would tag every row's local governments.
3. **The row's title is the name**, not the page H1, because two pages are titled differently from the fund they
   describe and the index is the agency's list.
4. **No ALN is invented** for the two federal revolving funds; `pass_through` with an empty list says "federal money,
   number not stated here".
5. **The Septic program is a grant by override**: the name has no keyword and the page calls it a grant program.
6. **Phone numbers are dropped from the stored body** (the WebGrants rule).

## Known gaps

- "small and disadvantaged communities" (Supplemental) and "subdivisions" (CFMGP's statute word, in quotes on the
  index) tag nothing; CFMGP is tagged from its page's "local jurisdictions". Settled 2026-11-11 (roadmap 10.6):
  "Assistance primarily to ... communities" describes who benefits, not who applies (Saj's rule: communities tag only
  where they apply or are eligible), and the index's "subdivisions" is not in an applicant line; source-limited.
- The 87.5% / 12.5% split and the $1.5 million ceilings stay in text (`match_pct`, `amount_max` null): the rules read
  sentences, and a `match_pct` parser is a third-case question.
- MDE's other grants (recycling, lead, the Clean Water Commerce Act project lists, EV charging) are not on this index
  and have no listing; when a town asks for one by name it is a hand-added entry here.

## Fixtures

`tests/fixtures/md_mde/`: `index__programs__water__wqfa__pages__index.json` (`url`, `main_html`) and one JSON payload
per page, written by `uv run python scripts/probe_maryland_sharepoint.py md_mde`.
