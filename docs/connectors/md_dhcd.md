# Maryland DHCD connector: site verification and field mapping

Milestone 3 pre-work. Live probe of the five CLAUDE.md candidates on 2026-10-15, the raw data behind the pick, and the
field mapping the parser implements. Written before any code, by design: CLAUDE.md asks for URL, raw sample, and
mapping before any parser.

## Implemented (2026-10-15, same day)

`connectors/md_dhcd.py` follows this doc. Live run on a fresh database: 33 records added (13 open, 2 forecasted,
15 closed, 1 exhausted, 2 unknown), matching the crawl table at the end of this doc; the second run reports no
changes; `v_open_for_municipalities` lists CDBG Recovery Housing (tier likely, closes 2026-11-01), as predicted.
Three things changed between the mapping below and the code, all on the side of inventing less:

- **Applicant tags are read from the who-may-apply eligibility sections only.** "Eligible activities", "Eligible
  project locations", "Eligible use of funds" and the like are kept verbatim in `eligibility_text` but not scanned
  for applicant keywords, because "serve residents of a Priority Funding Area" was tagging TAG as a household
  program. The rule is an exclusion list on the heading (`THING_HEADING_RE`), so "Eligible participants" and
  "Eligible circuit sponsors" on the Circuit Rider page still count. `501(c)(3)` was added as a nonprofit phrase.
- **No ALN for CDBG Recovery Housing.** SAM.gov has no listing titled Recovery Housing (14.277, 14.278, 14.279 are
  other programs), so it is `pass_through` with an empty ALN list. 14.228, 81.042 and 93.568 verified.
- **`Next funding cycle` is kept in `closes_at_text`** (MEAP), never parsed into a date column.

Known gaps, all because the page does not say it, so the record does not either:
- **Cleaned up 2026-10-28.** State Revitalization Programs now takes its applicant tags from its six sub-program pages
  (Baltimore Regional Neighborhood Initiative, Community Legacy, Facade Improvement, National Capital SED, SEED,
  Strategic Demolition): `before_fetch` reads the SRP page and the pages it links one level down, once a run, and
  `annotate` stamps `sub_programs` (name and applicant lines) into the SRP payload. Each sub-program's lines are cut at
  a condition lead-in ("a hospital institution in the State that:") and lose their "for projects located in ..."
  clause, so the SEED fund's definition of a hospital ("two or more unrelated individuals") and BRNI's counties do not
  tag. SRP tags: municipality and county ("Local governments"), nonprofit ("Nonprofit Community Development
  Organizations"), higher_ed ("institution of higher education"). If any of the seven pages cannot be read the stored
  copy stands. Maryland Housing Leadership Awards names its applicants under an "Award categories" heading ("Awards will
  be made to local jurisdictions"), which `APPLICANT_HEADING_RE` now includes; it tags municipality and county.
- Still untagged because the page does not say: Main Street Improvement Grant ("Main Street Maryland communities" and
  "community development organizations" are the eligible applicants; neither is a municipality in the source's words, and
  the earlier note that it is a municipal round was an assumption), Main Street Tier Structure, Homelessness Solutions
  Program, Housing Choice Voucher Program, Lead Hazard Reduction.
- Milestone 4 moved the applicant scan to line level (see `maryland_drupal.md`, "Applicant lines"): MEAP and
  Housing Rehabilitation join the untagged list (nine now), CDBG drops the entitlement-county tags from its "Who is
  not eligible" section, NourishMD gains `for-profit`. Everything else, including every local-government tag, is
  unchanged.
- Only record pages are stored in `raw_record`, so the `lastmod` gate covers 33 of ~200 pages and a warm run is
  still about 170 requests (75 seconds). Fine for one agency.
- `Program.slug` embeds `source_id`, which here is a path with slashes. Unique and harmless, ugly if slugs ever
  become URLs.

## Context

CLAUDE.md lists five Maryland candidates for the first state connector and says to verify each URL before building, then
show the URL, a sample of the raw data, and the field mapping before any parser. The repo already has two connectors
(`connectors/grants_gov.py`, `connectors/sam_assistance_listings.py`) that set the pattern: `fetch(limit, prior)`,
`normalize(raw)`, `resolve_missing(source_id)`, one fixture directory per connector, registration in
`pipeline/run.py:CONNECTORS`.

## Verdict on the five candidates

| Site | CMS | Listing page found | Status field on programs | Verdict |
|---|---|---|---|---|
| grants.maryland.gov (Governor's Grants Office) | SharePoint | None. Home is an "About" page; Resource Library is ~30 outbound links to other agencies and federal sites. Every listing-style URL guessed returns 404. | n/a | Not a source. Useful as a seed list of agency grant pages for milestone 4. |
| dhcd.maryland.gov | Drupal 11 | sitemap.xml (4,556 URLs, every one with `lastmod`); 203 non-media, non-news pages; section index pages link every program | Yes. 33 program pages carry a themed "Application" box with `Application status` plus open/close dates | **Build this one.** |
| mdot.maryland.gov | SharePoint | None central. Grants are scattered: Kim Lamphier Bikeways (PageId=28), Urban Tree Program (PageId=165, rolling, reviewed Jan 15 and Jul 15), SHA programs on roads.maryland.gov | Prose only | Defer. Three to five programs, each page hand-written. |
| dnr.maryland.gov | SharePoint | `/Pages/grantsandloans.aspx` is a hand-curated link list, ~30 programs across sub-sites, one link already 404 | Prose only ("application period for FY2028 ... is now closed"). The Chesapeake and Coastal Grants Gateway page has real dates for six programs under one solicitation. | Defer. Per-page prose parsing. |
| energy.maryland.gov (MEA) | SharePoint | `/Pages/all-incentives.aspx`: five sector tables (Program, Description), 14 FY27 programs, most rows unlinked. `/transportation/Pages/incentives.aspx` links programs and separates "Archived Programs". FY27 General Notice PDF adds Type of Program, Estimated Launch Date, Target Audience. | Prose on program pages ("FY27 program opens on July 29, 2026") | Runner-up. Best candidate for connector 2 at milestone 4 (Commercial and Community Buildings, Community EVSE, SolarAPP+, Community Solar are municipal-relevant). |

Why DHCD wins: it is the only one of the five where status is a labeled field in stable markup rather than a sentence,
the site has a sitemap with per-page `lastmod` and an `og:updated_time` meta on every page (change detection for free),
robots.txt permits crawling, and its municipal programs (CDBG, State Revitalization Programs, Technical Assistance
Grant, Town Manager Circuit Rider, Main Street Improvement, MAHT grants) are exactly the pass-through and state-funded
rounds the registry exists to surface.

## Raw data (DHCD)

Sitemap entry (`https://dhcd.maryland.gov/sitemap.xml`):

```xml
<url><loc>https://dhcd.maryland.gov/media/1000</loc><lastmod>2026-06-18T19:22Z</lastmod><changefreq>yearly</changefreq></url>
```

Page metadata, present on every page:

```html
<meta property="og:updated_time" content="2026-10-09T09:02:21-0400" />
<meta name="description" content="DHCD is committed to assisting Maryland's local governments ..." />
<h1>Technical Assistance Grant</h1>
```

The Application box (identical component on all 36 pages that have it):

```html
<div role="region" class="maryland-summary-box" aria-labelledby="summary-box">
  <div class="maryland-summary-box__inner">
    <h2 class="maryland-summary-box__heading" id="summary-box">Application</h2>
    <div class="maryland-summary-box__text">
      <ul class="maryland-summary-box__list">
        <li><p><strong>Application Status:</strong> Closed</p></li>
        <li><p><strong>Application Opened:</strong> Friday, February 20, 2026 at 8:00 AM(EDT)</p></li>
        <li><p><strong>Application Closed:</strong> Friday, March 20, 2026 at 5:00 PM (EDT)</p></li>
      </ul>
    </div>
  </div>
</div>
```

Body content follows in `<div class="usa-prose maryland-toc-target">`, organized by `<h2>` headings such as
"Eligible applicants", "Who is eligible to apply?", "Who is not eligible to apply?", "Funding details",
"Available funding", "Application timeline", "How to apply".

Crawl of all 203 candidate pages (0 errors): 36 have the box, 33 have a status-type label (the 33 are listed at the end of this doc).

| Status value | Count |
|---|---|
| Open | 13 |
| Closed | 17 |
| Varies by jurisdiction | 1 |
| Funding status: fully spent (MEAP) | 1 |
| Waitlist status (HCVP) | 1 |

Label variants seen (this is the whole normalization problem):
`Application status` (26), `Application Status` (3), `Applications status` (1), `Registration status` (1),
`Funding status` (1), `Waitlist status` (1); open-date labels `Application opens` / `opened` / `period opened` /
`Opened` / `Registration period opens (expected)`; close-date labels `Application closes` / `closed` / `period closed` /
`Closed` / `Period Closed` / `Application deadline` / `Registration period closes (expected)`; plus `How to apply`
(9, free text) and a few unlabeled bullets.

Date value variants seen:
`July 6, 2026` | `August 17, 2026 at 9:00 AM` | `Friday, February 20, 2026 at 8:00 AM(EDT)` |
`February 2027` (month only) | `First business day of January at 8:00 AM` |
`We are accepting applications until available funds are committed.`

Representative records (full table at the end of this doc):

| Page | Box |
|---|---|
| Technical Assistance Grant | Closed; opened Feb 20 2026; closed Mar 20 2026 |
| State Revitalization Programs | Closed; period opened Jun 22 2026; closed Aug 6 2026 |
| Community Development Block Grant Program | Closed; deadline Jul 6 2026 |
| CDBG Recovery Housing Program | **Open**; opens Sep 2 2026; closes Nov 1 2026 |
| Maryland Town Manager Circuit Rider Program | Closed; opened May 8 2026; closed Jun 30 2026 |
| Main Street Improvement Grant (MIP) | Closed; opens February 2027 |
| NourishMD Grant Program | Open; opens Sep 22 2026; closes Nov 2 2026 |
| Net Zero Loan Program | Open; opened Apr 16 2025; "until available funds are committed" |
| Maryland Energy Assistance Program | Funding status: fully spent for 2025–2026, waitlist only |

Honest expectation for the municipal page: in October most DHCD municipal rounds are closed (they run spring to
summer). Today this connector adds roughly one open municipal record (CDBG Recovery Housing) plus closed-with-dates
records that will flip to open on a future run. That flip is the point of the diff pipeline.

## Enumeration and change detection

- Enumerate from `sitemap.xml`. Keep `<loc>` not under `/media/` or `/news-stories/`, and not the handful of utility
  paths (`/contacts`, `/about-us`, `/public-information-and-media-inquiries`, `/page-not-found`,
  `/google-translation-disclaimer`, `/procurement`, `*/special-loan-programs-local-contacts/*`, `*/program-contacts/*`).
  That is 203 pages today. Section index pages are the fallback if the sitemap ever disappears, not the primary path.
- Fetch each candidate with a 0.3 s delay, `User-Agent: funding-atlas/0.1 (+repo url)`. Cold and warm runs are both
  about 203 requests, around two minutes. `prior` lets `fetch()` skip re-parsing a page whose sitemap `lastmod` has not
  moved, same gate shape as `needs_detail()` in the SAM connector.
- A page becomes a record only if its box has a status-type label (see decision 1). `source_id` is the URL path.
- `resolve_missing(source_id)`: GET the page. 404 or box removed → `{"status": "unknown"}`. A vanished page is not
  evidence that a program closed.
- Secondary signal, not used in v1: `/news-stories/public-notices` is a Drupal view with a topic filter
  (`?topic=45` = CDBG, 16 = Neighborhood Revitalization) and 54 notices, e.g. "NourishMD Round 2 Grant Program
  Applications Open". Worth a look when the box misses a reopen.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source on page | Rule |
|---|---|---|
| source_connector | constant | `md_dhcd` |
| source_id | URL path, no leading slash | e.g. `neighborhood-revitalization/community-development-funding/technical-assistance-grant` |
| source_url | sitemap `<loc>` | as is |
| external_number | none | null |
| name | `<h1>` | strip zero-width chars (`clean()` from the SAM connector handles this) |
| level | constant | `state` |
| jurisdiction | constant | `MD` |
| administering_agency | constant | `Maryland Department of Housing and Community Development` |
| agency_code | constant | `MD-DHCD` |
| funding_type | name keywords | `Tax Credit` → tax_credit, `Loan` → loan, `Voucher` → voucher, `Grant` → grant, else null |
| funding_source | hand map by source_id | `pass_through` for known federal pass-throughs among in-scope pages: CDBG, CDBG Recovery Housing, WAP, MEAP; everything else `direct` |
| alns | same hand map | CDBG 14.228, WAP 81.042, MEAP (LIHEAP) 93.568. CDBG Recovery Housing: ALN to verify before committing; leave empty if unsure |
| amount_min / amount_max | none in v1 | null. Only two pages state amounts, in different prose ("Grant size: $25,000 – $150,000", "maximum grant request is $50,000"). Revisit after three connectors |
| match_required | body regex | `match is not required` → False, `match is required` → True, else null |
| match_pct | none | null |
| status | box status label | see status rules below |
| opens_at | box label matching `^(Application\|Registration)( period)? open(s\|ed)?( \(expected\))?$` | parse after stripping a leading weekday and a trailing ` at ...` or `(EDT)`; `parse_date()` from grants_gov handles `Month D, YYYY` |
| closes_at | box label matching `^(Application\|Registration)( period)? close(s\|d)?( \(expected\))?$` or `Application deadline` | same parsing; month-only or prose values stay null |
| closes_at_text | the box, verbatim | all date-type lines joined with `; ` as `Label: value`, so "February 2027" and "First business day of January" survive |
| rolling | close-date value regex | `until (available )?funds\|rolling\|ongoing` → True, else null |
| summary | `<meta name="description">` | as is (null if absent) |
| eligibility_text | body `<h2>` sections whose heading matches `eligib` | verbatim text of each matching section in page order, joined with a blank line. Includes "Who is not eligible to apply?" |
| eligibility_structured | none | null |
| applicant_types | keyword tags over eligibility_text | see decision 2; `source_code` = the matched phrase |
| categories | first URL segment | `housing` → housing; `energy-home-repair` → energy, housing; `neighborhood-revitalization` → housing; `business-development` → other; `policy-and-legislation` → other. `source_code` = section slug |

Status rules (box status value → `Status`):

| Box says | Status |
|---|---|
| `Open` | open |
| `Closed`, and an open-date line names a date or month-year later than today | forecasted (MIP "February 2027", Endow Maryland "February 8, 2027") |
| `Closed` otherwise | closed |
| `Varies by jurisdiction` | unknown |
| `Funding status` line containing `fully spent` / `exhausted` | exhausted |
| `Waitlist status` (any value) | unknown |
| no recognizable status label | not a record (decision 1) |

Keyword map for applicant_types (decision 2), phrase → tags:
`units? of (general )?local government`, `local governments?` → municipality, county;
`municipalit\w*`, `cities`, `towns?` → municipality; `count(y\|ies)` → county; `nonprofit` → nonprofit;
`for-profit`, `business(es)?`, `retailers?`, `developers?` → business; `homeowners?`, `households?`, `residents?`,
`renters?` → household; `individuals` / `individual` in noun position → individual; `housing authorit\w*` → housing_authority;
`school`, `local education agenc` → school. Only the eligibility sections are scanned, never the whole page.

## Decisions (1 and 2 confirmed 2026-10-15; 3 and 4 are defaults, override at review)

1. **Record scope: only pages with a status-type label** (33 today). Pages without a box are fetched but never become
   records. CLAUDE.md's "a listing that doesn't know it's closed is worse than none" is the reason.
2. **applicant_types: keyword tags from the eligibility sections**, with the matched phrase stored as `source_code`
   so the inference is auditable in SQL. Verbatim `eligibility_text` is kept alongside. Only the eligibility sections
   are scanned, never the whole page.
3. **HTML parsing dependency.** Add `beautifulsoup4` (best documented for a Python learner; the markup is clean). The
   grants_gov `_Stripper` is enough for text, not for walking the box and the `<h2>` sections.
4. **Raw payload shape.** Store the `<main>` element HTML plus `url`, `lastmod`, `updated_time`, `description` as the
   `raw_record` payload (20 to 60 KB per page, 33 pages). Keeps re-normalizing possible without a refetch, matches
   "payload is stored verbatim".

## Out of scope for this connector (say so in the module docstring)

- Multifamily financing programs (Rental Housing Program, LIHTC, HOME, NHTF) have no box; their rounds live in the
  Community Development Administration notices. Developer-facing anyway.
- Sub-programs of State Revitalization Programs (Community Legacy, Facade Improvement, Strategic Demolition Fund,
  BRNI, NCSED, SEED) have pages but no box; the SRP page is the record for the round.
- Individual and household programs (home repair loans, EmPOWER, WAP, MEAP, HCVP) are ingested because the box is
  there and applicant types are recorded; the municipal view filters them out by applicant type. Nothing is done
  with them in v0.1.

## Implementation session (next session, one connector)

Files to create or touch:
- `connectors/md_dhcd.py`: `fetch`, `normalize`, `resolve_missing`, the label and status rules above.
- `scripts/probe_md_dhcd.py`: writes fixtures (sitemap excerpt trimmed to candidate URLs, plus the sample pages).
- `tests/fixtures/md_dhcd/`: `sitemap_excerpt.xml`, and pages `technical-assistance-grant` (closed, weekday date
  format), `nourishmd-grant-program` (open, opens and closes), `community-development-block-grant-program` (closed,
  deadline-only label), `net-zero-loan-program` (open, rolling text), `main-street-improvement-grant-mip` (closed,
  month-only future → forecasted), `maryland-energy-assistance-program` (funding status → exhausted), and one
  box-less page to prove it is excluded.
- `tests/test_md_dhcd.py`: label normalization, each date variant, each status rule, applicant keyword tagging with
  source_code, section → category, no-invention test on a page with a bare box.
- `pipeline/run.py`: register `md_dhcd` in `CONNECTORS`.
- `pyproject.toml`: add `beautifulsoup4`.
- Commit as `connector(md-dhcd): ...` per CLAUDE.md.

## Verification

1. `uv run pytest` green against fixtures only (no network).
2. `uv run python cli.py run md_dhcd` on a fresh DB: expect about 33 records, 13 open, diff lists them as added.
3. Run again immediately: expect 0 changed, 0 missing.
4. `SELECT name, status, opens_at, closes_at, closes_at_text FROM program WHERE source_connector='md_dhcd' ORDER BY
   status, closes_at;` and eyeball against the live pages for TAG, SRP, CDBG, NourishMD, MIP.
5. `SELECT * FROM v_open_for_municipalities WHERE jurisdiction='MD';` should show CDBG Recovery Housing today.

## Leads for milestone 4 (not acted on)

- MEA is the runner-up; its transportation page already separates active from archived programs.
- Commerce (`commerce.maryland.gov/fund`), Maryland Historical Trust, and the Department of Aging are also Drupal 11 on
  the same `maryland-` theme platform as DHCD. The summary box was not found on their index pages, so whether the
  DHCD parser generalizes is unverified. If it does, the shared base class CLAUDE.md predicts for the third connector
  is a Drupal-theme parser, not a SharePoint one.
- GOCPP and DHS Office of Community Grants are WordPress; MDE and DGS Capital Grants are SharePoint.

## Appendix: every DHCD page with a status-type label (crawl of 2026-10-15)

| Page | Path | Box lines | Page updated |
|---|---|---|---|
| Own Your Future: Property Acquisition for Small Business | `business-development/business-lending/own-your-future` | Application status: Open; How to apply: Schedule a consultation to discuss your business's needs and financing options | 2026-08-26 |
| Small Business Companion Loans | `business-development/business-lending/small-business-companion-loans` | Application status: Open; How to apply: Schedule a consultation to discuss your business's needs and financing options | 2026-10-07 |
| Small Business Direct Loans | `business-development/business-lending/small-business-direct-loans` | Application status: Closed; Application opened: August 17, 2026 at 9:00 AM; Application closed: September 17, 2026 at 11:59 PM | 2026-10-07 |
| NourishMD Grant Program | `business-development/nourishmd-grant-program` | Application status: Open; Application opens: September 22, 2026; Application closes: November 2, 2026 | 2026-10-07 |
| BeSMART Home Loan Program | `energy-home-repair/energy-grants-and-loans-residents/besmart-home-loan-program` | Application status: Open; How to apply: Apply online or request paper application by email. | 2026-10-05 |
| EmPOWER Maryland Limited Income Energy Efficiency Program | `energy-home-repair/energy-grants-and-loans-residents/empower` | Application status: Open; How to apply: Apply online or submit application and supporting documents by mail | 2026-10-08 |
| Maryland Energy Assistance Program (MEAP) | `energy-home-repair/energy-grants-and-loans-residents/maryland-energy-assistance-program` | Funding status: Funding is fully spent for 2025–2026 (Waitlist only — assistance is not guaranteed); Next funding cycle: November 1, 2026 (October 1 for Garrett County only) - September 30, 2027, depending on available f… | 2026-10-05 |
| Net Zero Loan Program | `energy-home-repair/energy-grants-and-loans-residents/net-zero-loan-program` | Application status: Open; Application opened: April 16, 2025; Application closes: We are accepting applications until available funds are committed. | 2026-10-05 |
| Weatherization Assistance Program (WAP) | `energy-home-repair/energy-grants-and-loans-residents/weatherization-assistance-program-wap` | Application status: Open; How to apply: Contact your local weatherization agency (LWA) - PDF - 79.33 KB | 2026-10-05 |
| Accessible Homes for Seniors | `energy-home-repair/homeowner-repair-loans-grants/accessible-homes-seniors` | Application status: Open; How to apply: Submit application and supporting documents by email or mail | 2026-08-28 |
| Housing Rehabilitation | `energy-home-repair/homeowner-repair-loans-grants/housing-rehabilitation` | Application status: Open; How to apply: Submit application and supporting documents by email or mail | 2026-10-08 |
| Indoor Plumbing | `energy-home-repair/homeowner-repair-loans-grants/indoor-plumbing` | Application status: Open; How to apply: Submit application and supporting documents by email or mail | 2026-08-11 |
| Lead Hazard Reduction | `energy-home-repair/homeowner-repair-loans-grants/lead-hazard-reduction` | Application status: Open; How to apply: Submit application and supporting documents by email or mail | 2026-08-11 |
| Independent Living Tax Credit | `energy-home-repair/independent-living-tax-credit` | Application status: Closed; Application opens: First business day of January at 8:00 AM; Application closes: June 1st of the current calendar year at 5:00 PM | 2026-08-21 |
| Community Schools Rental Assistance Program | `housing/homeless-solutions/community-schools-rental-assistance-program` | Application status: Varies by jurisdiction; Application schedule: Intermittent | 2026-09-29 |
| Homelessness Solutions Program (HSP) | `housing/homeless-solutions/homelessness-solutions-program-hsp` | Application Status: Closed; Application Period Closed: April 25, 2025 | 2026-09-01 |
| Maryland Housing Counseling Fund Program | `housing/homeless-solutions/maryland-housing-counseling-fund-program` | Application status: Closed; Application closed: June 13, 2025 | 2026-08-05 |
| Housing Choice Voucher Program (HCVP) | `housing/housing-choice-voucher-program-hcvp` | Waitlist status: Closed; Waitlist reopened: April 1, 2026, at 9:00 AM; Waitlist closed: April 30, 2026, at 5:00 PM | 2026-10-07 |
| Group Home Program | `housing/multifamily-financing-programs/group-home-program` | Applications status: Closed; Not accepting applications at this time | 2026-10-08 |
| Catalytic Revitalization Tax Credit | `neighborhood-revitalization/community-development-funding/catalytic-revitalization-tax-credit` | Application status: Closed; Application opened: August 12, 2026; Application closed: October 1, 2026 at 5:00 PM | 2026-10-01 |
| Community Development Block Grant Program | `neighborhood-revitalization/community-development-funding/community-development-block-grant-program` | Application status: Closed; Application deadline: July 6, 2026 | 2026-08-24 |
| Community Development Block Grant Recovery Housing Program | `neighborhood-revitalization/community-development-funding/community-development-block-grant-program/recovery-housing-program` | Application status: Open; Application opens: September 2, 2026; Application closes: November 1, 2026 | 2026-10-07 |
| Community Investment Tax Credits Program | `neighborhood-revitalization/community-development-funding/community-investment-tax-credits-program` | Application status: Closed; Application period opened: June 2, 2026; Application period closed: July 14, 2026 | 2026-10-09 |
| Endow Maryland Tax Credit Program | `neighborhood-revitalization/community-development-funding/endow-maryland-tax-credit-program` | Registration status: Closed; Registration period opens (expected): February 8, 2027; Registration period closes (expected): February 26 by 5:00 PM | 2026-08-13 |
| Maryland Affordable Housing Trust Grant Program | `neighborhood-revitalization/community-development-funding/maryland-affordable-housing-trust-program/maht-grant-program` | Application status: Closed; Application period opened: July 16, 2026; Application period closed: September 10, 2026 | 2026-09-11 |
| Safe and Secure Water Access in Homes Grant Program | `neighborhood-revitalization/community-development-funding/maryland-affordable-housing-trust-program/safe-and-secure-water-access-homes-grant-program` | Application status: Closed; Application opened: May 29, 2026; Application closed: July 10, 2026 | 2026-08-26 |
| Maryland Town Manager Circuit Rider Program | `neighborhood-revitalization/community-development-funding/maryland-town-manager-circuit-rider-program` | Application status: Closed; Application opened: May 8, 2026; Application closed: June 30, 2026 | 2026-08-17 |
| State Revitalization Programs | `neighborhood-revitalization/community-development-funding/state-revitalization-programs` | Application status: Closed; Application period opened: June 22, 2026; Application period closed: August 6, 2026 | 2026-10-09 |
| Technical Assistance Grant | `neighborhood-revitalization/community-development-funding/technical-assistance-grant` | Application Status: Closed; Application Opened: Friday, February 20, 2026 at 8:00 AM(EDT); Application Closed: Friday, March 20, 2026 at 5:00 PM (EDT) | 2026-10-09 |
| Main Street Improvement Grant (MIP) | `neighborhood-revitalization/main-street-maryland/main-street-improvement-grant-mip` | Application status: Closed; Application opens: February 2027 | 2026-08-14 |
| Main Street Maryland Tier Structure | `neighborhood-revitalization/main-street-maryland/main-street-maryland-tier-structure` | Application status: Closed; For details on the application process, review how to become a Main Street Maryland community and our frequently asked questions (FAQ) | 2026-09-10 |
| Baltimore Vacants Reinvestment Initiative | `neighborhood-revitalization/reinvest-baltimore/baltimore-vacants-reinvestment-initiative` | Application Status: Closed; Application Opened: February 18, 2026 at 10:00 AM; Application Closed: April 1, 2026 at 11:59 PM | 2026-10-07 |
| Maryland Housing Leadership Awards | `policy-and-legislation/housing-starts-here-executive-order/maryland-housing-leadership-awards` | Application status: Open; Application deadline: Sunday, November 1, 2026, at 11:59 PM | 2026-08-14 |
