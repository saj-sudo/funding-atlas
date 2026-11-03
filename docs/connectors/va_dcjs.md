# Virginia DCJS connector (`va_dcjs`): source, raw data and field mapping

Milestone 11, Virginia's first agency (decision 2026-11-03: the municipal five in a state with no central index).
Written 2026-11-03 from the Mid-Atlantic survey (`docs/surveys/mid_atlantic.md`), which called DCJS "the one structured
thing in Virginia", before the parser. Law enforcement, courts, juvenile justice and victim services: the Virginia
cousin of Maryland's GOCPP gap, and the state's "599" aid to localities with police departments lives here.

## Implemented (2026-11-03, same day)

`connectors/va_dcjs.py` follows this doc. First live run on a fresh database: 59 records added in 45 seconds (all
closed on their due dates, 2024-10-18 to 2026-10-13; 58 grants and 1 loan by title keyword), 0 errors. Second run: 0
changed, 0 missing. 20 of 59 pages carry a labelled eligibility passage, 15 of them tag an applicant, 12 a municipality
and county (599, School Safety Officer, the JJDP rounds, Combating Hate Crimes, Byrne JAG for units of local
government, Operation Ceasefire, Unmanned Aircraft, Accreditation Enhancement), 6 a nonprofit. The Virginia page shows
0 open municipal rows and **10 between rounds**, the first state page the between-rounds group fills from its own
connector alone. `localities` entered the shared tagger here; on every stored record it moves three California AHSC
rounds, correctly.

## The source

The Department of Criminal Justice Services (DCJS) runs a Drupal 10 site, `https://www.dcjs.virginia.gov`, with a
standard Drupal `robots.txt` (nothing under `/grants` is disallowed; the agent is on no list). Pages used:

| Page | What | Fetches per run |
|---|---|---|
| `/grants` | the "Current Funding Opportunities" view: one `table.usa-table`, 59 rows on 2026-11-03, no pager (`?page=1` answers the same table) | 1 |
| `/grants/programs/<slug>` | one program page per row: a body of prose, a "Grant Program Details" block with three dates, a contact block, guideline attachments | 58 |

About 60 requests a run, 0.3 s apart, under a minute. Server-rendered, no session, no query form. There is no
archive listing (`/grants/archive`, `/grants/past-funding-opportunities` are 404; `/grants/programs` is a user-guide
page): a row leaves the view on its Archive Date, which the program page states.

**"Current" does not mean open.** On 2026-11-03 every one of the 59 rows had a due date in the past (2024-10-18 to
2026-10-13): the view holds a round from its posting until its archive date, one to three years later. The list is
the recent history of the office, which is what the between-rounds group needs (the 599 recertification, the school
safety and JJDP rounds recur every year), and status comes from the due date, never from being listed.

### The view

```html
<table class="usa-table cols-3"><thead><tr><th>Title</th><th>Application Due Date</th><th>Date Posted</th></tr></thead>
<tbody><tr>
  <td class="views-field views-field-title"><a href="/grants/programs/cy-2027-2029-virginia-opioid-use-reduction-and-jail-based-substance-use-disorder">CY 2027-2029 Virginia Opioid Use Reduction and Jail-Based Substance Use Disorder Treatment and Transition Fund Grant Program</a></td>
  <td class="views-field views-field-field-application-due-date"><time datetime="2026-10-13T16:00:00Z">10/13/2026 - 12:00</time></td>
  <td class="views-field views-field-field-date-posted"><time datetime="2026-09-11T12:00:00Z">11 September, 2026</time></td>
</tr>
```

Every row has a link and both `<time datetime>` values (ISO, UTC). The slug (the last path segment) is the key; one
slug appeared twice in the 59 rows on the survey day (58 distinct pages), and the first row is kept. The page also
carries a "Grant Awards Approved by the CJSB" block (past awards, not opportunities) and is not read.

### A program page

The node body is `#block-uswds-base-subtheme-content .field--name-body` (the site's mega menu also uses
`field--name-body`, inside the header, so the selector is anchored on the content block). The body is prose: a
paragraph saying DCJS "is accepting applications through the On-line Grants Management System (OGMS)", a purpose
paragraph, and on 20 of 59 pages a labelled eligibility passage, as a heading (`Eligibility`, `Applicant
Eligibility`, `Eligible Applicants`) or a bold run opening a paragraph (`Eligible Applicants: This funding
opportunity is open to all Virginia units of local government.`). Examples on 2026-11-03:

- "This funding opportunity is available to local units of government in Virginia. This solicitation is not open to
  non-profit organizations." (JJDP)
- "Local units of government, including law enforcement agencies and school divisions in the Commonwealth of Virginia
  are eligible to apply." (School Safety Personnel)
- "Current '599' recipients are eligible to recertify. To maintain eligibility, a locality must ..." (599)
- "This funding opportunity is available exclusively to non-profit organizations providing human services or criminal
  justice services." (Firearm Violence Intervention)
- "Funding is only available to juvenile detention centers in Virginia." (Byrne JAG for detention centers)

The other 39 pages say who may apply nowhere on the page, or only inside the attached guidelines PDF ("These
guidelines provide detailed guidance to aid applicants in determining eligibility"), which is not read.

Beside the body: a "Grant Program Details" views block,

```html
<div class="views-field views-field-field-application-due-date"><span class="views-label">Application Due Date: </span><strong class="field-content"><time datetime="2026-08-18T16:00:00Z">Tue, 08/18/2026 - 12:00</time></strong></div>
<div class="views-field views-field-field-date-posted"><span class="views-label">Date Posted: </span><div class="field-content"><time datetime="2026-06-08T12:00:00Z">2026-06-08</time></div></div>
<div class="views-field views-field-field-archive-date"><span class="views-label">Archive Date: </span><div class="field-content"><time datetime="2029-08-18T12:00:00Z">2029-08-18</time></div></div>
```

and a "Grant Contact Information" block (`#block-uswds-base-subtheme-grantcontactinformation-3`: coordinator and
monitor names, phones, contact links), which is never read. Guideline PDFs are linked from a "Guidelines & Forms
Reference" block in the content column (`/sites/dcjs.virginia.gov/files/grants/...pdf`) and kept as URLs only.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `va_dcjs` |
| source_id | row link | the slug (`fy-2027-state-aid-localities-police-departments-599`) |
| source_url | row link | `https://www.dcjs.virginia.gov/grants/programs/<slug>` |
| external_number | none | null |
| name | row title | the link text, whitespace collapsed (the full title; the page's `h1` is the same) |
| level / jurisdiction | constant | `state` / `VA` |
| administering_agency | constant | `Department of Criminal Justice Services` |
| agency_code | constant | `VA-DCJS` |
| funding_type | name, then the path | the shared `funding_type_for` keyword; else `grant` (the page lives under `/grants/programs` and the office calls every row a grant program). Decision 4 |
| funding_source | none | `direct`: the page makes no labelled claim about whose money it is (Byrne JAG rounds are federal, which the title says and the page does not) |
| amount_min / amount_max | none | null |
| match_required / match_pct | none | null |
| status | due date | see status rules |
| opens_at | Date Posted | the date part (when the solicitation went up) |
| closes_at | Application Due Date | the date part |
| closes_at_text | none | null (every row carries a due date) |
| rolling | none | null |
| summary | body | the first paragraph that is not the OGMS boilerplate ("is accepting applications through ..."), whitespace collapsed; else the first paragraph |
| eligibility_text | body | the eligibility passage: every paragraph and list item after a heading or bold label that mentions eligibility, up to the next heading or label, one per line; null when the page has none |
| eligibility_structured | details block, body | `{"due_at": "2026-08-18T16:00:00Z", "archive_date": "2029-08-18", "guidelines": ["https://.../file.pdf"]}`, keys only when present |
| applicant_types | eligibility passage | the shared tagger, sentence by sentence, negated sentences dropped (the Texas and WebGrants rule). Decision 3 |
| categories | none | none: the TX rule; "public safety" is knowledge about the office, not a field on the page |
| alns | none | always empty |

### Status rules

| The page says | Status |
|---|---|
| due date on or after today | open |
| due date before today | closed |
| no due date | unknown |

The day of the due date is open. Whether the row is still in the view does not matter (decision 1).

### What happens when a round leaves the view

A row leaves on its Archive Date, one to three years after its due date, by which time it is already closed on its
dates. `resolve_missing(source_id)` re-reads the program page: a due date that has passed closes the record with that
date (it already is closed; this only confirms), a future one is `unknown` (never seen), and an unreadable page is
`None` (unknown).

### Change detection

The hash is over the Program. Pages carry no modified stamp, so every program page is read every run; a page that
cannot be read falls back to the last stored copy (the Illinois and WebGrants rule), and the row alone is stored when
there is none.

## Decisions (defaults; override at review)

1. **Status comes from the due date, not from the view.** The "Current Funding Opportunities" view held 59 rounds with
   past due dates and none open on the survey day; "listed" means "not yet archived".
2. **The whole list is read every run, closed rows included.** It is the office's recent history and one request.
3. **Applicants come from the labelled eligibility passage only**, never from the purpose prose: the WebGrants rule.
   "Jail-based substance use disorder treatment" names a beneficiary, not an applicant. 20 of 59 pages have the
   passage; the others carry no tag, including rounds whose titles say they are for localities, because the page does
   not say it outside its PDF. `localities` tags municipality and county from 2026-11-03 (the shared tagger learned the
   word here: "a locality must ..." on the 599 page; measured on every stored record).
4. **Every row is a grant unless its title says otherwise**: the pages sit under `/grants/programs`.
5. **No category**, as for Texas.
6. **The contact block is never read**: named coordinators and monitors with phone numbers on a published database.

## Known gaps (the source's wording, not the parser's)

- 39 of 59 pages state eligibility only in their guidelines PDF, so most law-enforcement rounds carry no applicant tag
  even where "local law enforcement agencies" plainly means a locality's department; the tagger does not read "law
  enforcement agencies" as a government unit, and that is a shared-tagger question, not a Virginia one.
- Federal pass-throughs (Byrne JAG, VOCA, SASP, RSAT) are `direct` because the page does not label its source.
- No round was open on the survey day; the Virginia page shows DCJS only in the between-rounds group.

## Out of scope

The guidelines PDFs, OGMS (login), the CJSB award lists, DCJS's other sections (training, certification).

## Verification

- `tests/test_va_dcjs.py` against `tests/fixtures/va_dcjs/` (the view trimmed to five rows plus one repeat, and five
  program pages with their contact block and scripts removed, written by `scripts/probe_va_dcjs.py`): row parsing and
  the repeat, the body selector against the mega menu, the eligibility passage under a heading and under a bold run, a
  page with none, the negated sentence, dates and status, `fetch` with a stub (fallback to prior, limit),
  `resolve_missing`.
- Two live runs: all added, then 0 changed.
