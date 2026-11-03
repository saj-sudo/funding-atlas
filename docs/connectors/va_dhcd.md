# Virginia DHCD connector (`va_dhcd`): source, raw data and field mapping

Milestone 11, Virginia's second agency (the municipal five, decision 2026-11-03). Written 2026-11-03 from the
Mid-Atlantic survey and a read of every page the site's section menus reach, before the parser. Community development
block grants, downtown and industrial revitalization, water and sewer, housing rehabilitation, the Appalachian
Regional Commission: the agency a Virginia town administrator deals with most.

## Implemented (2026-11-03, same day)

`connectors/va_dhcd.py` follows this doc. First live run on a fresh database: 30 records added in 38 seconds (the
crawl reached 8 program pages the hand count below had not: the CDBG Urgent Need and Economic Development funds,
Manufactured Housing, Acquisition and Rehabilitation, the Livable Homes Tax Credit, Communities of Opportunity, VERP
and the VEZ Local Zone Administrators page, five at depth one, 23 at depth two, two at depth three), 0 errors. Second
run: 0 changed, 0 missing. Status: 2 open (VEZ, due 2027-04-01; Manufactured Housing, due 2026-12-28), 28 `unknown`;
10 records carry a cycle sentence, 3 of them a full date. 25 of 30 carry an applicant tag, 15 a municipality
(IRF, the CDBG family, VAARC, PHCRF, the Regional Water and Wastewater Fund, VHTF, HOPWA, CBL, VERP, ARS). The
Virginia page: 0 open municipal rows (the two open rounds are for zone investors and park owners) and 11 between
rounds (10 DCJS, 1 DHCD: IRF, due 2026-07-31, which the page still states). Found while writing the parser: the
first cycle regex picked "application is submitted" on the CDBG page over "the spring of every year"; the rule now
keys on deadline, due, accepted, received-by, period, closed and rolling words only.

## The source

The Department of Housing and Community Development (DHCD) runs a Drupal 10 site, `https://www.dhcd.virginia.gov`,
with a standard Drupal `robots.txt` (only `/core/`, `/profiles/` and the like disallowed), no sitemap (404) and no
grants index (`/grants` and `/programs` are 404). Programs are reached by menu: three section pages, each a grid of
teasers, lead to topic landing pages, which lead to program pages; some teasers go straight to a program.

| Page | What | Fetches per run |
|---|---|---|
| `/communities`, `/housing`, `/businesses` | the three section pages: teasers ("Click Here") to landing or program pages | 3 |
| a landing page (`/downtown-revitalization`, `/water-sewer-and-drainage`, `/housing-rehabilitation`, ...) | more teasers, the same markup | about 35 |
| a program page (`/irf`, `/vaarc`, `/cdbg-community-improvement-grants`, ...) | the program template: a contact block with an intro paragraph, a body, three "detail boxes" | about 50 |

About 90 requests a run, 0.3 s apart, under a minute. Every teaser on the host is followed to a depth of three below
the sections (the CDBG family pages sit at depth two and link on to the CDBG grant pages with "Learn More"); links off
the host, PDFs and the site chrome (`/about`, `/codes`, `/foia`, ...) are not. Pages are fetched once per run however
many teasers point at them. On 2026-11-03 the crawl reached about 90 pages: 3 sections, the landings, 30 program
pages and the rest (regional council pages, resource pages, a GO Virginia board page, an "Access denied" node).

### A teaser

```html
<div class="listingitem"><div class="imageboxouter">...</div>
  <div class="contentouter"><h3>Industrial Revitalization Fund (IRF)</h3>
    <div class="listingitem-body"><p>The Industrial Revitalization Fund (IRF) leverages local and private resources ...</p>
      <a href="http://www.dhcd.virginia.gov/irf" class="button"><span class="orange-tabs ffx_background_lightteal">Click Here</span></a></div></div></div>
```

The CDBG family pages (`/cdbg-downtown-revitalization`, `/cdbg-water-sewer-and-drainage`, ...) use the same `a.button`
with "Learn More", pointing at `/cdbg-community-improvement-grants` and `/cdbg-planning-grants`. Hrefs are written
with `http://www.dhcd.virginia.gov` and as site-relative paths; both are normalised to the `https` host.

### A program page

```html
<title>Industrial Revitalization Fund (IRF) | DHCD</title>
<div class="programcontact"><div class="container"><h1>Contact:</h1>
  <div class="left"><div class="user"><div class="name">...</div><div class="email"><a href="mailto:...">...</a></div><div class="phone">...</div></div>
  <div class="content"><p>The Industrial Revitalization Fund (IRF) leverages local and private resources to achieve market-driven redevelopment ...</p></div></div></div>
<article class="page full clearfix"><div class="field field--name-body ...">...prose, often empty...</div></article>
<div class="detail_boxes">
  <div class="detail_box expandable"><div class="header eligibility"><span class="image"></span><span class="text">Eligibility</span></div>
    <div class="content" name="bxEligibility"><div class="field field--name-field-eligibility ..."><p>Only local governments (city, county or town) or regional or local economic or industrial development authorities may apply for the funds. ...</p></div></div></div>
  <div class="detail_box expandable"><div class="header resources"><span class="text">Resources</span></div>...</div>
  <div class="detail_box expandable"><div class="header helpful"><span class="text">Helpful Links</span></div>...</div>
</div>
```

The page's `h1` is the word "Contact:"; the program name is the `<title>` before ` | DHCD` (the site writes some in
capitals: `VIRGINIA SMALL BUSINESS RESILIENCY FUND`). **The box label is the marker.** Three boxes with CSS classes
`eligibility`, `resources`, `helpful` appear on every templated page, but the site fills them freely: on `/vhsp` the
`eligibility` box is titled "Service Provider Resources", on `/vez` the `helpful` box is titled "Eligibility", on the
GO Virginia region pages the first box is "Support Organization". A page is a program when a box's visible label is
`Eligibility`: 30 pages on 2026-11-03 (IRF, VAARC, VEZ and its Local Zone Administrators page, VMS, CBL, PHCRF, the
CDBG Project, Planning, Urgent Need and Economic Development pages, Regional Water and Wastewater Fund, EHARP, IPR,
LHR, WAP, HOME, NHTF, CHDO, HOPWA, VHTF Homeless Reduction, VHTF Loan Pool, VIDA, VSBRF, Private Activity Bonds,
Manufactured Housing, Acquisition and Rehabilitation, the Livable Homes Tax Credit, Communities of Opportunity, VERP).

Eligibility box text on 2026-11-03, the applicant line of each: "Only local governments (city, county or town) or
regional or local economic or industrial development authorities may apply" (IRF); "eligible candidates include
localities, planning district commissions (PDCs), educational institutions, health organization, nonprofit
organizations and others" (VAARC); "Non-entitlement units of local government are the only eligible recipients of
Virginia CDBG funding" (CDBG); "Local governments, nonprofit organizations, and public housing authorities" (CHDO
and HOME pages vary). The intro, body and boxes carry the only dates: "Applications will be due on July 31, 2026."
(IRF intro), "Applications for the upcoming grant year, Grant Year 2026 (GY26), are due April 1, 2027. The EZ
Application Submission Portal will be open for submitting GY26 applications from January 1, 2027 to April 1, 2027."
(VEZ body), "Applications are accepted on an open, rolling basis from May 10 to November 15th, or until funds are
exhausted" (CDBG Planning), "The timeline for submission of competitive grant applications to DHCD is the spring of
every year" (CDBG Project Grants). Most pages state no date at all: the MEA and DNR situation.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `va_dhcd` |
| source_id | page path | the slug (`irf`, `cdbg-community-improvement-grants`) |
| source_url | page | `https://www.dhcd.virginia.gov/<slug>` |
| external_number | none | null |
| name | `<title>` | the part before ` \| DHCD`, as written |
| level / jurisdiction | constant | `state` / `VA` |
| administering_agency | constant | `Department of Housing and Community Development` |
| agency_code | constant | `VA-DHCD` |
| funding_type | name | the shared `funding_type_for` keyword (`grant`, `loan`, `tax credit`); else null (DHCD's programs are grants, loans, bonds and tax credits and the page does not label which) |
| funding_source | none | `direct`: no labelled claim (CDBG and HOME are federal money, which the page names but does not label) |
| amount_min / amount_max | none | null |
| match_required / match_pct | none | null |
| status | the cycle sentence | see status rules |
| opens_at / closes_at | the cycle sentence | the first and last full date (`Month D, YYYY`) in it when the sentence says `from ... to`; the last full date alone as `closes_at` when it says `due`, `deadline`, `by`, `through` or `until`; else null |
| closes_at_text | the cycle sentence | verbatim: the first sentence of the intro, body or boxes that mentions a deadline, due date, application period, acceptance of applications or a closed or open round; null when none |
| rolling | the cycle sentence | `True` when it says `rolling` or `open basis`; else null |
| summary | intro | the first paragraph of the contact block's `content`, whitespace collapsed |
| eligibility_text | the Eligibility box | its paragraphs and list items, one per line |
| eligibility_structured | boxes | `{"boxes": ["Eligibility", "Resources", "Helpful Links"]}`: the box labels as written |
| applicant_types | the Eligibility box | the shared tagger, sentence by sentence, negated sentences dropped |
| categories | none | none (the TX rule) |
| alns | none | always empty |

### Status rules

In order; the first that applies wins. Dates are read only from the cycle sentence.

| The page says | Status |
|---|---|
| a cycle sentence with `closed` (`now closed`, `is closed`, `closed to new applications`) | closed |
| a full due date on or after today | open |
| a full due date before today | unknown (a stale page is not a closure: the MEA rule) |
| anything else, including no cycle sentence | unknown |

### What happens when a page leaves the tree

`resolve_missing(source_id)` returns `unknown` without a request: a page the menus no longer reach is a page the
agency stopped pointing at, which it does not state as a closure, and the page itself carries no status to read back.

### Change detection

The hash is over the Program. No modified stamp anywhere (the pages are Drupal nodes without dates), so every page is
read every run. A section page that cannot be read aborts the run (every program would look missing); a deeper page
that cannot be read is skipped, and if it was a program last run its stored copy is kept.

## Decisions (defaults; override at review)

1. **The Eligibility box label is what makes a page a program.** The site has no program content type; the templated
   contact block appears on resource pages, regional council pages and a board page too. The visible label
   `Eligibility` is the agency saying "this is something you apply for". Cost: program pages whose boxes are labelled
   otherwise are left out (decision 5).
2. **Applicants come from the Eligibility box only**, sentence by sentence, negated sentences dropped: the WebGrants and
   DCJS rule. The intro describes; the box says who.
3. **Status is `unknown` unless the page states a dated deadline ahead or says a round is closed.** Most pages state no
   date; a dated deadline in the past is a stale page. The cycle sentence is kept verbatim so a reader sees "spring of
   every year" or "open, rolling basis from May 10 to November 15th" where the data has no date.
4. **The crawl, not a hand list.** Three menus and the teaser markup are stable; a page DHCD adds to a menu appears on
   the next run. Depth three, host only, no PDFs, each page once.
5. **Left out on purpose, with a hand list as the remedy when outreach asks**: the Virginia Telecommunication
   Initiative (VATI, the broadband grant localities apply for; its first box is "Looking for BEAD Information?"), the
   Virginia Homeless Solutions Program, the Continuum of Care, HIEE, the Disaster Assistance Fund and three flood
   relief programs, Weatherization Deferral Repair, RISE, Opportunity Zones technical assistance and CDBG-DR. Each
   has the program template but no box labelled `Eligibility`. A `HAND_ADDED` tuple of slugs read with the same parser
   is the one-line addition; it is not added today because a page without an eligibility box yields a record with no
   applicant, and the roadmap says build what a town asks for.
6. **The contact block's people are never read**: names, emails and phones on every program page.

## Known gaps (the source's wording, not the parser's)

- 10 or so program pages have no `Eligibility`-labelled box and are not records (decision 5); VATI is the one that
  matters for towns.
- Status is `unknown` on most records: the pages state cycles in words ("spring of every year"), not dates.
- `funding_type` is null where the name has no keyword (IRF, VAARC, VEZ, PHCRF): the page does not say grant or loan
  in a labelled field.
- `localities` tags municipality and county (shared tagger, 2026-11-03); "planning district commissions",
  "development authorities" and "public housing authorities" tag nothing or `housing_authority` only.

## Out of scope

CAMS (the application portal, login), the Resources and Helpful Links boxes (PDF manuals, recordings), the Codes and
Broadband sections' non-program pages, the GO Virginia regional council pages.

## Verification

- `tests/test_va_dhcd.py` against `tests/fixtures/va_dhcd/` (one section page, one landing page, one CDBG family page
  with "Learn More", and program pages: IRF, VAARC, CDBG Project Grants, CDBG Planning Grants, VEZ, VIDA, plus VHSP as a
  templated page that is not a program; contact names, emails and phones replaced by placeholders, scripts removed;
  written by `scripts/probe_va_dhcd.py`): teaser parsing and normalisation, the program marker, the box and intro
  parsing, the cycle sentence and its dates, every status branch, applicants, `fetch` as a crawl (depth, once per
  page, a failed section aborts, a failed program falls back to prior), `resolve_missing`.
- Two live runs: all added, then 0 changed.
