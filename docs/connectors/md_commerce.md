# Maryland Commerce connector: site verification and field mapping

Milestone 4, connector 2. Live probe 2026-10-15. Platform notes and the base class are in `maryland_drupal.md`.

## Source

`https://commerce.maryland.gov`, Drupal on the maryland.gov platform. Programs live under `/financial-incentives/`
in three sections: `grants` (8), `loans-financing` (11), `tax-incentives` (15). 34 program pages; the three section
index pages and two Global Gateway sub-pages have no status section and are not records.

Sitemap entry:

```xml
<url><loc>https://commerce.maryland.gov/financial-incentives/grants/exportmd-program</loc><lastmod>2026-10-02T14:11Z</lastmod><changefreq>monthly</changefreq></url>
```

Page skeleton (ExportMD):

```html
<meta name="description" content="The ExportMD Program gives Maryland small businesses up to $5,000 ..." />
<meta property="og:updated_time" content="2026-10-02T10:11:34-0400" />
<h1>ExportMD Program</h1>
<div class="usa-prose maryland-toc-target">
  <p><strong>About this page:</strong> Get back up to $5,000 to help market your small business in other countries.</p>
  <h2>Program Status</h2>
  <p dir="ltr">The ExportMD Program is currently active.</p>
  <p dir="ltr">Commerce accepts applications every month. <strong>Applications are due on the 1st of each month.</strong></p>
  <p dir="ltr">The program is funded in part by the U.S. Small Business Administration (SBA) through the federal State Trade Expansion Program (STEP). ...</p>
  <h2>What This Program Does</h2> ...
  <h2>Who Can Apply</h2> ...
  <h2>What the Grant Can Fund</h2> ...
  <h2>Key Eligibility Requirements</h2> ...
  <h2>How to Apply</h2> ...
```

`Program Status` is the first `<h2>` on all 34 pages (one page, the data center exemption, has it twice with the same
text). It is prose, but the first sentence is formulaic. Every distinct opening seen:

| Opening sentence(s) | Count | Reading |
|---|---|---|
| `The program is currently active.` / `is active.` / `X is currently active.` / `is ongoing.` | 24 | open |
| `The application period for Tax Year 2025 is open.` | 1 | open |
| `The program is active but between funding rounds. The most recent application period closed January 30, 2026.` | 1 | closed |
| `The program is currently closed. The Tax Year 2025 application period opened May 1, 2026 and closed September 15, 2026.` | 1 | closed |
| `The application period is currently closed. The program sunsetted on September 30, 2026.` | 1 | closed |
| `Closed to new positions.` / `Closed to new enrollment as of June 1, 2024.` | 2 | closed |
| `... Applications are not being accepted at this time. Check this page for the next application window (August 2, 2027).` | 1 | forecasted |
| `... The most recent round accepted applications from July 1, 2026 through August 14, 2026. That window has closed.` | 1 | closed |
| `... The most recent posted deadline was 5:00 p.m. on June 1, 2026 ... That deadline has passed and no later round has been posted.` | 1 | closed |
| `The program is active and awards grants once per year ... Both dates have passed.` | 1 | closed |
| `CBAF is a financing resource operated by Commerce. Its current funding opportunity is ... The application portal opened June 3, 2025.` | 1 | unknown |

"Active" in Commerce's usage means the program exists in statute, not that an application window is open ("active but
between funding rounds"). So closed wording wins over active wording, and a page with neither is `unknown`.

Date wording seen in the status text: `opened May 1, 2026 and closed September 15, 2026`, `opened Aug. 3, 2026 and
closed Aug. 31, 2026`, `from July 1, 2026 through August 14, 2026`, `from June 1, 2026 until the November 15, 2026
statutory deadline`, `closed January 30, 2026`, `deadline was 5:00 p.m. on June 1, 2026`, `opened in September 2026`
(month only), `next application window (August 2, 2027)`. Sunset sentences (`terminates June 30, 2032`, `remains in
effect until January 1, 2032`, `taxable years beginning before January 1, 2027`) also carry dates and must not be read
as deadlines.

## Enumeration and change detection

- Enumerate from `sitemap.xml`; keep only `<loc>` under `/financial-incentives/`. 41 pages. (The rest of the site is
  press releases, boards, and about pages; crawling all 209 non-media pages found no other status section.)
- Same `lastmod` gate, delay, user agent, and `resolve_missing` as DHCD (base class).
- A page is a record only if its body has a `Program Status` section. `source_id` is the URL path.

## Field mapping

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `md_commerce` |
| source_id / source_url | sitemap | path without leading slash / `<loc>` |
| name | `<h1>` | cleaned |
| level / jurisdiction | constant | `state` / `MD` |
| administering_agency / agency_code | constant | `Maryland Department of Commerce` / `MD-COMMERCE` |
| funding_type | name keywords, then URL section | `tax credit` → tax_credit, `exemption` → other, `loan` → loan, `grant` → grant, `voucher` → voucher; else `grants` → grant, `loans-financing` → loan, `tax-incentives` → tax_credit |
| funding_source / alns | hand map | ExportMD is `pass_through` with ALN 59.061 (State Trade Expansion; the page says it is funded through the SBA STEP cooperative agreement; verified on SAM.gov 2026-10-15). MSBDFA mentions SSBCI money but is a state authority: `direct`. |
| amount_min / amount_max | none | null in v1 ("Get back up to $5,000" lives in an "About this page" line, "What's Offered" and "Loan Terms" vary too much) |
| match_required | body regex | same wording rule as DHCD (`match is (not )?required`); expect null nearly everywhere |
| status | Program Status text | closed wording (`not being accepted`, `between funding rounds`, `currently closed`, `is closed`, `closed to new`, `window has closed`, `deadline has passed`, `dates have passed`, `sunsetted`) → closed; else open wording (`currently active`, `is active`, `is ongoing`, `is open`, `now open`, `accepting (new )?applications`, `accepts applications`, `applications are accepted`, `are accepting`) → open; else unknown. Closed plus a `next ... (<Month D, YYYY>)` date after today → forecasted. |
| opens_at | Program Status text | `opened|opens [on] <date>` or `from <date>`, in a sentence that is not a sunset sentence; `Aug.` → `Aug` before parsing |
| closes_at | Program Status text | `closed|closes|through|until [the] <date>` or `deadline ... <date>`, same sentence filter |
| closes_at_text | Program Status text | the sentences that name a month or say rolling/deadline/round/window, minus sunset sentences, joined with a space |
| rolling | Program Status text | `rolling basis`, `no fixed deadline`, `no fixed application window`, `no annual deadline`, `no statewide application deadline`, `every month`, `year-round` → True, else null |
| summary | `<meta name="description">` | as is |
| eligibility_text | sections headed `Who ...`, `Eligibility`, `Key Eligibility Requirements`, `Eligible ...` | verbatim, page order, blank line between |
| applicant_types | keyword tags over the `Who ...` sections only | `Key Eligibility Requirements` is kept verbatim but not scanned ("Tier 1 county" would tag a county) |
| categories | constant | `other`, source_code = URL section (`grants` etc.). None of the fixed categories fit business incentives; PWQ is the one arguable `workforce` and is left `other` rather than special-cased. |

## Decisions

1. **Closed beats active.** See the table; "active" is Commerce for "exists".
2. **Dates are read from the status section only**, sentence by sentence, never from sunset sentences. Month-only
   values stay in `closes_at_text`.
3. **No amounts in v1.** Revisit with MHT's cleaner "Available funding" wording as the model.
4. **All records are `other` category.** Honest; the municipal view's `local_gov_wording` rule still surfaces
   Advantage Maryland from its eligibility text.

## Expected result (October 2026)

34 records: 24 open (most on a rolling basis), 8 closed, 1 forecasted (Manufacturing 4.0, next window
2027-08-02), 1 unknown (CBAF). Municipal relevance: Advantage Maryland (`likely`, from "counties, municipalities");
everything else `possible` or `unlikely`. Commerce adds breadth to the registry, not many municipal hits; that is
expected and fine.

## Fixtures

`tests/fixtures/md_commerce/`: `sitemap_excerpt.xml` plus `exportmd-program` (open, every month, pass-through),
`maryland-manufacturing-40-m40` (forecasted, `Aug.` dates), `employer-security-clearance-costs-tax-credit-escc`
(closed, opened/closed dates, sunset sentence to ignore), `research-and-development-tax-credit-rd` (open with a
from/until window), `child-care-capital-support-revolving-loan-fund` (active but between rounds), `advantage-maryland-medaaf`
(municipal wording), `cannabis-business-assistance-fund-cbaf` (unknown), `grants` (section index, no status, excluded).
