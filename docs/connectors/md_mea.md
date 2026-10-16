# Maryland Energy Administration connector: site verification and field mapping

Milestone 7, connector 1. Live probe 2026-10-16. First SharePoint (mdgov theme) agency; the Drupal notes in
`maryland_drupal.md` do not apply here beyond the shared text helpers it lends (`clean`, `sentences`,
`applicant_types_for`, `funding_type_for`, the HTTP constants).

## Implemented (2026-10-16, same day)

`connectors/md_mea.py` follows this doc. Live run on the session database: 28 records (9 open, 1 forecasted, 14
closed, 1 exhausted, 3 unknown), as expected below; the second run reports no changes (the very first attempt died on a
30 s read timeout from one page, which the pipeline records as a failed run; the next attempt loaded everything). Five open records carry a
municipality tag and reach `v_municipal_page`: SolarAPP+ (closes 2026-11-18), Commercial & Community Buildings
(2026-12-09), Community EVSE (2026-12-09), Community Solar (2026-12-15), Energy Challenge (2026-12-02). Maryland's
open municipal count went from 6 to 11.

Two things the probe settled that the survey had not:

- **The HTML hash is unstable, the text hash is stable.** Cloudflare rewrites the `data-cfemail` attribute on every
  response, so two fetches of the same page differ in markup and agree in text. `content_hash` is over the cleaned
  text of the main section. Every page's probe line reads `text hash stable: True | markup identical: False`.
- **Labels are not reliably in one block.** SharePoint's editor nests a `<div>` per paragraph, so "Target Audience:"
  and its value often sit in the text a `<div>` has before its first child `<div>`. Reading each block's own text
  (minus nested blocks) finds every label; reading leaf blocks only lost the audience line on two pages.

Known gaps, all because the page does not say it the way the rules read:

- Solar Technical Assistance "provides technical assistance ... to state and local government entities" in a
  description sentence, not an applicant sentence, so it carries no tags. Jane E. Lawton moved to the Maryland Clean
  Energy Center on 2026-07-01 and its MEA page is a pointer: `unknown`, no tags.
- `\bindividuals?\b` in the shared keyword table matches "individual school facilities" (Decarbonizing Public Schools)
  and "the individual identified to receive funding" (Affordable Electrification Outreach). Both records are closed;
  the table is shared, so the fix (an adjective guard) waits for a case that surfaces.
- The FY27 General Notice of Upcoming Programs PDF is not parsed: `pdftotext` flattens its table into interleaved
  multi-line cells, and the program pages carry their own launch dates. Decision 7.

## Source

`https://energy.maryland.gov`, SharePoint on the state's `mdgov` theme, behind Cloudflare. No sitemap (404).
`robots.txt` disallows only `/_vti_bin/`, `/_layouts/`, `/_catalogs/`.

There is no single linked index. `/Pages/all-incentives.aspx` lists the 14 FY27 programs in five sector tables
(Program, Program Description) whose rows are unlinked. The five category pages link their programs:

| Index | Headings seen | Links |
|---|---|---|
| `/Pages/Renewables.aspx` | Grants, Tax Credits (two empty `<h3>`s between) | 16 |
| `/Pages/EnergyEfficiency.aspx` | none (one table) | 9 |
| `/transportation/Pages/incentives.aspx` | (excise tax credit and a rebate before the first heading), Grants & Loans, Archived Programs | 6 + 5 archived |
| `/Pages/resiliency.aspx` | none | 5 |
| `/Pages/Communities.aspx` | none | 6 |

Union after dropping off-site links (mva.maryland.gov), the news page and the EmPOWER fact page: 34 program paths,
6 of them 404 on the probe date (all five archived programs plus `/residential/Pages/incentives/CleanEnergyGrants.aspx`
and nothing else), 28 live records. Paths are linked in mixed case (`/residential/pages/...`,
`/business/pages/ResilientMaryland.aspx`); SharePoint serves them case-insensitively with no redirect, so
`source_id` is the lowercased path. One path carries a percent-escape, `/Pages/Commercial%26CommunityBuildingsGrantProgram.aspx`,
kept as linked.

Page skeleton (every page, verified on all 28 live program pages and the 5 indexes):

```html
<main id="mdgovMain">
  <section class="mdgov-section">
    <div id="ctl00_PlaceHolderMain_editmodepanel2"><h1>Maryland SolarAPP+ Implementation Grant Program</h1></div>
    <div id="ctl00_PlaceHolderMain_RichHtmlField1__ControlWrapper_RichHtmlField" class="ms-rtestate-field">
      <p><strong>Program Type:</strong> First-Come First-Served Grant</p>
      <p><strong>Target Audience:</strong> Maryland counties, cities, towns, and other Authorities Having Jurisdiction (AHJs) ...</p>
      <p><strong>Funding Opportunity Announcement Issue Date:</strong> July 1, 2026</p>
      <p><strong>Application Deadline:</strong> 3:00 PM ET, November 18, 2026 through the JotForm application portal. ...</p>
      <p><strong>Online Application Portal Status:</strong> Open to new applications</p>
      <p><strong>Anticipated Program Budget:</strong> MEA anticipates up to $3,800,000 will be available from the U.S. Department of Energy (DOE) State Energy Program ...</p>
```

Two other `.ms-rtestate-field` divs on each page are theme stubs under 220 bytes. Every page has
`<meta name="description">`. Response headers: `Last-Modified` is the same timestamp on every page (the CDN's), no
`ETag`, `Cache-Control: private, max-age=0`.

### Labels seen (28 pages)

| Kind | Label variants | Value shapes |
|---|---|---|
| status | `Online Application Portal Status`, `FY27 Online Application Portal Status`, `FY26 Program Status`, `Application Status` | `Open to new applications`, `OPEN to new applications.`, `Open to New Applications`, `Closed to New Applications`, `The application portal is currently CLOSED to new applications.`, `Closed` |
| deadline | `Application Deadline`, `Program Application Deadline`, `Anticipated Application Deadline`, `FY27 Application Deadline` | `3:00 PM ET, November 18, 2026 through the JotForm application portal. ...`, `December 9, 2026 - 3:00 PM Eastern Time`, `3:00 P.M. ET, Monday, February 11, 2026.`, `Stage 1: 3:00 PM Eastern Time December 02, 2026` (value in the next block), `December 31, 2025 – 5:00pm EST`, `Deadline Extended: Wednesday, November 19th at 5PM.` (no year), `None. The program remains open until funding is expended. ...`, `Applications are accepted on an ongoing basis until funding is fully awarded or until December 17, 2025 ...`, and on CI&A a budget paragraph with no date |
| launch | `Program Launch Date`, `Funding Opportunity Announcement Issue Date`, `FY27 Funding Opportunity Announcement Issue Date` | `September 9, 2026` |
| audience | `Target Audience`, `FY27 Target Audience`, `Eligible Applicants`, `Eligible entity types are` | prose; "Open (e.g. businesses, nonprofits, local governments, ...)" on the Energy Challenge |
| program_type | `Program Type`, `Type of Program`, `Type of Grant Program` | `First-Come First-Served Grant`, `Competitive Grant`, `Statewide Competitive`, `Rebate Program (Upfront Reservation Required).`, `Competitive Auction (closed bids)`, `Competitive Challenge` |
| (ignored) | `Anticipated Program Budget`, `Program Budget`, `FY26 Total Budget`, `Program Contact`, `Contact Information`, `Last Update to Total Budget Reserved`, `June 8, 2026 UPDATE` | |

Prose status sentences seen where there is no status line: `The Local Government Energy Modernization Program (L-GEM)
is CLOSED`, `Now Open! FY27 Commercial & Community Buildings Grant Program`, `The FY26 program is closed.`, `THE FY2026
MECHANICAL INSULATION GRANT PROGRAM IS NOW CLOSED AND IS NO LONGER ACCEPTING APPLICATIONS`, `**FY26 PROGRAM NOW
ACCEPTING APPLICATIONS**`, `The Fiscal Year 2027 (FY27) program is now open in the My MEA Application Portal`, `The
application JotForm Portal is now closed to new applications`, `PLEASE NOTE THAT DUE TO THE FY26 FUNDING DEPLETION, THE
APPLICATION PORTAL IS NOW CLOSED`, `THIS PROGRAM IS INACTIVE AS OF THE END OF CALENDAR YEAR 2024, AND IS NO LONGER
ACCEPTING APPLICATIONS, PER STATE LAW.`, `*FY26 Higher Education Clean Energy Grant Program is CLOSED *`.

## Enumeration and change detection

- `fetch()` GETs the five indexes (a non-200 aborts the run: without an index every program it lists would be marked
  missing), collects every on-site `.aspx` link in the body with the text of the nearest preceding heading, drops
  `SKIP_PATH` (news, facts, home, all-incentives) and the indexes themselves, and fetches the union. A 404 is skipped
  (dead index links are a fact of this site); other HTTP errors raise.
- Every page is fetched every run. `prior` is accepted and unused: no usable `Last-Modified`, no `ETag`. About 40
  requests at 0.3 s.
- The payload is `{url, title, description, main_html (the mdgov section), content_hash (text sha256),
  index: {index_path: heading}}`. The index map is stamped on every record, so a program moving under "Archived
  Programs" changes the record even if its page did not.
- Every enumerated page with an mdgov body is a record, labels or not (Jane E. Lawton is a pointer page: `unknown`).
- `resolve_missing`: refetch the page. 404 → `unknown`. Still there → what it says now, with no index entry. A
  de-listed page whose text did not change produces no change row; it is still visible in SQL as a record whose
  `last_seen` is older than the connector's last successful run.

## Field mapping

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `md_mea` |
| source_id | URL | lowercased path, no leading slash, fragment dropped, percent-escapes kept |
| name | `<h1>` in the edit-mode panel | cleaned, leading `FY27 ` / `FY25 ` stripped ("FY27 Commercial & Community Buildings Grant Program" → "Commercial & Community Buildings Grant Program"); `<title>` if there is no H1 |
| level / jurisdiction | constant | `state` / `MD` |
| administering_agency / agency_code | constant | `Maryland Energy Administration` / `MD-MEA` |
| funding_type | name, then the program_type line | `rebate` in the name → rebate; then the shared name keywords (tax credit, loan, voucher, grant); then the program_type label+value: rebate, tax credit, loan, grant, and Challenge / Prize / Auction → other; else null |
| funding_source / alns | hand map | SolarAPP+ is `pass_through` with ALN 81.041 (the page says DOE State Energy Program; listing verified on SAM.gov 2026-10-16). Maryland RISE says "federally-funded" without naming the program: direct. |
| amount_min / amount_max | none | null. "Anticipated Program Budget" is the program's pot, not an award size. |
| match_required | shared `match is (not) required` wording over the body | null on every page today |
| status | see decisions 1 to 4 | archived-only → closed; first status line (closed/inactive → closed, open → open); else closed prose (exhausted when the sentence blames funding), then open prose; a future launch date turns closed or undecided into forecasted; a deadline-only page is open while the deadline is ahead and unknown after; else unknown |
| opens_at | launch line, else "opens on <date>" prose | the first full date |
| closes_at | first deadline line | the first `Month D, YYYY` in the line's first sentence, times and weekdays around it ignored, ordinals stripped, no year → null; kept whatever the status |
| closes_at_text | status, deadline and launch lines | `Label: value` joined with `; ` |
| rolling | deadline line, open records only | `ongoing`, `remains open`, `until funding`, `first-come`, `rolling` → True |
| summary | `<meta name="description">` | as is |
| eligibility_text | audience lines + applicant sentences | `Label: value` for every audience line, then the body sentences matching `may apply`, `eligible applicants/entities/to apply`, `is/are open to`, `available to`, minus negated ones; page order; deduplicated |
| applicant_types | keyword tags over the same lines | shared table; `municipal` added for this connector |
| categories | constant + index | `energy` (source_code `mea`); plus `transportation` when the transportation index lists the page |

## Decisions

1. **The first status line wins; closed prose beats open prose.** MSAP carries its FY27 portal line ("Open to new
   applications") above an FY26 contractor-list line ("Application Status: Closed"); document order is the agency's
   own emphasis. Without a status line, "is CLOSED" / "no longer accepting" beats "Now Open" the way Commerce's rule
   does, because closed sentences are the ones MEA adds when a round ends.
2. **A funding-depletion closure is `exhausted`.** Commercial & Canopy Solar: "DUE TO THE FY26 FUNDING DEPLETION, THE
   APPLICATION PORTAL IS NOW CLOSED". DHCD's `fully spent|exhausted` rule, same spirit. The Energy Storage tax credit
   closed "PER STATE LAW" first and ran out of money second: closed.
3. **A stated future launch date makes a closed or undecided page `forecasted`**, the rule DHCD already applies to its
   "Opens" date. Megawatts for Maryland: portal "Closed to New Applications", FOA issue date October 26, 2026 →
   forecasted with `opens_at`. MEA's FOA issue date and launch date are the same day where both appear (Commercial &
   Community Buildings), so both labels feed `opens_at`.
4. **Deadline-only pages: open ahead of the deadline, `unknown` after.** The source says applications are due on a
   date; while that date is ahead it is taking applications. Once it has passed, the page is stale, not evidence of
   closing (Maryland RISE, FY25, deadline January 21, 2025), and `unknown` with `closes_at` kept lets the views drop it.
   One calendar comparison, recorded here; never a month without a year.
5. **Text hash, not markup hash**, because of Cloudflare's e-mail obfuscation. The record hash is still the change
   signal; `content_hash` is for the probe and for audit.
6. **Budgets are never amounts.** Every "Anticipated Program Budget" is the pot for the round.
7. **The FY27 General Notice PDF is not parsed.** Its table flattens badly and every launch date in it is also on the
   program page. Revisit only if a program is announced in the PDF before its page exists.
8. **Index enumeration stamps the index map on every record** (MHT's `listed_open` pattern) rather than storing the
   index page as a record: the pipeline normalizes every RawRecord into a Program, and additions and removals already
   surface as `added` and `missing`.
9. **No shared SharePoint base yet.** The pure helpers (`main_section`, `page_payload`, `leaf_lines`, `text_hash`,
   `source_id_for`, `canonical_url`, `fixture_name`) are module functions written to move. Extracted at DNR, the second
   mdgov site, the way `maryland_drupal.py` was extracted at Commerce.

## Expected result (October 2026)

28 records. Open (9): SolarAPP+ (2026-11-18), Commercial & Community Buildings (2026-12-09), Community EVSE
(2026-12-09), Community Solar (2026-12-15), Energy Challenge (2026-12-02), Maryland Solar Access (2027-05-31),
Residential EVSE Rebate (2027-05-31), Energy Storage (2027-05-31), Solar Technical Assistance (rolling). Forecasted
(1): Megawatts for Maryland (opens 2026-10-26, closes 2026-11-30). Exhausted (1): Commercial & Canopy Solar. Unknown
(3): Jane E. Lawton, Commercial & Industrial Grant, Maryland RISE. Closed (14): the rest, including L-GEM and
Residential Energy Equity, both municipal programs that will show in the diff when their FY27 rounds open.

Municipal open rows: the five grants named in Implemented. L-GEM (closed, "Only incorporated towns, cities, and
counties of Maryland may apply") is the one to watch.

## Fixtures

`tests/fixtures/md_mea/`: `index__*.json` for the five indexes (url + the mdgov section, so the index parser runs
offline); `govt__pages__solarapp` (status line open, deadline, counties/cities/towns, DOE pass-through),
`pages__commercial-26communitybuildingsgrantprogram` ("Now Open!" prose, launch date, audience split over nested divs,
`%26` in the path), `pages__communityevse` (status line, "local governments", transportation index),
`govt__pages__smartenergycommunities` (L-GEM: "is CLOSED" prose, "may apply" sentence, past deadline kept),
`business__pages__resilientmaryland` ("FY26 Program Status" line), `pages__energy-storage-grant-program` (labels with
the value in the next cell, "now open" prose), `residential__pages__incentives__maryland-solar-access-program` (two
fiscal years; first status line wins), `govt__pages__solartechnicalassistanceprogram` (rolling, no tags),
`govt__pages__janeelawton` (pointer page, unknown), `pages__megawattsformaryland` (closed line + future FOA date →
forecasted), `business__pages__commercial-solar` (funding depletion → exhausted). Written by
`scripts/probe_maryland_sharepoint.py md_mea`.
