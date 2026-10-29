# New Jersey DCA SAGE connector (`nj_dca_sage`): source, raw data and field mapping

Milestone 9, connector 7. Written 2026-10-28 from the Mid-Atlantic survey (`docs/surveys/mid_atlantic.md`), before the
parser. One state department, one public page, ten RFPs: the last of the small single-office builds.

## Implemented (2026-10-28, same day)

`connectors/nj_dca_sage.py` follows this doc. First live run on a fresh database: 10 records added in 2.5 seconds (all open;
1 loan by title keyword, 9 with no stated type), 0 errors. Second run: 0 changed, 0 missing. On the New Jersey page: 3 open
municipal rows (Affordable Housing Trust Fund 2027, deadline 2026-11-19; Lead-Safe Home Remediation 2026, 2026-12-22;
NJHOMES Launchpad Predevelopment Fund 2027, 2027-06-30; all likely tier) and no between-rounds group yet. The deadlines and
eligible-applicant text of those three were checked against the live page. Found while writing the fixture: the page's
HTML is not well formed, so a tree parser nests later RFPs inside earlier ones; the connector reads by field id and
document order, which is unaffected, and the probe trims the page by text offsets instead of by tree.

## The source

The Department of Community Affairs (DCA) runs its grants through SAGE, an IntelliGrants system (Agate Software). Its
portal, `https://dcasage.intelligrants.com/Portal.asp`, links "View available grant opportunities" to one public page:

```
https://dcasage.intelligrants.com/RFPMailingRequest_List.asp
```

Titled "Request more information about available RFPs"; the page itself says "Please note that no registration is
required." Classic ASP, 112 KB, 17 nested layout tables, no paging, no query form. `robots.txt` is a 404 (no
restrictions). One GET a run.

The other SAGE instance, `https://njsage.intelligrants.com` (the "other NJ State Department's SAGE", reached from
`sage.nj.gov`), is **login-only**: `/Opportunities.aspx` redirects to a login and the RFP list path answers 404. DCA's
page is the only public New Jersey listing. (`dep.nj.gov` sits behind an Incapsula challenge and is recorded in the
census as not read; nothing here changes that.)

### The page

Each RFP is a block of labelled fields. Every value is in `<span id="<field>_<n>_text" class="FieldStandard">`, `n`
being the RFP's position on the page (0 to 9 today). Titles and divisions are `<label class="RFPCategoryName">`: on a
`#C3D3D3` row for a division, on a `#D3D3D3` row for a title, in document order (a division, then its titles, then
that title's fields).

| Label on the page | Field id | Notes |
|---|---|---|
| Grant Period Start / Stop | `rfpContractStartDate`, `rfpContractStopDate` | the award's term; blank on one RFP |
| Deadline for Submission | `rfpDueDate` | `M/D/YYYY` on all 10 |
| Deadline for Initiation | `rfpAvailabilityStopDate` | equal to the submission deadline on all 10 |
| Contact Information | `ProgramContact`, `ProgramContactPhone`, an e-mail link | a named staff member; not stored |
| Population to be Targeted | `rfpPopulationTargeted` | |
| Dollar Range for Award Minimum / Maximum | `rfpMinimumAwardAmount`, `rfpMaximumAwardAmount` | `$50,000.00`; minimum on 2 of 10, maximum on 4 |
| Estimate of Total Amount of Funds to be Awarded | `rfpEstimateTotalRFPFunds` | on 4 of 10 |
| Allowable Costs | `rfpAllowableCosts` | |
| Eligible Applicant | `rfpEligibility` | free text, on all 10 |
| Purpose of Grant | `rfpDescription` | 105 to 535 characters |
| Timeframe for Completion of Activities | `rfpTimeframeCompletion` | |
| Technical Assistance Meeting | `rfpTechnicalAssitance` (sic) | |
| Other Information | `rfpOtherInformation` | links to PDFs |

There is **no ID** and no per-RFP URL: every RFP is on the one page, titles carry the year ("Affordable Housing Trust
Fund 2027") and are unique today, and `n` is positional, so it changes whenever an RFP is added or removed.

### What the page held on 2026-10-28

Ten RFPs: nine from the Division of Housing and Community Resources, one from the Division on Fire Safety.

| Title | Due | Eligible applicant (start of the text) |
|---|---|---|
| Affordable Housing Trust Fund 2027 | 11/19/2026 | Municipalities, for-profit and non-profit affordable housing developers |
| HOME Community Housing Development Organizations 2027 | 6/30/2027 | Limited to nonprofit, community based developers that are certified as Community Housing Development Organizations |
| HUD Lead Hazard Control and Healthy Homes 2026 | 11/24/2026 | Non-profit organizations and community action agencies ... |
| Lead-Safe Home Remediation 2026 | 12/22/2026 | This RFP is open to nonprofit organizations and units of local government ... |
| National Housing Trust Fund 2027 | 6/30/2027 | non-profit or for-profit affordable housing developers |
| Neighborhood Revitalization Tax Credit Planning 24 | 12/31/2026 | Qualified non-profit organizations ... |
| New Jersey Healthy Homes Initiative 2027 | 6/30/2027 | for-profit and non-profit affordable housing developers |
| NJHOMES LAUNCHPAD PREDEVELOPMENT FUND 2026 | 6/30/2027 | Non-profit affordable housing developers ... |
| NJHOMES LAUNCHPAD PREDEVELOPMENT FUND 2027 | 6/30/2027 | Municipalities, for-profit and non-profit affordable housing developers |
| Volunteer Emergency Service Organization Loan 2027 | 6/30/2027 | Fully and partially volunteer fire companies, first aid squads and rescue squads |

Through the shared tagger (negated sentences dropped): three name municipalities or units of local government
(Affordable Housing Trust Fund 2027, Lead-Safe Home Remediation 2026, NJHOMES Launchpad 2027); the others are nonprofit,
business or tag nothing (the volunteer fire companies). Six of ten due dates are `6/30/2027`, the end of the fiscal
year. "Neighborhood Revitalization Tax Credit Planning 24" is listed with a grant period that ended 6/3/2024 and a
deadline of 12/31/2026; the page says both.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `nj_dca_sage` |
| source_id | title | the slug of the title (`affordable-housing-trust-fund-2027`); a repeated slug gets `-2`, `-3` |
| source_url | constant | the list page (every RFP is on it) |
| external_number | none | null |
| name | title | whitespace collapsed |
| level / jurisdiction | constant | `state` / `NJ` |
| administering_agency | division | `Department of Community Affairs, <division>`; both are the page's own words ("the State of New Jersey Department of Community Affairs grant management system", the division label) |
| agency_code | constant | `NJ-DCA` |
| funding_type | title | the shared `funding_type_for`, except that a `tax_credit` result is dropped (decision 4) |
| funding_source | none | `direct`: the page makes no claim about whose money it is |
| amount_min / amount_max | Dollar Range for Award Minimum / Maximum | labelled award limits; `$50,000.00` is 50000; blank is null |
| match_required / match_pct | none | null: no labelled field |
| status | Deadline for Submission | see status rules |
| opens_at | none | null: the page has no opening date (the grant period is the award's term, not the application window) |
| closes_at | Deadline for Submission | the date as written |
| closes_at_text | none | null |
| rolling | none | null: the page states a date for every RFP, including the six that are the fiscal-year end |
| summary | Purpose of Grant | whitespace collapsed |
| eligibility_text | Eligible Applicant | verbatim, whitespace collapsed |
| eligibility_structured | Population, funds, term, division | `{"division": ..., "population": ..., "total_funds": "$30,000,000.00", "grant_period": "7/1/2026 - 6/30/2027"}`, keys only when present |
| applicant_types | Eligible Applicant | see decision 2 |
| categories | none | none: the page states no topic |
| alns | none | always empty |

### Status rules

The page's own word is "Available RFPs".

| The page says | Status |
|---|---|
| a Deadline for Submission before today | closed |
| otherwise (a deadline today or later, or none) | open |

The day of the deadline is open. A listed RFP is open until its own deadline passes; the page is not expected to carry a
closed one, but a stale posting must read `closed`, never `open`.

### What happens when an RFP leaves the page

`resolve_missing(source_id)` returns `unknown` and makes no request. There is one page and nothing behind it to read
back. When DCA retitles a program for a new year ("... 2027" to "... 2028") the new title is a new record and the old one
goes `unknown`; with no ID on the page that is the correct picture of a new round.

### Change detection

The hash is over the Program. The page carries no modified stamp; one request is read every run.

## Decisions (defaults; override at review)

1. **Parse by field id, not by position or layout.** The page is 17 nested tables; the ids are the stable part. A field
   missing from one RFP does not shift the others, and the title and division of each RFP are the nearest preceding
   `RFPCategoryName` labels in document order.
2. **Applicants are the Eligible Applicant text, sentence by sentence.** Split into sentences, drop any the shared
   `NEGATION_RE` matches, then the shared `applicant_types_for`. Same rule as `webgrants` and `tx_egrants`.
3. **The run aborts if the parser and the page disagree.** The number of RFPs found must equal the number of "Deadline
   for Submission" labels, and a page with no RFP must still carry the page's "Request more information about
   available RFPs" instruction text. An error page or a changed layout fails loudly instead of marking every round
   missing. An honestly empty list (the instruction text and no RFP) returns no records.
4. **A `tax_credit` title is not a funding type here.** "Neighborhood Revitalization Tax Credit Planning" is a planning
   grant named for the tax-credit program it supports, and the page gives it a grant period like the others. The shared
   keyword rule would call it a tax credit; the connector keeps `loan` and `grant` and leaves the rest null.
5. **The program contact is dropped before the payload is stored.** Name, phone and e-mail of a staff member are on the
   page; the database is published (the same rule as `webgrants`).
6. **Award limits are award limits; the estimate is a total.** `Dollar Range for Award Minimum` and `Maximum` fill the
   amount columns; `Estimate of Total Amount of Funds` is a program total and stays in `eligibility_structured`.
7. **Fiscal-year-end deadlines keep their date.** `6/30/2027` is stated, so it is `closes_at`; the record does not
   claim `rolling`.

## Known gaps (the source's wording, not the parser's)

- No ID: a retitled RFP is a new record (above).
- No opening date, so a new RFP cannot be told from an old one by `opens_at`; "new" on the page comes from first-seen.
- The Fire Safety RFP's applicants (volunteer fire companies, first aid squads, rescue squads) are not in the shared
  tagger's vocabulary and carry no tag.
- The empty-list fixture is built from the real page by removing every RFP; the page has not been seen with no RFP, so
  the instruction-text check is a guess at what an honestly empty page looks like (if it is wrong the run aborts, which is
  the safe direction).
- The "Neighborhood Revitalization Tax Credit Planning 24" posting is stale on its own page (a grant period that ended in
  2024 against a 2026 deadline); the record repeats what the page says.

## Out of scope

The RFP documents (PDFs) and the guidelines; the other SAGE instance (login-only); other New Jersey departments.

## Verification

- `tests/test_nj_dca_sage.py` against `tests/fixtures/nj_dca_sage/` (the live page trimmed to four RFPs across both
  divisions with contacts, scripts and hidden inputs removed, and an empty-list page, written by
  `scripts/probe_nj_dca_sage.py`): field-id parsing, the division and title assignment, statuses including a past-due and a
  missing date, amounts and the total, the three municipal tags, the tax-credit title, slug uniqueness, `fetch` with a
  mock transport (retry, an HTTP error aborts, the count and instruction-text aborts, an empty list), the contact absent
  from the payload and the record, `resolve_missing`.
- Two live runs: all added, then 0 changed.
