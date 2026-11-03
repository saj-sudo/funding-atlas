# Delaware DNREC Environmental Finance connector (`de_dnrec`): source, raw data and field mapping

Milestone 11, Delaware's first agency (the municipal five, decision 2026-11-03). Written 2026-11-03 from the
Mid-Atlantic survey, which called DNREC Environmental Finance "the closest thing to a Delaware local-government grants
index", and a read of every page the office's menu lists, before the parser. Water, sewer, stormwater and land
conservation money for towns, plus the property-owner and private-sector programs beside them.

## Implemented (2026-11-03, same day)

`connectors/de_dnrec.py` follows this doc. First live run on a fresh database: 12 records added, 0 errors; second run
0 changed. Two open on the page's words (Community Water Quality Improvement, "Now Accepting Project Proposals"; the
Asset Management Incentive Program, "submitted at any time ... first come, first served", rolling), ten `unknown`.
Seven tag a municipality (the planning grants, planning advances, asset management, the water quality, stormwater
and land conservation loans), four a county. The Delaware page: **1 open municipal row** (Asset Management, likely)
and 0 between rounds. Found while writing the parser: "Notice of Intent" is a loan-list step, not a cycle, and left
the cycle words.

## The source

`https://dnrec.delaware.gov/environmental-finance/` (WordPress on the state's CLF template; `robots.txt` is
`User-agent: * / Disallow:`, nothing restricted). The index page groups its programs under "Assistance For Local
Governments" (Grants: Community Water Quality Improvement, Surface Water Matching Planning, Wastewater Matching
Planning, Asset Management Incentive, Project Planning Advances; Loans: Publicly Owned Wastewater Treatment, Water
Quality Improvement, Stormwater Infrastructure, Land Conservation), "Grants for Property Owners" (Septic
Rehabilitation) and "Loans for the Private Sector" (Private Projects that Support Estuary Programs), plus the
Non-Point Source Program Funding page the text links. Twelve program pages, read by hand list (decision 1); the Clean
Water Initiative page is a fund overview, not a program, and is not read.

| Slug | Kind (from the index section) |
|---|---|
| `community-water-quality-improvement`, `surface-water-planning-grants`, `wastewater-planning-grants`, `asset-management`, `planning-advances` | grant |
| `wastewater-treatment`, `water-quality-improvement`, `stormwater-infrastructure`, `land-conservation` | loan |
| `septic-rehabilitation` | grant |
| `estuary-programs` | loan |
| `non-point-source-funding` | (the page says loans and grants; null) |

Twelve GETs a run, 0.3 s apart.

### A page

```html
<div id="main_content"> ... <div class="col-md-3"> (the section menu) </div>
  <div class="col-md-9"> <h1>Project Planning Advances</h1>
    <p class="wp-block-paragraph">Municipalities are eligible to receive up to $75,000 to complete planning reports each year. Municipalities are allowed to submit one application per state fiscal year (July 1 through June 3).</p>
    <h4 class="wp-block-heading">Eligible Projects</h4><p class="wp-block-paragraph">Preliminary Engineering Reports and Environmental Information Documents needed for loan applications.</p>
    <h4 class="wp-block-heading">Eligible Applicants</h4><p class="wp-block-paragraph">Municipal governments</p>
    <p><small><span class="label label-success">Related Topics:</span> <a rel="tag">clean water</a>, <a rel="tag">drinking water</a>, <a rel="tag">finance</a>, ...</small></p>
```

Prose with WordPress block headings. What the twelve said on 2026-11-03:

| Page | Applicant text | Cycle text |
|---|---|---|
| Community Water Quality Improvement Grants | "Nonprofit organizations, conservation districts, community organizations and homeowners' associations can submit proposals" | "Now Accepting Project Proposals"; "Submission deadline: Oct. 30." (no year) |
| Surface Water Matching Planning Grants | "The program is designed to assist counties and municipalities" | none |
| Wastewater Matching Planning Grants | "municipal and county wastewater utilities" | "An informational workshop is held once a year in January"; "capped at $50,000 with a 1:1 cash match requirement" |
| Asset Management Incentive Program | `Eligible Sectors`: "Delaware public wastewater and drinking water utilities"; "Eligible municipal utilities can receive either grants or loan interest rebates" | "Applications can be submitted at any time and are reviewed on a first come, first served basis, as long as funding remains." |
| Project Planning Advances | `Eligible Applicants`: "Municipal governments" | "one application per state fiscal year" |
| Publicly Owned Wastewater Treatment Projects | `Eligible Applicants`: "Owners/operators of publicly owned wastewater treatment facilities" | the Project Priority List cycle ("begins in January") |
| Water Quality Improvement Loan Program | `Eligible Projects` only | none |
| Stormwater Infrastructure Loans | `Eligible Applicants`: "Stormwater projects can be eligible as municipal (212) projects, non-point source (319), and/or green infrastructure" | the Project Priority List cycle |
| Land Conservation Loan Program | `Eligible Applicants`: "Municipalities with wastewater projects on the fundable portion of the WPCRF project priority list" | none |
| Septic Rehabilitation Grant Program | eligible costs only (property owners by the index section) | none |
| Private Projects that Support Estuary Programs | `Eligible Projects`: "Privately owned water quality improvement projects" | none |
| Non-Point Source Program Funding | "The program allows private landowners, homeowner associations, corporations, local and county governments, state agencies, nonprofit ..." | none |

Every page ends with "Related Topics" tags (`clean water`, `drinking water`, `finance`, `grants`, `infrastructure`,
`water quality financing`, `loans`, `septic systems`, ...): the agency's own topic labels. Contact paragraphs name a
person with an e-mail and phone.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `de_dnrec` |
| source_id | hand list | the slug |
| source_url | hand list | `https://dnrec.delaware.gov/environmental-finance/<slug>/` |
| external_number | none | null |
| name | `h1` | as written |
| level / jurisdiction | constant | `state` / `DE` |
| administering_agency | constant | `Department of Natural Resources and Environmental Control` |
| agency_code | constant | `DE-DNREC` |
| funding_type | the index section | `grant` or `loan` by the section the index lists the page under; null for Non-Point Source (the page says both) |
| funding_source | none | `direct`: the revolving fund is federally capitalised, which the pages do not say per program |
| amount_min / amount_max | none | null (caps such as "$75,000" and "$50,000" are in the text, not a labelled field) |
| match_required | page text | `True` when a sentence states a match ("1:1 cash match requirement", "matching grant"); else null |
| match_pct | none | null |
| status | the cycle sentence | see status rules |
| opens_at / closes_at | the cycle sentence | full dates only (none on the survey day: "Oct. 30" has no year) |
| closes_at_text | the cycle sentence | verbatim: the first sentence (or heading) that says now accepting, a deadline, at any time, first come, an application period, one application per year, a notice of intent, or closed |
| rolling | the cycle sentence | `True` for "at any time" or "first come, first served"; else null |
| summary | first paragraph | the first paragraph of the content column |
| eligibility_text | labelled passages and applicant sentences | the paragraphs under a heading or bold label that mentions eligible applicants, eligible sectors, eligibility or now accepting, plus every sentence that says who may apply, can submit, can receive or is eligible to apply, one per line |
| eligibility_structured | Related Topics | `{"topics": ["clean water", "drinking water", ...]}` |
| applicant_types | eligibility_text | the shared tagger, sentence by sentence, negated sentences dropped |
| categories | Related Topics | each tag through the shared table; tags the table does not know are skipped (`finance`, `grants` are not topics): `clean water`, `drinking water`, `wastewater`, `stormwater`, `septic systems`, `non-point source`, `water quality financing` → water; `infrastructure`, `green infrastructure loans` → infrastructure |
| alns | none | always empty |

### Status rules

| The page says | Status |
|---|---|
| the cycle sentence says closed | closed |
| "now accepting", "at any time", "first come, first served" | open |
| a full due date on or after today | open |
| anything else (a Project Priority List cycle, "one application per state fiscal year", nothing) | unknown |

### What happens when a page leaves

`resolve_missing` is `unknown` without a request (a hand list). An unreadable page falls back to the stored copy.

## Decisions (defaults; override at review)

1. **A hand list of twelve pages.** The index is one page whose sections changed never in the survey window; a new
   program is a one-line addition with its kind.
2. **The kind comes from the index section**, not the title: "Asset Management Incentive Program" pays grants, "Project
   Planning Advances" are grants the index files under Grants.
3. **Related Topics are categories**: the agency tags every page; only tags the shared table knows count.
4. **"Now accepting" and "at any time" are open; a Project Priority List cycle is unknown.** The loan programs run on
   an annual Notice of Intent list the page describes without dates.
5. **Contact paragraphs are not stored**: a named officer with phone and e-mail on most pages.

## Known gaps

- Only one page states a deadline (CWQIG, "Oct. 30", no year); the rest state cycles in words or nothing.
- The revolving-fund loans are federally capitalised money the pages do not label as federal: `direct`.
- Septic Rehabilitation and the estuary loans tag no applicant from their text (property owners and private owners
  by the index section; "privately owned" and "property owners" are not applicant words the tagger knows).

## Verification

- `tests/test_de_dnrec.py` against `tests/fixtures/de_dnrec/` (the twelve pages, contact paragraphs and e-mails
  removed, written by `scripts/probe_de_dnrec.py`).
- Two live runs: all added, then 0 changed.
