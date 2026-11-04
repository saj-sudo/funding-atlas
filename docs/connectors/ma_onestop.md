# Massachusetts Community One Stop for Growth connector (`ma_onestop`): source, raw data and field mapping

Milestone 12.3, the first state of "the rest of the states" (decision 2026-11-03). Written 2026-11-04 from a read of
the One Stop page and its fourteen program pages, before the parser. The One Stop is the Commonwealth's single
application for its community economic development and housing capital grants: MassWorks, the Downtown Initiative,
Vacant Storefronts, the Rural Development Fund, Seaport, Housing Choice, Community Planning, HousingWorks, the MBTA
Communities Catalyst Fund and MassDevelopment's five. A Massachusetts town's planner applies for all of them once a
year through one portal with one deadline, which is what makes a connector cheap here: one round for fourteen records.

## Implemented (2026-11-04, same day)

`connectors/ma_onestop.py` follows this doc. First live run against the published database: 14 added in 7 seconds
(the index, nine mass.gov pages, the MassDevelopment page once), 0 errors; second run 0 changed. Every record is
`closed` on the round's Full Application deadline (2026-06-03), with `opens_at` 2026-01-23 and the deadline line
verbatim. Seven tag `municipality` from their own page (Downtown Initiative, Vacant Storefronts, Rural Development
Fund, Housing Choice, HousingWorks, MBTA Communities Catalyst Fund; Seaport's "coastal communities are eligible to
apply" is kept as text and tags nothing, because `communities` is not an applicant word). The Massachusetts page: 3
agencies, 14 programs, 0 open, 6 between rounds (the six municipal rows, shown with the June deadline until the next
round opens). Found while writing the parser: the One Stop page writes its program list as `<p><a>` pairs under each
agency `h3`, not as a list, and its Key Dates lines end in zero-width spaces.

## The source

`https://www.mass.gov/info-details/community-one-stop-for-growth` (Drupal 11; `robots.txt` blocks SemrushBot and the
usual Drupal paths, nothing else). The page is the index and the round in one:

- under the `h2` "One Stop Programs", three `h3` agencies (Executive Office of Economic Development; Executive Office
  of Housing and Livable Communities; MassDevelopment Finance Agency), each followed by one `<p><a>` per program.
  Fourteen links on 2026-11-04 (the overview paragraph says "12"; the list is the fact). Nine are mass.gov pages in
  three templates (`/orgs/massworks`, `/info-details/<slug>`, `/how-to/<slug>`); five are anchors on one
  massdevelopment.com page (`/products-and-services/community-development/grant-programs/#<id>`), where each program is
  a `<section id="<id>">` with an `h2`, paragraphs and lists.
- under the `h2` "FY27 Round of the One Stop: Key Dates", the round's dates as `p` and `li` lines with a bold label
  each: "FY26 Round of One Stop Opens : January 23, 2026", "Full Application Submission Period : May 4, 2026 – June 3,
  2026", "June 3, 2026 – Full Application Submission Deadline", webinars, office hours, "Anticipated Notification of
  Award - October 2026". The heading says FY27 and every date says FY26; the connector reads the dates and never the
  heading. The lines carry zero-width spaces (U+200B), stripped before anything is read.

```html
<h2 class="ma__comp-heading" id="one-stop-programs">One Stop Programs</h2>
<h3>Executive Office of Economic Development</h3>
<p><a href="/orgs/massworks">MassWorks Infrastructure Program</a></p>
<p><a href="/info-details/rural-development-fund">Rural Development Fund</a></p>
...
<h3>MassDevelopment Finance Agency</h3>
<p><a href="https://www.massdevelopment.com/products-and-services/community-development/grant-programs/#underutilized-properties-pro">Underutilized Properties Program</a></p>

<h2 class="ma__comp-heading" id="fy27-round-of-the-one-stop-key-dates">FY27 Round of the One Stop: Key Dates</h2>
<p><strong>FY26 Round of One Stop Opens</strong>: January 23, 2026&#8203;</p>
<p><strong>Full Application Submission Period</strong>: May 4, 2026 – June 3, 2026&#8203;</p>
```

A program page on mass.gov is read from its `main` element's outermost `.ma__rich-text` blocks only: that is the
editor's prose (the `info-details` template's sections, the `how-to` template's "What you need" and "More info", the
`orgs` template's intro). Everything else on those pages (the table of contents, contact cards and contact lists,
related links, press teasers, the feedback form) is outside those blocks and never read. A MassDevelopment program is
read from its own `section` on the one grant-programs page, fetched once a run.

What the pages said on 2026-11-04:

| Program | Agency | Who applies (the page's words) |
|---|---|---|
| MassWorks Infrastructure Program | EOED | "provides grants to communities" |
| Massachusetts Downtown Initiative Capital Program | EOED | "municipalities and other public entities are encouraged to submit Expressions of Interest" |
| Massachusetts Vacant Storefront Program | EOED | "All Massachusetts municipalities are eligible to submit an application" |
| Rural Development Fund | EOED | "Eligible municipalities and other public entities are invited to submit expressions of interest" |
| Seaport Economic Council Grant Program | EOED | "All 78 Massachusetts coastal communities are eligible to apply" |
| Housing Choice Grant Program | EOHLC | "a community must have a current Housing Choice Community ... Designation. Other eligible entities must serve a currently designated community" |
| Community Planning Grant Program | EOHLC | the page names no applicant |
| HousingWorks Infrastructure Program | EOHLC | "a competitive grant open to municipalities" |
| MBTA Communities Catalyst Fund | EOHLC | "is available to municipalities that have received a district compliance determination letter" |
| Underutilized Properties, Site Readiness, Brownfields Redevelopment Fund, Real Estate Services Technical Assistance, TDI Equity Investment | MassDevelopment | the sections describe projects, not applicants |

## Field mapping (Program model in pipeline/models.py)

| Program field | Source | Rule |
|---|---|---|
| source_connector | | `ma_onestop` |
| source_id | the link | the last path segment of a mass.gov link (`massworks`, `rural-development-fund`, `housing-choice-grant-program`); `massdev#<fragment>` for a MassDevelopment anchor |
| source_url | the link | absolute, fragment kept |
| external_number | | null |
| name | the link text | whitespace normalized (the page's own `h1` can differ: "MassWorks") |
| level / jurisdiction | | `state`, `MA` |
| administering_agency | the `h3` above the link | as written |
| agency_code | the `h3` | `MA-EOED`, `MA-EOHLC`, `MA-MASSDEV`; an `h3` not in that table gives null |
| funding_type | name | the shared keyword rule, else `grant` (the One Stop is a grant application; "TDI Equity Investment Program" keeps whatever the keyword rule says, else `grant` too, because the One Stop awards it as a grant round) |
| funding_source | page text | `pass_through` when the page says federal funds or a federal program, else `direct` (state capital budget; no page said federal on 2026-11-04) |
| amount / match | page text | amounts null; `match_required` true when the page says a match is required, else null |
| status | the index's Key Dates | one round for every program: `open` while the Full Application deadline is today or ahead, `forecasted` when the round's open date is still ahead, `closed` once the deadline has passed, `unknown` when the section carries no deadline |
| opens_at / closes_at | Key Dates | the date on the "Opens" line; the last date on the "Full Application Submission" line |
| closes_at_text | Key Dates | the Full Application Submission line verbatim |
| rolling | | null |
| summary | page | the first paragraph of the program's prose |
| eligibility_text | page | the lines under a label matching `eligib` or `who may/can apply`, plus the sentences that say who may apply (see the regex in the module), one per line |
| eligibility_structured | index | `{"one_stop_round": "<the Key Dates heading>"}`, the round the dates belong to by the page's own name |
| applicant_types | eligibility lines | the shared tagger, negated sentences dropped |
| categories | the `h3` | EOHLC -> `housing`; EOED and MassDevelopment -> `infrastructure` (economic development is infrastructure everywhere, decision 10.1); `source_code` the agency name |
| alns | | none |

### Status rules

| Key Dates says | Status |
|---|---|
| a Full Application Submission line with a date today or ahead, and an Opens date ahead | forecasted |
| a Full Application Submission line with a date today or ahead | open |
| a Full Application Submission line with a past date | closed (the between-rounds group shows it for 15 months) |
| no Full Application Submission line, or no date on it | unknown |

The round sentence is the index's, so every program carries the same status: the One Stop is one NOFA. A program
page's own dates (the Rural Development Fund's "Application Deadline: Wednesday, June 3, 2026") are not read for
status; they repeat the round.

### What happens when a program leaves

The index is read every run and a program no longer linked is `resolve_missing` -> `unknown` (the One Stop's program
list has changed between rounds before: MassWorks joined in FY22). A program page that cannot be read keeps its stored
page with the fresh round facts stamped on; with no stored page the record still exists (the index listed it) with the
round's status and no applicant lines.

## Decisions (defaults; override at review)

1. One connector for the One Stop, not one per agency: the application, the deadline and the index are one. The
   agency is a field.
2. Status from the index's dates, never from the heading: "FY27 Round ... Key Dates" over FY26 dates is the page's
   own contradiction; dates are facts, a heading is a label.
3. The Full Application deadline is the deadline. The Expression of Interest deadline (the same day in FY26) is an
   optional step and is not read.
4. MassDevelopment's five are records of this connector, not of a MassDevelopment connector: the One Stop lists them
   and awards them through its round. Their page is fetched once a run.
5. `communities` alone is not an applicant word (the tagger does not know it either); the applicant regex needs an
   eligibility verb beside it ("are eligible to apply", "open to", "is available to", "provides grants to").
6. Categories by agency, not by program text: the One Stop's own grouping is by agency, and the three agencies map
   cleanly to housing and infrastructure.

## Known gaps

- Community Planning Grant Program names no applicant on its page; its guidelines PDF would. Hand quote when a town asks.
- Seaport Economic Council: "All 78 Massachusetts coastal communities are eligible to apply" tags nothing; whether
  `coastal communities` should tag a municipality is a shared-tagger question for a measured session (10.x), not this one.
- The MassDevelopment sections describe what a good project is, not who applies; same remedy.
- Fourteen records against one date means the Massachusetts page moves fourteen rows at once on the day the round opens.

## Verification

`tests/test_ma_onestop.py` against `tests/fixtures/ma_onestop/` (the index, the nine mass.gov pages and the
MassDevelopment page, scrubbed of scripts, SVG, contacts and the feedback form by `scripts/probe_ma_onestop.py`).

## Live runs

| Run | Date | Result |
|---|---|---|
| first | 2026-11-04 | fetched 14, added 14, changed 0, missing 0, 7 seconds |
| second | 2026-11-04 | fetched 14, added 0, changed 0, missing 0 |
