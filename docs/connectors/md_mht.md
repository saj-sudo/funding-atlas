# Maryland Historical Trust connector: site verification and field mapping

Milestone 4, connector 3. Live probe 2026-10-15. Platform notes and the base class are in `maryland_drupal.md`.

## Source

`https://mht.maryland.gov`, Drupal on the maryland.gov platform. Funding programs live under `/funding/` (grants,
loans, three state tax credits) plus the Maryland Heritage Areas Program project grants under `/planning-protection/`.
12 program pages carry a `Timeline` section and an eligibility section. Local governments are named as eligible
applicants on 7 of them (Historic Preservation Capital and Non-Capital, MHAA project grants, Museum Assistance,
Loans for Historic Preservation, Maritime Heritage, both AAHPP grants), which makes MHT the most municipal of the
three Maryland agencies so far.

Sitemap entry:

```xml
<url><loc>https://mht.maryland.gov/funding/historic-preservation-capital-grant-program</loc><lastmod>2026-04-29T17:47Z</lastmod><changefreq>monthly</changefreq></url>
```

Page skeleton (Historic Preservation Capital Grant Program):

```html
<meta name="description" content="Learn about eligible projects and the application process for ..." />
<meta property="og:updated_time" content="2026-04-29T13:47:58-0400" />
<h1>Historic Preservation Capital Grant Program</h1>
<div class="usa-prose maryland-toc-target">
  ...
  <h2>Timeline</h2>
  <ul><li>Application opens: February</li><li>Application deadline: March</li><li>Awards announced: June</li></ul>
  <p>Applicants are strongly encouraged to contact MHT staff early in project planning for guidance.</p>
  <h2>Eligible applicants </h2>
  <ul><li dir="ltr">Nonprofit organizations</li><li dir="ltr">Local governments</li><li dir="ltr">Businesses</li><li dir="ltr">Individuals </li></ul>
  <h2>Eligible projects  </h2> ...
  <h2>Available funding</h2>
  <p>Applicants may request up to $100,000 in funding. A 1:1 cash match is required for all applicants other than nonprofits. ...</p>
  <h2>How to apply</h2> ...
```

Timeline wording seen (this is the whole problem: months, no years):

| Page | Timeline |
|---|---|
| HP Capital Grant | opens: February; deadline: March; awards: June |
| HP Non-Capital Grant | opens: May; Step 1 Intent to Apply: June; Step 2 Deadline: July/August; awards: November |
| MHAA Project Grants | Grant round opens: December; Intent to apply due: January; Full application due: March; awards: July |
| Museum Assistance | opens: August; deadline: October; awards: December/January |
| Maritime Heritage | Grant round opens: October 16; Full application due: November 13; awards: December |
| AAHPP Non-Capital | opens: early October; deadline: mid-November; awards: March |
| AAHPP Capital | opens: early April; deadline: July 1; awards: Winter |
| Loans | prose: "Loan applications are accepted year-round, as funds become available. Transfer applications ... opening in November and closing in January." |
| Homeowner Tax Credit | prose: "Applications are accepted year-round on a rolling basis." |
| Small Commercial Tax Credit | prose: "accepted year-round on a rolling, first-come, first-served basis until the program's annual $2 million funding cap is reached." |
| Competitive Commercial Tax Credit | prose: "generally available in early June and are accepted through August 31 each year." |

Nothing in a Timeline says whether the current round is open. Two things on the site do:

1. `/funding/how-apply-grant` has an `<h2>Open funding opportunities</h2>` list, today one item:
   `<a href="https://mht.prod.maryland.gov/funding/african-american-heritage-preservation-program-grants/aahpp-non-capital-grants">...</a> (closes November 20)`.
   Note the `mht.prod.maryland.gov` host; match on path.
2. The open program's page carries the platform summary box with heading `Applications now open for FY27 grant round!`
   and the line `<strong>Applications close on November 20, 2026 at 11:59 PM.</strong>`.

## Enumeration and change detection

- Enumerate from `sitemap.xml`; keep `/funding/...` and `/planning-protection/...`, skip media, education-outreach,
  about, events, locations, contacts. About 40 pages.
- `fetch()` first GETs `/funding/how-apply-grant` and reads the open list (paths). Non-200 aborts the run: without the
  list every status would be a guess. Every record payload, fresh or reused from `prior`, gets `listed_open: bool`
  stamped on it, so a change in the list changes the payload and the record even when the program page did not move.
- A page is a record only if its body has a `Timeline` section and a heading matching `eligib`. The easement page has a
  Timeline and no eligibility section; the federal tax credit page is a pointer to NPS with no sections.
- `resolve_missing`: same as the base. A page that vanished with the list unknown is `unknown`.

## Field mapping

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `md_mht` |
| name | `<h1>` | cleaned, verbatim. Both AAHPP pages are titled "Speaker Adrienne A. Jones African American Heritage Preservation Program"; the sub-program name exists only in the path. Not appended: never invent. `source_id` and `slug` disambiguate. |
| level / jurisdiction | constant | `state` / `MD` |
| administering_agency / agency_code | constant | `Maryland Historical Trust` / `MD-MHT` |
| funding_type | name keywords | `tax credit` → tax_credit, `loan` → loan, `grant` → grant; MHAA "Project Grants" → grant |
| funding_source / alns | hand map | Maritime Heritage Grant Program is `pass_through` with ALN 15.925 (National Maritime Heritage Grants; the page says "federal requirements" and "non-federal match"; listing verified on SAM.gov 2026-10-15). The rest `direct`. |
| amount_min / amount_max | `Available funding` section | exactly one `up to $X` → max X; else exactly one `$A to $B` / `$A-$B` range → min A, max B; two ranges (MHAA) → null |
| match_required | `Available funding` section | `match is not required` → False; `match is required` or `must provide a ... match` → True; else null |
| match_pct | none | null ("1:1" is ambiguous between 50% of project and 100% of grant) |
| status | see decision 1 | `listed_open` or box heading/text says `now open` → open; Timeline says `year-round` or `rolling` → open; otherwise closed |
| opens_at | none | null. Months without years are never dates. |
| closes_at | summary box | `Applications close on <Month D, YYYY>` → date; else null |
| closes_at_text | Timeline | the `<li>` lines joined with `; `, or the first sentence of a prose Timeline; plus the box close sentence if present |
| rolling | Timeline | `year-round` or `rolling` → True, else null |
| summary | `<meta name="description">` | as is |
| eligibility_text | sections headed `Eligib...`, `Ineligible ...` | verbatim, page order |
| applicant_types | keyword tags over `Eligible applicants` and `Eligibility` sections | `Local governments` → municipality, county; plus nonprofit, business, individual, tribe, state, higher_ed as the shared table says |
| categories | constant | `other`, source_code `historic-preservation`. None of the fixed categories is historic preservation; not inventing `parks`. |

## Decisions

1. **Status comes from MHT's own open list, not from the calendar.** A program on the "Open funding opportunities"
   list (or whose page says "now open") is open; year-round programs are open and rolling; everything else is
   closed. Reading "Application opens: February" against today's date would be our inference, not theirs, and the
   closed/forecasted distinction DHCD makes needs a year. The Timeline is kept verbatim in `closes_at_text` so a reader
   sees the cycle.
2. **The open list is fetched every run and failure aborts the run.** The flag is stamped on reused payloads too.
3. **Amounts are parsed here** because the wording is regular across pages; this is the first connector to fill
   `amount_max`. Two ranges on one page → null.
4. **Both AAHPP pages keep the shared `<h1>`.** Ugly in a list, but it is what the page says.

## Expected result (October 2026)

12 records: 4 open (AAHPP Non-Capital via the list, closes 2026-11-20; Loans, Homeowner and Small Commercial tax
credits as year-round), 8 closed. `v_open_for_municipalities` gains AAHPP Non-Capital (likely: "Local governments")
and Loans for Historic Preservation (likely). Maritime Heritage (round opens October 16, due November 13) is closed
today by MHT's own list; if their list lags, the diff on a later run shows the flip.

## Fixtures

`tests/fixtures/md_mht/`: `sitemap_excerpt.xml`, `how-apply-grant` (the open list), `historic-preservation-capital-grant-program`
(closed, up-to amount, match required), `aahpp-non-capital-grants` (open via list and banner, close date, match not
required), `maryland-heritage-areas-program-project-grants` (two ranges → null, tribe/state keywords),
`loans-historic-preservation` (year-round prose, loan), `maritime-heritage-grant-program` (pass-through, range amount,
dates without years), `small-commercial-tax-credit` (rolling until cap), `donate-or-convey-easement` (Timeline but no
eligibility section, excluded).
