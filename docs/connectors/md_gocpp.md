# GOCPP (Governor's Office of Crime Prevention and Policy): survey, blocked by robots.txt

Milestone 7, connector 3 in the roadmap's order. Live survey 2026-10-16. **No connector.** `https://gocpp.maryland.gov/robots.txt`
names about two dozen search-engine bots with a short disallow list each, then ends with:

```
User-agent: *
Disallow: /
```

A crawler that is not one of the named bots is asked to stay off the whole site. CLAUDE.md's rule for this is to say
so and stop, and that is the decision: no parser, no fixtures, no scheduled fetches. The survey below is what a
connector would look like if the office grants permission or publishes the data another way; it was gathered from a
single manual read of 45 pages during the survey, before the robots file was checked, which is the one thing this
session got in the wrong order.

## What the site is

WordPress (`WPMaryland_eGov_v1_3` theme), server-rendered, `Cache-Control: no-store`, no `Last-Modified`, but every
program page carries `<meta property="article:modified_time">`, a per-page change signal none of the SharePoint
agencies has.

- `/grants/programs/` lists all 43 grant programs as one `<ul class="spaced">` of links `/grants/programs/<code>/`.
- `/grants/` carries the sentence "A list of grant programs that are currently accepting applications are accessible
  using the links below:" followed by a `<ul>` of links (two on the survey date: LETS and VIPP-EVAL). The `<ul>` sits
  inside the `<p>` (invalid HTML), so it has to be found from the sentence, not with a CSS selector. The same role as
  MHT's open list.
- `/grants-calendar` is a JavaScript calendar widget with no events in the static HTML.

Program pages are `<article class="... type-gp_program ... eligible_apply-<slug> ... release_month-<month>
application_month-<month>">` with sections Overview (Description, History), Categories funded, Eligible to apply,
Documents (NOFA PDFs), Dates (Projected NOFA Release Month, Projected Application Month), Contacts. 23 of 43 carry
an "SFY 2027 - Funding Opportunity" callout, a `<ul>` whose items mix training-session lines with
`<li><b>Application Deadline</b><span>: April 17, 2026 at 11:59 p.m</span></li>` (note the space before the colon;
the trailing period comes and goes). Every deadline in those callouts was February to May 2026 on the survey date:
GOCPP's state-fiscal-year rounds run in late winter and spring.

## The taxonomy (30 `eligible_apply` slugs over 43 pages)

`local-law-enforcement` 24, `local-government-agencies` 18, `state-law-enforcement` 15, `nonprofit-organizations` 12,
`state-government-agencies` 11, `states-attorneys-offices` 6, `county-government-agencies` 5, `faith-based-organizations`
4, `designated-child-advocacy-centers` 4, `community-based-nonprofit-organizations` 4, `rape-crisis-centers` 4,
`state-and-local-courts` 3, `institutes-of-higher-learning` 2, `comprehensive-domestic-violence-programs` 2,
`direct-victim-services-providers` 2, `state-domestic-violence-coalition` 2, `governmental-entities` 2, and thirteen
single-use slugs (courts, labs, detention centers, researchers, Baltimore City Public Schools, two state departments).

Application months: April 16, March 6, June 4, July 4, September 4, and one `continuous` (LETS).

## The connector that was not built

- Enumerate from `/grants/programs/`; `source_id` = `programs/<code>`; payload `{url, title, article_html,
  content_hash, modified_time, listed_open}`; `before_fetch` reads `/grants/` and a non-200 aborts the run.
- Status: listed on `/grants/` → open; else a callout deadline ahead → open with `closes_at`, behind → unknown with
  `closes_at` kept; else unknown. Never forecasted: the months carry no year. `rolling` from `application_month-continuous`.
- Applicants from the taxonomy slugs with the agency's own definition as `source_code` ("law enforcement agencies of
  any county, incorporated city or town"): `local-government-agencies` and `local-law-enforcement` → municipality,
  county; `county-government-agencies` → county; `governmental-entities` → municipality, county, state; the state,
  nonprofit, higher-education and school slugs to their types; the rest unmapped and visible in `eligibility_text`.
- Category `public_safety`; funding type `grant`; `external_number` = the code in the H1.
- Federal pass-throughs where the program is the federal formula program by name, listings verified on SAM.gov
  2026-10-16: BJAG 16.738, VOCA 16.575, STOP/VAWA 16.588, Title II 16.540, RSAT 16.593, PSN 16.609, COSSUP 16.838,
  Coverdell 16.742, SASP 16.017, FVPS 93.671. ICAC (16.543 Missing Children's Assistance) and Byrne SCIP (SAM lists
  16.045 as a different program) would stay `direct` until the page names the listing.

Expected yield on the survey date: 43 records, 2 open (LETS rolling, VIPP-EVAL), 23 with a past SFY 2027 deadline,
18 unknown; one open municipal row (LETS). The connector earns its keep in February to May, when the SFY 2028
callouts appear.

## What to do instead

Ask. The office runs a Grants Management System (`grants.goccp.maryland.gov`, login) and posts NOFAs as PDFs; a
request for a feed or for crawl permission for `funding-atlas/0.1` is the next step, and belongs with the outreach
list in the roadmap. Until then the municipal law-enforcement rounds (BARM, SAPP, SAPC, PRAR, WAAG, GVRG, EDSG, PACT,
CGPF) are a known gap on the Maryland page.
