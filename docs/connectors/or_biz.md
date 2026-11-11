# Business Oregon connector (`or_biz`): source, raw data and field mapping

Milestone 12.3b, the second state of "the rest of the states" (decision 2026-11-03). Written 2026-11-04 from a read of
the Programs index and thirteen program pages across its topics, before the parser. Business Oregon is the state's
economic development agency and runs the programs an Oregon city or county applies to for infrastructure money: CDBG,
the Special Public Works Fund, the Levee grant, brownfields, broadband, fairgrounds, plus the business finance,
incentives, innovation and arts programs the same page lists. The index is one page; every program is one page of
the same shape; most programs state no round, so most records are `unknown` with the cycle sentence kept, which is
the honest reading the roadmap asked for (12.3 Oregon: "an index connector whose rows are mostly `unknown` with
applicants from prose").

## Implemented (2026-11-04, same day)

`connectors/or_biz.py` follows this doc. First live run against the published database: 99 added in 86 seconds (the
index plus 99 pages at 0.3 s apart), 0 errors; second run 0 changed. The first run read "No Longer Accepting
Applications" (Aquifer Recharge) as open, because the default table checks the open wording first; this connector's
`OPEN_RE` now refuses "no longer", "not" and "stopped" before "accepting", a third run moved that one record to
closed, a fourth changed nothing. Stored: 85 `unknown` (26 of them with a cycle sentence kept), 6 `open` (Levee and
Marine Navigation year-round and rolling; Seismic Rehabilitation, the Venture Fund, Arts Career Opportunity, and
Industrial Development Bonds whose timeline says "November 2025: Begin accepting applications"), 8 `closed`; 13
records tag a municipality or county; 26 carry the infrastructure category from their topic. The Oregon page: 1
agency, 99 programs, 1 open municipal row (the Levee Project Grant Fund), 0 between rounds. Found while writing the
parser: SharePoint wraps the page in a `<form>` and nests `h2` inside `p`, the index spells one program "ndustrial
Development Bonds" (kept as the source writes it), and "contact your Regional Development Officer" is prose, so only
an address or a phone number marks a contact line.

## The source

`https://www.oregon.gov/biz/programs/` (SharePoint; `robots.txt` disallows `_layouts`, `_vti_bin`, the search pages
and the style library, nothing under `/biz/programs/`). The page holds two views of one list inside its rich-text
field: `#programAlpha` (alphabetical, 95 links on 2026-11-04) and `#programTopic` (eight topic `h2`s: Arts and
Culture, Business Finance, Business Incentives, COVID-19 Response Programs, Global Trade, Infrastructure and Land
Programs, Innovation & Entrepreneurship, Other Business Services; 80 links, 78 unique). The union, on the agency's
own host under `/biz/`, is 99 programs; the topic view gives 76 of them a topic. Two links go to other hosts (the
state art collection, the Arts Commission's own site) and are left out.

```html
<div id="programTopic" class="programTabContent">
  <div class="block"><h2>Infrastructure and Land Programs</h2>
    <ul><li><a href="/biz/programs/CDBG/Pages/default.aspx">Community Development Block Grants (CDBG)</a></li> ...
```

A program page is three SharePoint rich-text fields inside `main`: an intro (`RichHtmlField11`, a paragraph), a
sidebar (`RichHtmlField12`, "Additional Resources": documents, contacts; never read) and the body (`RichHtmlField1`)
with the agency's own headings, most often "Who is Eligible?", "How Does Funding Work?" and "What is the Application
Process?", each with paragraphs and lists. SharePoint nests the headings inside paragraphs and repeats them as bold
paragraphs, so each block's own text is read and a repeat of the heading is dropped. The page carries two `h1`s
(the site section and the program); the index link text is the name.

```html
<div class="ms-rtestate-field" id="...RichHtmlField1__ControlWrapper_OregonRichHtmlField">
  <h2>Who is Eligible?</h2>
  <p>-Municipalities;</p>
  <p>-Corporations or companies for drainage or flood control organized under ORS chapter 554; and</p>
  ...
  <h2>What is the Application Process?</h2>
  <p>Applications are accepted year-round based on funding availability. ...</p>
```

What the thirteen sampled pages said on 2026-11-04:

| Program | Topic | Round sentence | Who applies (the page's words) |
|---|---|---|---|
| CDBG | Infrastructure and Land | "February 1–April 30, applications accepted." (two windows a year, no year stated) | "Non-metropolitan cities and counties in rural Oregon can apply ... Oregon tribes ..." |
| Levee Project Grant Fund | Infrastructure and Land | "Applications are accepted year-round based on funding availability." | "-Municipalities; -Corporations or companies for drainage or flood control ...; -For-profit or nonprofit entities and individuals ..." |
| County Fairgrounds Funding | Other Business Services | none ("The award decisions for this funding opportunity have been decided.") | none |
| Business Expansion Program | Business Incentives | none | "A company must plan ..." |
| Brownfields | Infrastructure and Land | none | "available to provide financing ..." |
| Governor's Strategic Reserve Fund | Business Incentives | none | none |
| Commercialization Gap Fund | Innovation | none (portfolio lists) | none |
| Aggie Bond | Business Finance | none | "Be an Oregon resident; Have a net worth of no more than $750,000; ..." |
| Housing Infrastructure Support Fund | (alphabetical only) | "We're currently not accepting any applications at the moment." | none |
| Broadband Deployment Program | (alphabetical only) | "Online Application (Deadline April 25, 2024)" | "Partnerships between eligible applicants" |
| SBMA (CDBG-CV) | (alphabetical only) | "This application period for this program is now closed." | "Was in business prior to March 8th, 2019 ..." |
| Regionally Significant Industrial Areas | Infrastructure and Land | "The program is no longer accepting nominations ..." | none |
| Arts Build Communities | Arts and Culture | "Applications must be submitted ... no later than 5:00 pm on the deadline date" | "Be a unit of municipal government ... nonprofit ... school ... tribe" |

## Field mapping (Program model in pipeline/models.py)

| Program field | Source | Rule |
|---|---|---|
| source_connector | | `or_biz` |
| source_id | the link | the page path under `/biz/`, lowercased, without `/Pages/default.aspx`: `programs/cdbg`, `programs/bdp/dctp`, `aboutus/artscommission/grants/for-organizations/arts-build-communities` |
| source_url | the link | absolute, as the index writes it |
| external_number | | null |
| name | the link text | whitespace normalized; the alphabetical view's wording when a program is in both views |
| level / jurisdiction | | `state`, `OR` |
| administering_agency / agency_code | | "Business Oregon (Oregon Business Development Department)", `OR-BIZ` (the Arts Commission's grants are listed by the same page under the same agency) |
| funding_type | name | the shared keyword rule (`grant`, `loan`, `tax credit`, `bond`), else null: the page lists services and designations beside grants, so no default |
| funding_source | page text | `pass_through` when the page says federal funds, HUD, a U.S. Department, ARPA or the American Rescue Plan; else `direct` |
| amount / match | page text | amounts null (the dollar lines are per-category limits, not a range); `match_required` true when the page says a match is required |
| status | the round sentence | the hand-list default table (`HandListConnector.status_for`) with this connector's `OPEN_RE` and `CLOSED_RE`: accepting with a date -> open while the date is ahead; "accepted year-round" or "rolling" -> open and rolling; "not accepting", "no longer accepting", "is now closed", "closed for applications" -> closed; else unknown |
| closes_at | the round sentence | its last date (a 2024 deadline on a page that says nothing else gives a past `closes_at` and `unknown`) |
| closes_at_text | | the round sentence: the table's pick, else the first prose sentence that states a cycle (`applications accepted`, `application period/round/window/cycle`, `deadline`, `are due`), never a heading |
| rolling | the round sentence | from the table |
| summary | page | the first paragraph (the intro field's) |
| eligibility_text | page | the blocks under a label matching `who is eligible`, `eligible applicants` or `eligibility` up to the next label, plus the sentences that say who may apply (`eligible applicants`, `may apply`, `are eligible`, `eligible to apply`, `is available to`, `open to`) |
| eligibility_structured | index | `{"topic": "<the topic h2>"}` when the topic view lists the program |
| applicant_types | eligibility lines | the shared tagger, negated sentences dropped |
| categories | the topic | the shared table (`infrastructure and land programs` -> `infrastructure`, added 2026-11-04); the other seven topics name none of our categories and give no tag; `source_code` the topic |
| alns | | none |

### Status rules

| The round sentence says | Status |
|---|---|
| accepting applications, applications are open / being accepted, with a date ahead | open |
| the same with no date, or "accepted year-round" / "on a rolling" | open (rolling when it says so) |
| "not accepting", "no longer accepting", "is now closed", "closed for applications" | closed |
| awards have been announced | closed |
| a cycle sentence only (two windows a year with no year; a dated deadline alone) | unknown, sentence kept |
| nothing | unknown |

"Applications that meet program requirements are accepted for further review" (Arts Build Communities) and
"Applications are open to public comments and challenges" (Broadband Deployment) are not open statements; the
connector's `OPEN_RE` excludes both shapes.

### What happens when a program leaves

The index is read every run; a program no longer linked is `resolve_missing` -> `unknown`. A page that cannot be read
keeps its stored page; with no stored page the record still exists with no round and no applicants.

## Decisions (defaults; override at review)

1. The whole Programs page, not the municipal subset: the agency's own index is the listing, and the navigator's
   tiers decide what a town sees. Business incentives and arts grants are records too (`unlikely` on the Oregon page).
2. One agency for every row, the Arts Commission included: the index is Business Oregon's and the commission sits
   inside the department.
3. `unknown` is the common status and that is the product: the roadmap's Oregon item asked for honest coverage of a
   state whose pages seldom state a round. The cycle sentence is kept so a reader sees "February 1–April 30" even when
   no year is stated.
4. No funding-type default: the page lists designations (Enterprise Zones), services (COBID) and funds alike.
5. The alphabetical view's title wins over the topic view's where they differ (the alphabetical list is the fuller
   one; 23 programs appear there only, 6 in the topic view only).

## Known gaps

- (Fixed 2026-11-11, roadmap 10.6.) "Be an Oregon resident" (Aggie Bond) tagged a household and "150 percent of the
  state or county average wage" (BEP; the county came from the wage statistic, not "in the county") and "the county's
  median farm size" (Aggie Bond) tagged a county. A residency condition and a county statistic no longer tag; both
  records now carry no applicant tag, which is what their pages say about governments.
- 76 of 99 programs have a topic; the 23 alphabetical-only ones (broadband, housing infrastructure, CHIPS) have no
  category tag.
- (Fixed 2026-11-11, roadmap 10.6.) CDBG states two windows a year with no year on them ("February 1–April 30,
  applications accepted", "July 1–September 30, applications accepted"). Read for the run date's year: inside a window
  it is `open` to the window's end; between windows `closed` at the last window's end, so it sits in the between-rounds
  group. The page's "until all funds available for the year have been obligated" is kept in the text, not read.

## Verification

`tests/test_or_biz.py` against `tests/fixtures/or_biz/` (the index and thirteen program pages, scrubbed by
`scripts/probe_or_biz.py`; `--all` reads every program without saving).

## Live runs

| Run | Date | Result |
|---|---|---|
| first | 2026-11-04 | fetched 99, added 99, changed 0, missing 0, 86 seconds |
| second | 2026-11-04 | fetched 99, added 0, changed 0, missing 0 |
| third (after the `OPEN_RE` guard) | 2026-11-04 | fetched 99, changed 1 (Aquifer Recharge: open -> closed) |
| fourth | 2026-11-04 | fetched 99, added 0, changed 0, missing 0 |
