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

## Implemented (2026-11-14)

Three modules, each with its own reader: `sd_goed` (`<main>`, each repeated tab line read once, the CAPER notice dropped, the
read stopped at the "Planning Districts" tab), `sd_dot` (`<main>`, a list item that wraps paragraphs read through its
paragraphs once, the read stopped at the Commission's award announcements) and `sd_danr` (the main column, the first `h2` as
the title). First live runs on a copy of the restored database: **10 added, 0 errors**; second runs **0 changed**.
`scripts/probe_south_dakota.py` saved the fixtures.

| Record | Status on 2026-11-14 | Applicants tagged | Source |
|---|---|---|---|
| Community Development Block Grants | unknown: "Deadlines are April 1 and October 1." (kept) | municipality, county | pass_through |
| Local Infrastructure Improvement | unknown: quarterly deadlines, no year (kept) | municipality, county | direct |
| **Bridge Improvement Grants** | **open to 2027-01-02** | county | direct |
| Industrial Park Road Grants, Agri-Business Road Grants | unknown: "Applications are due April 15, July 15, or October 15." | municipality, county | direct |
| Community Access Grants | unknown: "Applications are due July 15." | municipality | direct |
| Transportation Alternatives | unknown: due 2026-10-01, past | none named on the page | pass_through |
| Drinking Water, Sanitary and Storm Sewer Project Funding (`loan`) | unknown: quarterly, "on or before the first day of January, April, July, and October" | special district, state, municipality, county, tribe, nonprofit | direct |
| Solid Waste Disposal and Recycling Project Funding (`loan`) | unknown, the same | individual, county, municipality, tribe, special district | direct |

**The South Dakota page lists 0 open rows on 2026-11-14.** Bridge Improvement Grants is open, but its applicants are counties
(a county with a wheel tax and a five-year plan), and the navigator lists programs a municipality can apply to. It is stored,
in the feeds and in the data; eight municipal records show under "Status not confirmed". No script errors and no sideways
scroll at 390px.

### Shared changes (`connectors/hand_list.py`)

Each measured on its own: the restored database (7,734 records) and the 158 fixture records of every other agency-page
connector (Arkansas's included). **Every change: 0 tag moves, 0 hash moves.**

- `YEARLESS_RE` on `AgencyPageConnector`, off by default: a module that sets it keeps the first sentence it matches (with no
  year in it) as `closes_at_text` when the status is `unknown` and nothing else was kept. Nebraska's DED and NDOT carry their
  own copies (12.6g); this is the third case, so it moved to the base. Nebraska's were not migrated (their hashes would have to
  be re-checked; a follow-up for a quiet session).
- `APPLICANT_SENTENCE_RE`: "grants will be made to ...", "Local governments interested in ...", "funds for towns ...", "to be
  eligible for ..., a county must ...", "sponsored by one of the following ...".
- Cut before tagging: a purpose clause ("for the development of new or expanded agri-business industries", "are for the
  construction or reconstruction of major streets ... schools, hospitals") and a program's name as the subject ("The
  Agri-Business grants will be made to ..."). Without them Agri-Business tagged `business` and Community Access `school`.

### Gaps and follow-ups

- **Emergency Management is not read**: the Office of Emergency Management is on `www.sd.gov`'s ServiceNow portal, a
  JavaScript shell. Ask Saj before any headless read (CLAUDE.md).
- **Game, Fish and Parks is deferred**: LWCF and Recreational Trails have no page this survey found. Reopen with the parks
  division's grants URL.
- SD Housing disallows `ClaudeBot`: not read.
- Transportation Alternatives names its applicants only in the application guide (a PDF): quoted by hand only if a round is
  open and the quote would put it on the page (Saj's 10.6 rule).
- Every municipal round on the page today is `unknown` because the agencies state deadlines without a year. If Saj ever
  relaxes the no-year rule ("the next April 1"), South Dakota is where it would show most.
