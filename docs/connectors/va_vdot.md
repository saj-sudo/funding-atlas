# Virginia VDOT connector (`va_vdot`): source, raw data and field mapping

Milestone 11, Virginia's fourth agency (the municipal five, decision 2026-11-03). Written 2026-11-03 from a read of
VDOT's Local Assistance Division pages, before the parser. Revenue Sharing, State of Good Repair, Transportation
Alternatives, access roads, the Urban program: the money a Virginia town's public works director applies for.

## Implemented (2026-11-03, same day)

`connectors/va_vdot.py` follows this doc. First live run on a fresh database: 6 records added, 0 errors; second run 0
changed. Every record is `unknown`, as expected: three carry a cycle sentence (SGR's October-to-December period, the
Urban program's February 1st change requests, Revenue Sharing's "biennial"), none a full date. All six tag municipality
and county from the "For localities" section and the card blurbs. The Virginia page: unchanged (0 open municipal rows,
nothing between rounds from VDOT). Found while writing the parser: the site's editor splits words across spans
("appl", "ications"), so text is joined without separators.

## The source

`https://www.vdot.virginia.gov` (the old `virginiadot.org` redirects here) is a custom site whose `robots.txt` names
only Googlebot rules for asset and archive directories; nothing for other agents. The Local Assistance Division page,
`https://www.vdot.virginia.gov/doing-business/for-localities/local-assistance/`, sits under the site's "For
localities" section and lists its programs as resource cards:

```html
<div class="resource-card"><span class="resize-check"><img ... aria-hidden="true" />
  <a href='/doing-business/for-localities/local-assistance/revenue-sharing/'><h3>Revenue sharing</h3></a>
  <p>VDOT administers the Revenue Sharing Program, in cooperation with participating localities. The program provides additional funding for use by a county, city, or town to construct or improve the highway systems.</p>
</span></div>
```

Eight cards on 2026-11-03; six are programs (Access road programs, Other programs, Revenue sharing, State of Good
Repair, Urban programs, Transportation alternatives) and two are process pages (Locally administered projects,
Training and outreach), excluded by slug. The index is read every run (a card VDOT adds appears on the next run) and
then each program page: seven GETs, 0.3 s apart.

### A program page

`<main id="main-content-container">` with `h1.pagetitle`, `h2`/`h3` section headings and paragraphs; the site's
editor splits sentences across many inline spans, so text is read with spaces and collapsed. What the six pages said:

| Page | Cycle sentence | Applicant sentence |
|---|---|---|
| Revenue sharing | "Funding applications are biennial and must be submitted online by accessing the CTB's Smart Portal." | the card: "funding for use by a county, city, or town"; the page: "provides funding localities for the construction and/or improvement of highway systems" |
| State of Good Repair | "The application period typically opens the first week of October and closes by mid-December each year." | "Virginia localities must submit applications for SGR Primary Extension through the SMART Portal."; "A notification of the application period is sent to eligible localities each year." |
| Transportation Alternatives | "FY27-28 Transportation Alternatives Application Timeline" (a link title); "... pre-application cycle" | "SRTS infrastructure projects and non-infrastructure programs are eligible to apply for funding through Virginia's competitive ..." |
| Urban program | "Change requests are due February 1st to be included in the following fiscal year." | "A municipality qualifies for the urban program if it meets any of the following criteria: All cities, regardless of population ..." |
| Access road programs | none | none on the page (three programs described: Economic Development, Airport, Recreational Access) |
| Other programs | none | "Section 33.2-366 of the Code of Virginia sets out the process for determining the amount that the state pays these counties" |

No page states a full date; the cycles are "biennial", "first week of October", "February 1st".

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `va_vdot` |
| source_id | card link | the last path segment (`revenue-sharing`, `urban-program`) |
| source_url | card link | `https://www.vdot.virginia.gov<path>` |
| external_number | none | null |
| name | page `h1` | as written (`Revenue sharing`, `State of Good Repair Program`); the card's `h3` when the page has none |
| level / jurisdiction | constant | `state` / `VA` |
| administering_agency | constant | `Department of Transportation` |
| agency_code | constant | `VA-VDOT` |
| funding_type | name | the shared keyword; else null (revenue sharing is a match, SGR an allocation, TAP a grant: the page does not label it) |
| funding_source | none | `direct`: the "Other programs" page lists federal and state programs together and no page labels its own source |
| amount_min / amount_max / match_required / match_pct | none | null |
| status | the cycle sentence | `open` only with a full date on or after today; else unknown. No page had one |
| opens_at / closes_at | the cycle sentence | full dates only; none on the survey day |
| closes_at_text | the cycle sentence | verbatim: the first sentence that mentions an application period, applications being due, accepted or submitted, a deadline or a cycle |
| rolling | none | null |
| summary | page | the first paragraph under the `h1` |
| eligibility_text | card and page | `For localities (VDOT section): <card blurb>` then every page sentence that says who is eligible, who qualifies or names localities, counties, cities or towns, one per line. Decision 2 |
| eligibility_structured | none | null |
| applicant_types | eligibility_text | the shared tagger, sentence by sentence, negated sentences dropped |
| categories | none | none (the TX rule; "transportation" is the agency's name, not a field) |
| alns | none | always empty |

### Status rules

`unknown` unless the cycle sentence carries a full date on or after today (`open`) or says a round is closed
(`closed`). On 2026-11-03 every record is `unknown` with its cycle sentence kept as text.

### What happens when a card leaves

`resolve_missing(source_id)` returns `unknown` without a request: a card VDOT drops is not a closure it stated.

### Change detection

The hash is over the Program; seven pages, every run. A program page that cannot be read falls back to the stored
copy; an unreadable index aborts the run.

## Decisions (defaults; override at review)

1. **The index cards are the enumeration; two process cards are excluded by slug.** Locally administered projects and
   Training and outreach are how-to pages, not funding.
2. **The section name and the card blurb are applicant text.** The pages sit under VDOT's own "For localities" section
   and each card says whom the program funds ("for use by a county, city, or town"); the pages themselves describe
   process more than eligibility. Both are the agency's words about who the money is for and both go through the
   tagger with the phrase as source_code. The access roads and "Other programs" pages still name no applicant beyond
   the section, so they tag municipality and county from `localities` alone.
3. **No category and `direct`**: the pages label neither topic nor source (TX rule).
4. **Contact blocks are not read**: a named engineer on every page.

## Known gaps

- Every record is `unknown`: the cycles are stated as seasons and weekdays, never as dates. The between-rounds group
  gets nothing from VDOT until a page states a date.
- (Fixed 2026-11-11, roadmap 10.6.) The access roads page is three programs and three records: Economic Development
  Access keeps the page's id (`access-roads-programs`, so the stored record of the whole page becomes it rather than
  lingering as an `unknown` no run returns), Airport Access and Recreational Access are `access-roads-programs#...`.
- TAP, FLAP and SGR's federal share are `direct` because no page labels its source.

## Out of scope

The SMART Portal (login), the program guidelines PDFs, the Locally Administered Projects manual, urban inventory data.

## Verification

- `tests/test_va_vdot.py` against `tests/fixtures/va_vdot/` (the index and six program pages, contact blocks removed,
  written by `scripts/probe_va_vdot.py`): card parsing and the exclusions, the split-span text, the cycle sentence,
  the applicant lines and tags, `fetch` (index abort, page fallback), `resolve_missing`.
- Two live runs: all added, then 0 changed.
