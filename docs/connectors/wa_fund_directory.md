# Washington seed list (`wa_fund_directory`): source, raw data and field mapping

Milestone 12.4, the second of the two seed lists (decision 2026-11-03). Written 2026-11-04 from a read of the State
Treasurer's Washington Fund Directory, before the parser. The census (8.2) recorded Washington as a "seed list by
topic". Milestone 12 builds it as a directory connector: one record per program, `unknown`, the link kept, the agency
named, the fund source and topic kept. It is the richer of the two seed lists: a "Type of Program" label per row
(23 of them) and a Fund Source (Grant, Loan, Grant/Loan), so every row carries a funding type and 108 of 128 a category.

## Implemented (2026-11-04, same day)

`connectors/wa_fund_directory.py` follows this doc. First live run: 128 added in three seconds (seven GETs), second
run 0 changed. Every record `unknown`; 118 `grant` and 10 `loan` from the Fund Source column; 108 of 128 carry a
category from their Type of Program (transportation 31, water 23, parks 17, public_safety 15, energy 6,
infrastructure 6, housing 5, health 5); 4 `pass_through`; 15 agency codes over 16 agency spellings ("Dept. of
Commerce" once). The Washington page: 16 agencies, 128 programs, 0 open, 0 between rounds.

## The source

`https://tre.wa.gov/financing-and-debt/other-programs/washington-fund-directory` (Drupal 10; robots allows). The
landing page asks "What type of project are you funding?" and answers with six topic cards, each an `h3` link to a
page under the same path: Education, Emergency Management, Environment Water & Energy, Housing Infrastructure &
Economic Development, Recreation Culture & Social Services, Transportation. Each topic page is one Drupal views
table with five columns: Program (a link to the agency's own page), Type of Program, Fund Source, Agency, Details.

```html
<tr>
<td class="views-field views-field-title" data-sort-value="CDBG General Purpose Grant Program"><a href="https://www.commerce.wa.gov/cdbg/cdbg-general-purpose/">CDBG General Purpose Grant Program</a></td>
<td class="views-field views-field-field-type-of-program">Economic Development</td>
<td class="views-field views-field-name">Grant</td>
<td ...>Department of Commerce</td>
<td ...>Community Development Block Grant General Purpose Grants fund projects benefiting low- and moderate-income persons in rural communities.</td>
</tr>
```

On 2026-11-04: 149 rows across the six tables (6, 17, 52, 19, 22, 33), 128 programs, because a program is listed
under every topic it fits (111 under one, 15 under two, 2 under four). Every program links out (commerce.wa.gov 28,
ecology.wa.gov 27, rco.wa.gov 22, mil.wa.gov 11, wsdot.wa.gov 10, tib.wa.gov 7, ...). Sixteen agencies. Fund Source
is Grant 117, Loan 10, Grant/Loan 1. No status, no dates, no eligibility, no amounts anywhere.

## Field mapping (Program model in pipeline/models.py)

| Program field | Source | Rule |
|---|---|---|
| source_connector | | `wa_fund_directory` |
| source_id | Program | the slug of the program name; one record however many topics list it |
| source_url | the Program link | absolute; the landing page when a row has no link (none today) |
| external_number | | null |
| name | Program | the link text, whitespace normalized |
| level / jurisdiction | | `state`, `WA` |
| administering_agency | Agency | as written (one row writes "Dept. of Commerce"; kept as written) |
| agency_code | Agency | `WA-` plus the state's own acronym from a sixteen-entry table (`WA-COM`, `WA-ECY`, `WA-RCO`, `WA-WSDOT`, `WA-MIL`, `WA-TIB`, `WA-CRAB`, `WA-OSPI`, `WA-OST`, `WA-FMSIB`, `WA-UTC`, `WA-PARKS`, `WA-DOH`, `WA-WSHS`, `WA-WTHP`); an agency the table does not know gets its initials |
| funding_type | Fund Source | `Grant` -> grant, `Loan` -> loan, `Grant/Loan` -> grant (the label is kept in the structured field); the shared keyword rule only when the cell is empty |
| funding_source | Details | `pass_through` when the details say federal funds, FEMA, HUD, EPA, USDA or FHWA; else `direct` |
| amount / match | | null |
| status | | `unknown`: a directory states no round |
| opens_at / closes_at / closes_at_text / rolling | | null |
| summary | Details | as written (about a hundred characters) |
| eligibility_text / applicant_types | | null and none: Details say what the money is for ("benefiting low- and moderate-income persons in rural communities"), a population served, not who applies (decision 10.2) |
| eligibility_structured | Type of Program, Fund Source, topics | `{"type_of_program", "fund_source", "topics": [...]}` |
| categories | Type of Program | the row's own label through the shared table (added 2026-11-04): Water Quality, Pollution Cleanup, Wetlands Watershed and Shoreline Restoration -> water; Energy -> energy; Transit and other alternative transportation, Bridges Roads and Safety Improvements, Rail and Freight -> transportation; Economic Development -> infrastructure; Housing -> housing; Recreation, Outdoor Recreation, Recreation and Conservation, Recreation and Culture -> parks; Emergency Management, Emergency Mitigation -> public_safety; Social Services -> health. Air Quality, Salmon Recovery, Conservation, Broadband, Education, Agriculture name none of ours. `source_code` the label |
| alns | | none |

### Status rules

One: `unknown`.

### What happens when a program leaves

The six tables are read every run; a program no longer in any of them is `resolve_missing` -> `unknown`. A topic
page that cannot be read aborts the run rather than mark its programs missing.

## Decisions (defaults; override at review)

1. One record per program across the six topics, with every topic kept: the Treasurer's page repeats a program per
   topic as a finding aid, and a reader wants one row.
2. The category comes from the row's "Type of Program", not the topic card: the row's label is the agency's own
   classification of that program; the topic is the Treasurer's grouping and is kept as a list.
3. Fund Source is the funding type. It is the source's own word; `Grant/Loan` (one program) is recorded as a grant
   with the label kept, the TOD precedent (one program, two kinds).
4. Agency codes are the state's acronyms, hand-mapped once, because initials collide (Commerce and Ecology would both
   be "DE"-shaped) and a reader of `WA-WSDOT` knows the agency.
5. No applicant tags, as for North Carolina: a directory's description is what the money is for.

## Known gaps

- No row is ever open or between rounds from this connector; the coverage line is the product.
- The Washington Trust for Historic Preservation is a nonprofit, not a state agency; it is listed because the
  Treasurer lists it.

## Verification

`tests/test_wa_fund_directory.py` against `tests/fixtures/wa_fund_directory/` (the landing page and six topic pages,
scrubbed by `scripts/probe_wa_fund_directory.py`).

## Live runs

| Run | Date | Result |
|---|---|---|
| first | 2026-11-04 | fetched 128, added 128, changed 0, missing 0, three seconds |
| second | 2026-11-04 | fetched 128, added 0, changed 0, missing 0 |
