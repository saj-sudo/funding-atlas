# Kansas's agency pages: survey (12.9, 2026-11-24)

Kansas has no public state index of grants. Breadth first (Saj, milestone 12.9): the CDBG agency, then a second only if
cheap. Surveyed read-only with the connectors' User-Agent, **10 s or more between requests** (the site's `Crawl-delay`),
pages saved and read from disk.

| Agency | Host | CMS | robots | Result | Verdict |
|---|---|---|---|---|---|
| Department of Commerce (CDBG, Quality Places) | `www.kansascommerce.gov` | WordPress (Yoast; the "tardigrade" theme by Imagemakers), behind Cloudflare with no challenge | `User-agent: * / Disallow:` (empty), no `ClaudeBot` rule, **`Crawl-delay: 10`** | 200 on every page asked | **readable, built** (`ks_commerce`, `DELAY_S = 10.0`) |
| Kansas Infrastructure Hub | `kshub.gov` | - | - | walled by Akamai (the caller's survey) | **not read**, never fetched here |
| KDOT, KDHE (the revolving funds), Water Office, Emergency Management, Wildlife and Parks | other hosts | not surveyed | not asked: only `www.kansascommerce.gov` is on this session's network allowlist | never fetched | **not surveyed** (follow-up) |

## What Commerce gives

- `/program/community-programs/` ("Quality Places Programs") is a tile index: Broadband, CDBG, two tax credits, Kansas
  Community Empowerment, Main Street, RHID, STAR Bonds.
- **`/cdbg/`** is the CDBG hub: "Eligible Applicants" and ten cards, each a program with its maximum award and a status
  word ("Closed" on all ten today), each linking to a detail page on one template.
- **Each detail page** (`/cdbg/water-sewer/` read in the survey) has a strip of cells ("MAX AWARD", "MATCH", "APPLICATIONS
  CLOSED: Closed for 2026", a "Qualify" checklist), then "Program Overview": a status headline ("Applications for 2026 are
  closed.") and labelled paragraphs (Purpose, Qualifying Projects, Eligible Applicants, CDBG National Objective, Selection
  Criteria, Matching Funds), then FAQs and "How to Apply".
- `/grantscalendar/` is one table of every Commerce grant (33 rows): description, maximum, match, the months of the
  announcement, application period and awards, with no year and no applicant column.

## Scope: the ten CDBG programs, one record per detail page

Community Facilities: Large Grants; Community Facilities: Small Grants; Water & Sewer Infrastructure; Commercial Rehab;
Blueprint to Build; Housing; Youth Job Training; Economic Development; Regional Water Implementation; Urgent Need for
Disasters. All ten are applied for by cities and counties. Urgent Need is the regular program's urgent-need category, not
CDBG-DR, so it is in.

Out, and listed under Gaps: Commerce's other grants on the calendar that a town can apply for (HEAL, SEED, Towns, Rural
Champions, ROOMS, SIGNS, the tourism grants), each on a page of its own, deferred to keep the first read at ten pages and
the host under fifteen requests; the tax credits (CSP, IDA), RHID and STAR Bonds (incentives and financing districts);
the Arts Commission's grants (arts organizations); broadband (providers); apprenticeship and export grants (employers).
The calendar itself is not read: it has no year and no applicants.

## Sample of the raw data (`/cdbg/water-sewer/`, 2026-11-24)

```
p.im-cdbg-hero-headline   Water & Sewer Infrastructure
p.im-cdbg-hero-desc       This program supports efforts to ensure reliable, safe, and sustainable water and wastewater
                          services for communities across Kansas.
cell   MAX AWARD | Up to $2,000 per beneficiary with a maximum of | $800,000
cell   MATCH | 25% | of the CDBG grant request
cell   APPLICATIONS CLOSED | Closed for 2026          (a commented-out line beside it reads "May 1, 2023": comments are not read)
cell   Qualify: Benefit Low- to Moderate-Income persons / At least 25% matching funds / Approved Pre-Application
h2     Program Overview
h1     Applications for 2026 are closed.
label  Purpose
p      The Water and Sewer Infrastructure Grant Program provides vital funding for projects that improve the reliability,
       safety, and sustainability of water and wastewater systems in Kansas communities. ...
label  Eligible Applicants
p      Only cities and counties (units of local government) can apply for CDBG grants. Large cities and urban counties are
       considered entitlement communities and receive CDBG funds directly from HUD ... The following entitlement
       communities are NOT eligible to apply for the state CDBG program: Kansas City, Lawrence, ...
label  Matching Funds
p      Local funding is required for all CDBG projects, and no project can be funded entirely by grants. ...
h2     FAQs                                             (not read)
h2     How to Apply                                     (not read)
```

## Field mapping

The agency-page table in `connectors/hand_list.py`, with a reader of this module's own (the theme's CDBG template; no
other Kansas agency is read).

- **Text**: three parts of `section.body-content`, in page order: the hero's description; each cell of the `#deadline`
  strip as one line, its title, a colon and its text ("MATCH: 25% of the CDBG grant request"), the "Qualify" checklist as
  a label and its items; the `#overview` section, where a `p.im-cdbg-overview-subtitle` is a label and the `h1` headline
  a paragraph. `#faqs` (hearing timelines, environmental review) and `#apply` (a community picker run by script, a
  sign-up form) are not read. Lines with a phone number or an e-mail address are dropped.
- `name`: `p.im-cdbg-hero-headline` with "CDBG" in front (the page's `h1` in the hero is the template's "CDBG Interior
  Page"; a headline is "Housing Rehabilitation & Demolition" or "Economic Development", which names nothing in a list of a
  state's programs; the Grants Calendar writes "CDBG | Economic Development"). Three headlines are printed in capitals
  ("URGENT NEED FOR DISASTERS") and are set in title case.
- `status`: the shared table. "Applications for 2026 are closed." is closed wording: `closed`, the sentence kept,
  `closes_at` null (Small Grants' cell says "March 2 – Oct. 30, 2026", a window that is over; it stays in the text). A
  cell that states a deadline with its date ("APPLICATION DEADLINE: May 1, 2027") would read as a round through the same
  table; that shape is a test on an edited fixture, **not seen live**.
- `eligibility_text`, applicants: the first paragraph under "Eligible Applicants" ("Only cities and counties (units of
  local government) can apply for CDBG grants. ..."; Housing: "Only cities (not counties) ..."). A second paragraph under
  that label ("Eligible Properties", "Eligible Businesses") is about what a project may assist and is not read as
  applicants. Blueprint to Build and Youth Job Training have no such section: the hub's sentence is quoted, dated and
  attributed (`HAND_QUOTES`, the MDOT and Illinois precedent), and its ", excluding the federal entitlement areas: ..." is
  cut before tagging.
- `funding_type`: `grant`; Economic Development `loan` ("operates as a loan that must be repaid").
- `match_required`: the shared rule over the page text (`True` on nine; Urgent Need, whose match is "the cost of the
  Environmental Review", stays null).
- `funding_source`: `pass_through`: eight pages name HUD, the other two are set by hand (one federal program).
- Categories: `community development`; the two water programs `environment and water`, Housing `housing`, Youth Job
  Training `workforce development`.
- Amounts are not parsed ("MAX AWARD" stays in the stored text): the amount parser is deferred (roadmap).
- Two pages (Blueprint to Build, Housing) leave a tag open, so in the markup `#overview` contains `#faqs` and `#apply`; the
  reader cuts the section at the first of them. Blueprint's "Additional Resources" (links) ends its read.

## Implemented (2026-11-24)

`connectors/ks_commerce.py` (`AGENCY_CODE` `KS-COMMERCE`, `DELAY_S = 10.0`), `scripts/probe_kansas.py` (saved the fixtures,
ten seconds between GETs; its scrub also removes the site chrome, staff cards and every line with an e-mail address, a
phone number or a named contact), `tests/test_kansas.py` (7 tests). One live probe run, 2026-11-24, 10 GETs, no errors.
The module was not run through `cli.py run` (the pipeline's registry is edited centrally), so no database run is recorded
here. The probe's lines (ids, status, dates, source; tags and names as the finished reader gives them from the saved pages):

```
== ks_commerce
  large-grants          closed  open=None close=None pass_through ['county', 'municipality'] | Applications for 2026 are closed.
  small-grants          closed  open=None close=None pass_through ['county', 'municipality'] | Applications for 2026 are closed.
  water-sewer           closed  open=None close=None pass_through ['county', 'municipality'] | Applications for 2026 are closed.
  commercial-rehab      closed  open=None close=None pass_through ['county', 'municipality'] | Applications for 2026 are closed.
  blueprint-to-build    closed  open=None close=None pass_through ['county', 'municipality'] | Applications for 2026 are closed.
  housing               closed  open=None close=None pass_through ['municipality']           | Applications for 2026 are closed.
  youth-job-training    closed  open=None close=None pass_through ['county', 'municipality'] | Applications for 2026 are closed.
  economic-development  closed  open=None close=None pass_through ['county', 'municipality'] | Applications for 2026 are closed.
  regional-water        closed  open=None close=None pass_through ['county', 'municipality'] | Applications for 2026 are closed.
  urgent-need           closed  open=None close=None pass_through ['county', 'municipality'] | Applications for 2026 are closed.
```

The live run printed the same ten ids, `closed` and the same sentence on every line. Four things were changed after it,
on the saved pages, without a second request (the host was at its budget): the applicant tags (the live run tagged
`business` on Commercial Rehab and Economic Development, municipality alone on Blueprint to Build, from an FAQ
sentence, and nobody on Youth Job Training), Youth Job
Training's source (`direct` live, before the hand entry), the names, and the FAQ cut. **The finished reader has not been
run against the live site**; the first daily run is that check.

| Record | Status on 2026-11-24 | Applicants tagged | Type, source |
|---|---|---|---|
| CDBG Community Facilities: Large Grants | closed ("Applications for 2026 are closed.") | municipality, county | grant, pass_through |
| CDBG Community Facilities: Small Grants | closed | municipality, county | grant, pass_through |
| CDBG Water & Sewer Infrastructure | closed | municipality, county | grant, pass_through |
| CDBG Commercial Rehabilitation | closed | municipality, county | grant, pass_through |
| CDBG Blueprint to Build | closed | municipality, county (the hub's sentence) | grant, pass_through (by hand) |
| CDBG Housing Rehabilitation & Demolition | closed | municipality | grant, pass_through |
| CDBG Youth Job Training | closed | municipality, county (the hub's sentence) | grant, pass_through (by hand) |
| CDBG Economic Development | closed | municipality, county | loan, pass_through |
| CDBG Regional Water Implementation | closed | municipality, county | grant, pass_through |
| CDBG Urgent Need for Disasters | closed | municipality, county | grant, pass_through |

Requests to `www.kansascommerce.gov` in this session: 14 (the community programs index, `/cdbg`, `/grantscalendar`, one
detail page in the survey, ten in the probe), ten seconds or more apart, plus the caller's `robots.txt`.

### Shared rule wished for, not made (`connectors/hand_list.py` is edited centrally)

- `APPLICANT_SENTENCE_RE` does not know "**can apply**" ("Only cities and counties (units of local government) can apply
  for CDBG grants."); it has "may apply" and "can now apply". Solved here by reading the label's first paragraph whole.
- The tagger drops a sentence with "excluding" as a negation, so "awarded to local units of government in cities or
  counties in Kansas, excluding the federal entitlement areas: ..." tags no one. Solved here by cutting the clause.

### Gaps and follow-ups

- **Next year's round**: the pages say only that 2026 is closed. The calendar gives months with no year ("Mar.-Oct.",
  announced "Jan."); when the 2027 round is posted the strip's third cell should carry it. Check the reader on that day.
- **Commerce's other grants a town can apply for**, each a page of its own, none read: HEAL, SEED, Towns, Rural Champions,
  ROOMS, SIGNS, the Tourism Attraction Development and Tourism Marketing grants. The Grants Calendar (`/grantscalendar/`,
  one table, 33 rows) lists them with maximum, match and months, and would be a cheap index for a second session; it states
  no applicants and no year. **12.11 (2026-11-25)**: the calendar links none of the program pages (one link, a 2026-10 news
  post, "Towns Grant Funding Available for Rural Quality-of-Place Projects"), and `/officeofruralprosperity/` answers 404;
  stopped there after two requests rather than guess URLs against `Crawl-delay: 10`. The next try starts from the site's
  own menu or sitemap.
- Kansas Main Street, Kansas Community Empowerment and the Office of Broadband Development pages were not opened.
- Other agencies (KDOT's local programs, KDHE's revolving funds and waste grants, the Water Office, Emergency Management,
  Wildlife and Parks' LWCF and trails) were not surveyed: their hosts are not on this session's network allowlist. The
  Kansas Infrastructure Hub (`kshub.gov`) is walled by Akamai and was not fetched.
- "MAX AWARD" and the allocation sentences ("A total of $1.5 million has been allocated ...") wait for the amount parser.
