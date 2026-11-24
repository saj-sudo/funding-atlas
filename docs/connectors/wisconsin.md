# Wisconsin's agency pages: survey and one connector (12.9, 2026-11-24)

Wisconsin has no public state grants index (`docs/surveys/state_portals.md`). Breadth first: the CDBG agency, which is
the Department of Administration's Division of Energy, Housing and Community Resources (DEHCR). Surveyed read-only with the
connectors' User-Agent, 3 s between requests, pages saved to disk and read from the saved copy.

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Department of Administration (home, Local Governments & Grants menu) | `doa.wi.gov` | SharePoint | `User-agent: *`, disallows only `/_layouts/`, `/_vti_bin/`, `/_catalogs/`; no `Crawl-delay`, no `ClaudeBot` rule | readable; home page only (its CDBG links all point to DEHCR's host) |
| DOA, Division of Energy, Housing and Community Resources (CDBG) | `energyandhousing.wi.gov` | SharePoint (publishing pages, a Bootstrap theme) | `/robots.txt` answers a SharePoint 404: no restriction | **readable**, built: `wi_doa` |

Every page asked for answered 200. The body is in the HTML (`main#main`, the page's rich-text fields), not delivered by
script.

## What DEHCR gives

`/Pages/CommunityResources.aspx` lists the State CDBG programs, one sentence each, and links one page per program:

| Program | Page | In? |
|---|---|---|
| Public Facilities (CDBG-PF) | `/Pages/AgencyResources/CDBG-PF.aspx` | in |
| Planning (CDBG-PLNG) | `.../CDBG-PLNG.aspx` | in |
| Public Facilities for Economic Development (CDBG-PFED) | `.../CDBG-PFED.aspx` | in |
| Economic Development (CDBG-ED) | `.../CDBG-ED.aspx` | in (the local government is the applicant, for a business) |
| Emergency Assistance (CDBG-EAP) | `.../CDBG-EAP.aspx` | in |
| Affordable Housing Conversion (CDBG-AHC) | `.../AffordableHousingConversion.aspx` | in (grants to local governments; a dated 2027 round) |
| Disaster Recovery (CDBG-DR) | `.../CDBG-DR.aspx` | out by the brief; not opened |
| Coronavirus (CDBG-CV) | `.../CDBG-CV.aspx` | out: a closed one-time program; not opened |
| Housing Regions Revolving Loan Program (CDBG-HSG) | `.../CDBG.aspx` | follow-up; not opened |
| Flexible Facilities Program | on the hub | out: "no new awards will be made" |
| CDBG-CLOSE | no longer listed anywhere on the hub or the menu | gone |

### Scope calls

- One record per program page, six records. The connector id is `wi_doa` (the agency is DOA; the host is its division's).
- CDBG-ED is in although a business benefits: "The business will work with the Unit of General Local Government (UGLG) to
  complete the application", and the grant is "awarded to local governments".
- **The Planning page never says who may apply** (it speaks of "community efforts" and "Applicants"). The hub's sentence
  does, and is quoted by hand, dated and attributed (`HAND_QUOTES`, the MDOT and Illinois precedent): "Planning Program
  (CDBG-PLNG) – provides grant funds to local governments to support planning efforts that improve community opportunities
  and vitality." The hub is not fetched by the connector.
- The other housing pages on the host's menu (HOME, HTF, HCRI, the homeless programs) fund developers, agencies and
  nonprofits and were not opened.

## Sample of the raw data (CDBG-PF, 2026-11-24)

```
h1  CDBG - Public Facilities Program (PF)
h2  Program Overview
p   Public Facilities (PDF) funds help support infrastructure and facility projects for communities. Grants are awarded
    to units of general local government and are limited to projects that meet a CDBG National Objective, including:
li  addressing the needs of and primarily serving individuals with a low- to moderate-income (LMI) status;
...
h3  Application Submission
p   The 2027 CDBG-PF applications due date is to be announced. Typically applications are due in mid-May each year.
p   INCOME SURVEY NOTICE: ... no later than February 15th* of the year they are applying ...
h2  Contact Information      (the read stops)
```

and Affordable Housing Conversion's timeline:

```
p   Timeline:
p   NOFO Posted: November 2026
p   Application Available: January 18, 2027
p   Applications Due May 15, 2027
p   Anticipated Award Date: August 2027
```

## Field mapping

The agency-page table in `connectors/hand_list.py` (`AgencyPageConnector`), with a reader of this module's own (Kentucky's
and Maryland's SharePoint readers were read for ideas and are not imported: other themes, other field ids).

- **Text**: `main#main`; `h2`/`h3`/`h4`, `p`, `li`; zero-width spaces (SharePoint leaves dozens) removed. A list item that
  wraps a paragraph is read once. The read stops at the first "Contact ..." heading or "CDBG Program Quick Links". Lines
  with a phone number or an e-mail address, the mailing address, and lines that are only a document link ("... (PDF)",
  "... (Word)", "... (Excel)") are dropped.
- `name`: the `h1` ("CDBG - Public Facilities Program (PF)").
- `status`: the shared `round_for`, with rules of this module's own, each the page's words:
  - "Applications are accepted on a continuous basis" (PLNG) and "applications may be submitted at any time" (PFED) are
    `open` and rolling;
  - "Application Available: January 18, 2027" (AHC) is the opening date, so a deadline still ahead reads `forecasted`
    until that day;
  - with no dated round, the sentence that states the cycle is kept as `closes_at_text` and the status stays `unknown`:
    "Typically applications are due in mid-May each year." (PF), "... must submit a notice of intent to apply within 90
    days of the disaster event." (EAP).
- Applicants: the shared reader plus this module's own sentence forms, "Grants are awarded to units of general local
  government", "grant funds ... are awarded to local governments", "funds are used to assist local units of government",
  "supports local governments in funding ...". The purpose clause "to assist businesses to create or retain jobs ..." is cut
  before tagging (the business benefits and does not apply); the stored text keeps it.
- `funding_source`: `pass_through` on every record, set by hand (State CDBG is HUD money; the hub says "Funding for CDBG
  programs is provided by the U.S. Department of Housing and Urban Development (HUD)", and not every program page repeats
  it).
- Categories: `infrastructure` (the "community development" label).

## Implemented (2026-11-24)

`connectors/wi_doa.py`; `scripts/probe_wisconsin.py` saves the fixtures (`tests/fixtures/wi_doa/`; contact lines are taken
out of the fixtures as well as out of the records). `tests/test_wisconsin.py`: 6 tests.

The probe ran live once on 2026-11-24 and every page answered 200, but that first version of its scrub removed `<form>`
elements, and SharePoint wraps the whole page in one, so the fixtures it wrote were empty and it printed six bare
`unknown` lines. The scrub was fixed (forms kept) and **the fixtures were rebuilt from the copies of the same six pages
saved during the survey a few minutes earlier, without asking the site again** (the host was already at 14 requests). Each
rebuilt fixture parses to exactly the blocks of its raw page. The per-record lines from that rebuild:

```
== wi_doa
  public-facilities                        unknown    open=None close=None rolling=None pass_through ['county', 'municipality'] | Typically applications are due in mid-May each year.
  planning                                 open       open=None close=None rolling=True pass_through ['county', 'municipality'] | Applications are accepted on a continuous basis.
  public-facilities-economic-development   open       open=None close=None rolling=True pass_through ['county', 'municipality'] | CDBG-PFED applications may be submitted at any time, and are reviewed by DOA as they are r
  economic-development                     open       open=None close=None rolling=True pass_through ['county', 'municipality'] | CDBG-ED applications may be submitted at any time, and are reviewed by DEHCR as they are r
  emergency-assistance                     unknown    open=None close=None rolling=None pass_through ['county', 'municipality'] | A local unit of government interested in applying for CDBG-EAP funds must submit a notice
  affordable-housing-conversion            forecasted open=2027-01-18 close=2027-05-15 rolling=None pass_through ['county', 'municipality'] | Applications Due May 15, 2027
```

| Record | Name | Status on 2026-11-24 | `closes_at` |
|---|---|---|---|
| `public-facilities` | CDBG - Public Facilities Program (PF) | unknown ("The 2027 CDBG-PF applications due date is to be announced. Typically applications are due in mid-May each year.") | none |
| `planning` | CDBG - Planning Program (PLNG) | open, rolling | none |
| `public-facilities-economic-development` | CDBG - Public Facilities Economic Development Program (PFED) | open, rolling | none |
| `economic-development` | CDBG - Economic Development Program (ED) | open, rolling | none |
| `emergency-assistance` | CDBG - Emergency Assistance Program (EAP) | unknown (a notice of intent within 90 days of a disaster) | none |
| `affordable-housing-conversion` | Affordable Housing Conversion Program | forecasted (application available 2027-01-18) | 2027-05-15 |

Not run through `pipeline/run.py` or against the database in this session (the runner's registry is edited centrally): the
module was imported and `SITE.fetch` / `normalize` exercised directly.

### Gaps and follow-ups

- The corrected `scripts/probe_wisconsin.py` has not itself been run against the live site (see above); its `scrub` is the
  function that rebuilt the fixtures.
- **Shared rules this module carries on its own** and a later state may want in `hand_list.py`: "accepted on a continuous
  basis" / "may be submitted at any time" as open and rolling; "Application Available: <date>" as an opening date; the
  applicant sentences "Grants are awarded to ..." and "funds are used to assist ..." (the shared pattern needs "will be
  awarded to"); cutting "to assist businesses ..." and "in addressing ... business assistance needs" before tagging.
- PF's round: when the page dates the 2027 deadline ("due date is to be announced" today) the shared rule reads it with no
  change here.
- CDBG-HSG (the Housing Regions revolving loan program, `/Pages/AgencyResources/CDBG.aspx`) was not opened: its grants go to
  a lead local government per housing region; a follow-up.
- `doa.wi.gov` itself: only the home page was read. Its "Local Governments & Grants" menu links Coastal Management (the
  Wisconsin Coastal Management Program's grants, which local governments apply for), Local Projects and the Municipal
  Services Payment program; none was opened. Coastal Management is the next candidate on that host.
- Not surveyed (other hosts, none on this session's allowlist, none requested): WisDOT's local programs, DNR's
  Environmental Loans and recreation grants, Wisconsin Emergency Management, WEDC, the Board of Commissioners of Public
  Lands.
