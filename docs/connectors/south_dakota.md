# South Dakota's agency pages: survey, scope and field mapping

Milestone 12.6i, the eighth agency state in the 12.6 cost ranking, built in the same session as Arkansas at Saj's word
(2026-11-14). Written from a read-only survey of the candidate agencies' hosts and pages, before any parser. South Dakota
has no state index (`docs/surveys/state_portals.md`: GOED's WordPress, the Municipal League's list behind a Cloudflare
challenge), so this is an agency state.

## Survey (2026-11-14, the connectors' own User-Agent, one GET per page)

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Governor's Office of Economic Development (GOED) | `sdgoed.com` | WordPress (a Tailwind theme; tab strips repeat each section once more for phones) | `User-agent: *`, nothing disallowed | **build** |
| Transportation (SDDOT) | `dot.sd.gov` | Umbraco 17 (Modern Logic); the program text is in `<main>`, menu links in single-quoted `href`s | no `robots.txt` (404) | **build** |
| Agriculture and Natural Resources (DANR), Environmental Funding | `danr.sd.gov/Funding/EnviromentalFunding/` | its own ASP.NET pages (Bootstrap; the text in the main `.col-xs-12` column of `.row-offcanvas`) | no `robots.txt` (404) | **build** |
| Game, Fish and Parks (LWCF, Recreational Trails) | `gfp.sd.gov` | its own ASP.NET | `User-agent: *`, `Crawl-delay: 5` | **defer**: no grants page in its 314-URL sitemap, `/grants/` redirects to the home page and `/parks/grants/` answers 500; the only grant link found (Partnerships) is a small shooting-range grant by e-mail. Reopen with the parks division's grants URL |
| Public Safety, Office of Emergency Management | `www.sd.gov/dps` | ServiceNow service portal (`ng-app`, `sp-page`) | | **stopped**: a JavaScript shell; reading it needs a headless browser (CLAUDE.md: stop and ask) |
| South Dakota Housing (`sdhousing.org`) | | | **`ClaudeBot` disallowed** | **not read**, the ADECA rule |

Three agencies, three platforms: no South Dakota base. Each module carries its own small reader, as Nebraska's do.

## Candidate programs and scope calls (each one line in a module's `PAGES`)

**GOED** (`sd_goed`, two records)

- **Community Development Block Grants**, `pass_through` (HUD named). "Deadlines are April 1 and October 1": a month and a day
  with no year, so `unknown` with the sentence kept (the Nebraska no-year rule). The CAPER notice's dates ("no later than
  August 3, 2026") are a comment period and are dropped; the read stops at the "Planning Districts" tab (forms and manuals).
- **Local Infrastructure Improvement Program**: "open to any political subdivision in South Dakota, tribal government, or
  local development corporation"; quarterly deadlines with no year: `unknown`.
- Out: the Community Based Child Care Grant ("now closed ... a one-time funding opportunity"), CDBG-DR (a disaster
  allocation page), REDI, bond and loan participation programs (businesses), BEAD (broadband providers), Workforce Development.

**SDDOT** (`sd_dot`, five records)

- **Bridge Improvement Grants** (counties with a wheel tax and a five-year plan): "2027 BIG Preservation/Replacement application
  deadline: Saturday, Jan. 2, 2027", so **open**. State money: `direct`.
- **Transportation Economic Development Grants**, one page, three programs named in its paragraphs, one record each through
  `SPLITS` on paragraphs: **Industrial Park**, **Agri-Business** ("any local unit of government"; "Applications are due April 15,
  July 15, or October 15") and **Community Access** ("towns less than 5,000"; "due July 1"). No year on any date: `unknown`. The
  Industrial Park record keeps the page's own `source_id`. The read stops at the Commission's award announcements.
- **Transportation Alternatives**, `pass_through` ("federal transportation funds"): "2027 Grant Applications - Due Thursday, Oct.
  1, 2026", past, so `unknown` with the date kept.
- Out: the Rural Access Infrastructure Fund (a formula allocation to counties by culvert count; local agencies apply to their
  county, the Missouri MoDOT rule), the Local Federal Bridge Program page (a list of documents and past awards, no program
  text), Urban Systems (an allocation), Emergency Relief (FHWA's), the transit pages (lists of eligible recipients, no round).

**DANR** (`sd_danr`, three records)

- **Drinking Water Project Funding**, **Sanitary and Storm Sewer Project Funding**, **Solid Waste Disposal and Recycling
  Project Funding**: grants and low-interest loans from the Board of Water and Natural Resources (the SRFs and the state's
  Consolidated Water Facilities Construction Program; "Applicants should expect to receive some portion of funding as a loan",
  so `loan`). Applications are taken quarterly, "on or before the first day of January, April, July, and October": no year,
  `unknown`. Applicants from the "Eligibility Requirements" list (a special purpose district, a municipality, county or
  township, a tribe). `direct`: the pages name the SRFs, not their federal funder.
- Out: Section 319 (the Watershed Protection pages are an overview and last year's application list, no program text), the
  Petroleum Release Compensation Fund (responsible parties), the Specialty Crop Block Grant (producers).

## Field mapping

The agency-page table in `connectors/hand_list.py` (as Arkansas): `name` from the page's `h1` (GOED, SDDOT) or its first
`h2` (DANR's `h1` is the division, "Environmental Funding"); `status`, `opens_at`, `closes_at` from `round_for`; applicants
from list items under an eligibility label and applicant sentences.

## Sample of the raw data

SDDOT's Transportation Economic Development Grants page (`<main>`):

```
p   The Industrial Park grants will be made to any local unit of government for the development of new or expanded access
    for new industry located within industrial parks. Applications are due April 15, July 15, or October 15.
p   The Agri-Business grants will be made to any local unit of government ... Applications are due April 15, July 15, or October 15.
p   Community Access Grants are state funds for towns less than 5,000 in population ... Applications are due July 1 ...
```

DANR's Drinking Water page (`.row-offcanvas > .col-xs-12`):

```
h2  Drinking Water Project Funding
h2  Eligibility Requirements
li  Be sponsored by one of the following entities: a special purpose district ...; a state agency or general purpose
    government such as a municipality, county, or township; a federally recognized Indian tribe ...
p   Application Deadlines and Award Dates Drinking water project applications are considered on a quarterly basis and must be
    postmarked or received by the department on or before the first day of January, April, July, and October.
```
