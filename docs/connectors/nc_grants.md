# North Carolina seed list (`nc_grants`): source, raw data and field mapping

Milestone 12.4, the first of the two seed lists (decision 2026-11-03). Written 2026-11-04 from a read of nc.gov's
grant table, before the parser. The census (8.2) recorded North Carolina as a "seed list": a state-run directory of
programs with no status or dates, "an enumeration aid, not a record source". Milestone 12 builds it anyway as a
directory connector: one record per program, `unknown`, the link kept, the agency named. Low value per row, honest
coverage, and the list of agencies a North Carolina session reads first.

## Implemented (2026-11-04, same day)

`connectors/nc_grants.py` follows this doc. First live run: 75 added in one second (one GET), second run 0 changed.
Every record `unknown`; 62 carry `grant` from their name, 13 no funding type; 35 carry a category (health 18,
infrastructure 12, public_safety 7, counting a program under each category it is listed in); 3 `pass_through`
(FEMA, USDA, federal wording in the description); 17 agency codes. The North Carolina page: 17 agencies, 75
programs, 0 open, 0 between rounds, as a directory should show. Found while writing the parser: eleven of the 86
rows are a program listed again under a second category, so the record count is 75 and a record keeps every
category.

## The source

`https://www.nc.gov/your-government/all-nc-state-services/grant-opportunities` (Drupal, static hosting; robots
allows, sitemap). One `table` with four columns, Category, Grant Program (a link to the agency's own page), Agency
(a code: Commerce, DEQ, DHHS, DNCR, DIT, DPI, DOA, DPS, AGR, DOL, DOT, DOJ, OSFM, LWF, APNEP, CFNC, VolunteerNC),
Description (one or two sentences on what the money is for). 86 rows on 2026-11-04; eleven are a program listed
again under a second category, so the connector reads 75 programs and keeps every category a program is listed
under. Ten categories: Agriculture, Art & Culture, Community Service, Disaster Recovery, Economic Development,
Education, Environment, Health and Human Services, Public Safety, Technology, Broadband and Digital Equity. No
status, no dates, no eligibility, no amounts anywhere on the page.

```html
<tr><td>Economic Development</td>
    <td><a href="https://www.commerce.nc.gov/grants-incentives/building-or-site-funds">Building and Site Fund Grants</a></td>
    <td>Commerce</td>
    <td>Building and Site Fund Grants include Building Reuse Grants, ...</td></tr>
```

The links go to 17 agencies on their own hosts (commerce.nc.gov 18, ncdhhs.gov 12, deq.nc.gov 15, ncbroadband.gov 6,
dpi.nc.gov 5, doa.nc.gov 4, ncdps.gov 3, ...). The connector never fetches them: that is what a North Carolina
agency session (12.6) does, in this order.

## Field mapping (Program model in pipeline/models.py)

| Program field | Source | Rule |
|---|---|---|
| source_connector | | `nc_grants` |
| source_id | Grant Program | the slug of the program name (`building-and-site-fund-grants`); a program listed under two categories is one record |
| source_url | the link | absolute; the index itself when a row has no link (none today) |
| external_number | | null |
| name | Grant Program | the link text, whitespace normalized |
| level / jurisdiction | | `state`, `NC` |
| administering_agency | Agency | the code as the table writes it (`DEQ`, `Commerce`) |
| agency_code | Agency | `NC-` plus the code upper-cased (`NC-DEQ`, `NC-COMMERCE`) |
| funding_type | name | the shared keyword rule (62 `grant`, 13 null: funds, programs, incentives named without the word); no default, the table does not say |
| funding_source | Description | `pass_through` when the description says federal funds, FEMA, HUD or USDA; else `direct` (3 pass-through today) |
| amount / match | | null; the table carries none |
| status | | `unknown`: a directory states no round |
| opens_at / closes_at / closes_at_text / rolling | | null |
| summary | Description | as written |
| eligibility_text / applicant_types | | null and none: a description says what the money is for ("financial assistance to farmers and growers"), which is a population served, not a statement of who may apply (decision 10.2); nothing is tagged |
| eligibility_structured | Category | `{"categories": [...]}`, every category the program is listed under |
| categories | Category | the shared table: Economic Development -> infrastructure, Health and Human Services -> health, Public Safety and Disaster Recovery -> public_safety (added 2026-11-04); the other six name none of ours and give no tag; `source_code` the category |
| alns | | none |

### Status rules

One: `unknown`. The page states no round for any program.

### What happens when a program leaves

The table is read every run; a program no longer in it is `resolve_missing` -> `unknown` (no request).

## Decisions (defaults; override at review)

1. One record per program, not per row: the table repeats a program under each category it fits, and a reader
   wants one row with two categories, not two rows.
2. No applicant tags from descriptions. The tagger would read "farmers", "local governments", "schools" in a
   sentence about what the money is for; the 10.2 rule says a population served is not an applicant. The North
   Carolina page therefore shows no municipal rows from this connector, which is the honest state of a directory.
3. The agency code is the table's own word, upper-cased: a reader sees `DEQ` the way the state writes it.
4. Nothing is fetched behind the links. That is 12.6's work, and the roadmap says which agencies first.

## Known gaps

- 13 programs have no funding type: the name says "Fund", "Program" or "Incentives" and the table says nothing more.
- No row will ever be open or between rounds from this connector; the coverage line is its product.

## Verification

`tests/test_nc_grants.py` against `tests/fixtures/nc_grants/index.html` (scrubbed by `scripts/probe_nc_grants.py`).

## Live runs

| Run | Date | Result |
|---|---|---|
| first | 2026-11-04 | fetched 75, added 75, changed 0, missing 0, one second |
| second | 2026-11-04 | fetched 75, added 0, changed 0, missing 0 |
