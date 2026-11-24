# Florida's agency sources: survey and two connectors (12.9, 2026-11-24)

Florida has no public state index of grant programs. Surveyed read-only with the connectors' User-Agent, one `robots.txt`
a host, at least 3 s apart (10 s on `floridadep.gov` while surveying).

| Agency | Host | Platform | robots | Result | Verdict |
|---|---|---|---|---|---|
| FloridaCommerce (CDBG, Rural Infrastructure Fund) | `floridajobs.org` | — | — | Azure WAF, blocked for good (earlier probe) | **blocked**, never fetched here |
| Department of State (arts, historic preservation, libraries, elections) | `www.dosgrants.com` | ASP.NET MVC behind Cloudflare | none: `/robots.txt` answers 200 with the site's HTML "Page Not Found" | `/Program` 200, a server-rendered table, no login | **readable**: `fl_dos` |
| Department of Environmental Protection | `floridadep.gov` | Drupal (nginx) | stock Drupal file, no `ClaudeBot` rule; `# Crawl-delay: 10` is commented out | every page 200 | **readable**: `fl_dep` |

## What each gives

**DOS Grants** (`https://www.dosgrants.com/Program`, "Below is a list of all grants"): one table, 19 rows in five groups
("Division: Arts and Culture", "Elections", "Historical Resources", "Library and Information Services", and one group with
no division name). Columns: Program Name, Description, Application Period (`6/1/2026 - 7/10/2026`), Actions (empty without
a login). It lists every program the system has ever taken applications for, the finished ones too ("The Florida CARES
Program is no longer active."). Applying needs an account; reading the list does not.

**DEP**: the Land and Recreation Grants Section (`/lands/land-and-recreation-grants`) links FRDAP, LWCF, ORLP, the
Readiness and Recreation Initiative, RTP, the Florida Communities Trust and the Stan Mayfield Working Waterfronts programs;
the Division of Water Restoration Assistance (`/wra`) links the State Revolving Fund, the Water Quality Improvement Grant
Program, the Nonpoint Source (319) program, the Springs and Watershed Restoration Program and Water Supply Restoration.
LWCF's and RTP's program pages are three paragraphs and four links; who applies, the match and the cycle are on each
one's "Application Process, Submission Cycles, and Funded Projects" page, so that is the page read.

## Scope calls

`fl_dos`, 9 records of 19 rows:

- **Out, by the site's own word**: a row whose description says "no longer active" or "no longer being accepted" (the
  African-American Cultural and Historical Grant, America 250, Fast Track Project, Florida ARP, Florida CARES).
- **Out, by name** (`OUT`, one line each to overrule): Albert Network Monitoring Solution Grant (no description, one round
  ended 3/31/2025), Federal Election Security ("non-recurring funds ... for fiscal year 2022-2023"), DLIS Florida ARPA and
  DLIS Florida CARES Act (one-time federal relief rounds, 2021 and 2020), Library Cooperative Grants ("Eligible applicants
  are the five Multitype Library Cooperatives"), Cultural Endowment (a state match for designated Cultural Sponsoring
  Organizations' endowments).
- **In**: Cultural Facilities, General Program Support and Specific Cultural Project (one row, "GPS/SCP", headed by two
  bold names: two records, Saj's one-record-per-program rule), Post-Election Voting System Audit (counties' election
  systems), Abandoned African-American Cemeteries, Small Matching, Special Category, Library Services and Technology Act,
  Public Library Construction ("Eligible applicants are municipal and county governments").
- Names are the table's ("Small Matching", "Special Category"), not lengthened.

`fl_dep`, 7 records from 6 pages: FRDAP, LWCF, RTP, the Florida Communities Trust's Parks and Open Space grants, the State
Revolving Fund page as two (Clean Water, Drinking Water; "State Revolving Fund Management" is an office, no record), the
Water Quality Improvement Grant Program. Not built (follow-ups below): ORLP, the Readiness and Recreation Initiative,
Stan Mayfield Working Waterfronts, 319, Springs and Watershed Restoration, Water Supply Restoration, Resilient Florida.

## Sample of the raw data

DOS Grants, one row (2026-11-24):

```
tr.k-grouping-row   Division: Library and Information Services
td  Public Library Construction
td  Eligible applicants are municipal and county governments. Public Library Construction grants are for the construction
    of public libraries. ... More information regarding the program is available <a>here</a>.
td  6/1/2026 - 7/10/2026
```

DEP, RTP's cycle page (2026-11-24):

```
h1  RTP: Application Process, Submission Cycles, and Funded Projects
p   Florida currently receives an annual appropriation of Recreation Trails Program funds from the Federal Highway
    Administration ...
p   Eligible applicants include agencies of city, county, state or federal governments, and nonprofit organizations
    approved by the state, and state or federally recognized Indian tribal governments. ... All grant awards require a
    match in funding from the project sponsor. ...
h3  FY2025-2026 RTP Grant Submission Cycle (Closed)
td  April 13, 2026-May 28, 2026
h3  FY2025-2026 RTP Application Materials   (the read stops)
```

## Field mapping

`fl_dos` (its own module, a table like `nm_dfa`; the page is read with `hand_list.get`):

- `source_id`: the name, slugged (`public-library-construction`); the table prints no id. `source_url`: the table's
  address; the row's "here" link is kept in `eligibility_structured.more_information` beside `division`.
- `status`, `opens_at`, `closes_at`: the Application Period against the run date: forecasted before it, open inside it,
  `unknown` with both dates kept after it (a past round is not a closure of the program). `closes_at_text`: "Application
  Period: 6/1/2026 - 7/10/2026".
- `summary`: the description without "More information regarding the program is available here."
- `eligibility_text` and applicants: only the sentences that start "Eligible applicants are". "Applicants must be
  associated with an Organization" is about the system's account type and is not read (so the arts and historic
  preservation records carry no applicant tag: the table does not say who applies).
- `funding_source`: `pass_through` where the row says "are federal funds" or "Federal Grants Trust Fund" (LSTA), else
  `direct`. The historic preservation rows say the Division "provides state and federal funds" and that "the Legislature
  determines the amount appropriated annually for the program": `direct`.
- `categories`: the division through the portal table (`other` for all four today).
- A fetch failure returns the stored records; a row that leaves the table is `unknown`.

`fl_dep` (the agency-page table in `connectors/hand_list.py`, a reader of its own):

- **Text**: the `article` in `main#main-content`; table header rows are dropped; a body cell or a `div` with no block
  inside it is a paragraph (FCT's text is bare `div`s, the cycles are in tables). The read stops at a heading that ends in
  "Webinar Materials", "Application Materials", "Priority List(s)", "Funded Projects", or is "More Information" or
  "Contacts". Contact lines, the dashboard paragraph and the SRF section's "Learn More" links are dropped.
- `name`: the `h1`; LWCF and RTP from `NAMES` (their cycle pages are titled "LWCF: Application Process, ...").
- `status`, in this order after the shared table: a date range under a "Submission Cycle" / "Application Cycle" heading
  ("November 15 - December 15, 2025", the year printed once) is the window: forecasted, open, or `unknown` once past;
  the page's own word then decides: "Closed on October 15, 2026" or "Cycle Closed Oct. 15, 2026" is `closed` with that
  date, a cycle heading that says "(Closed)" over a past window is `closed`; "a Request for Inclusion form, which can be
  submitted any time during the year" is `open` and rolling; a cycle printed as "TBD" stays `unknown` with the heading and
  that word as `closes_at_text`.
- Applicants: the shared reader, plus this agency's wordings (`APPLICANT_RE`): "loans to local governments", "are eligible
  loan sponsors", "All local governments ... may submit", "A local government entity is ...", "funding to Florida's
  governmental entities (cities, counties, municipalities, etc.)". One tag per type.
- `match_required`: the shared rule, plus "provided on a 50:50 (Program: Grantee) matching basis" (LWCF).
- `funding_type`: SRF is `loan` (`FUNDING_TYPES`). `funding_source`: RTP names the Federal Highway Administration; SRF
  ("funded through money received from federal grants as well as state contributions") and LWCF ("contingent upon
  appropriation by the federal government") are set `pass_through` in `FUNDING_SOURCES`; the rest `direct`.
- `categories`: "parks and recreation"; "clean water", "drinking water" and "water quality" for the three water records.
- Amounts ("may not exceed $200,000.00", "$1.5 million") are not parsed (the amount parser is still deferred).

## Implemented (2026-11-24)

`connectors/fl_dos.py`, `connectors/fl_dep.py`, `scripts/probe_florida.py`, `tests/test_florida.py` (12 tests),
fixtures in `tests/fixtures/fl_dos/program.html` and `tests/fixtures/fl_dep/<slug>.html` (scripts, chrome, images, mail
links, e-mail addresses, phone numbers and each page's "Contacts" block removed). Neither connector is registered in
`pipeline/run.py` or the workflow yet (done centrally).

`fl_dos`, the probe's live run on 2026-11-24:

```
== fl_dos
  cultural-facilities                        unknown    open=2026-06-01 close=2026-07-10 direct       [] | Application Period: 6/1/2026 - 7/10/2026
  general-program-support-gps                unknown    open=2026-06-01 close=2026-07-10 direct       [] | Application Period: 6/1/2026 - 7/10/2026
  specific-cultural-project-scp              unknown    open=2026-06-01 close=2026-07-10 direct       [] | Application Period: 6/1/2026 - 7/10/2026
  post-election-voting-system-audit          unknown    open=2026-07-15 close=2026-08-05 direct       [] | Application Period: 7/15/2026 - 8/5/2026
  abandoned-african-american-cemeteries      unknown    open=2026-06-01 close=2026-07-10 direct       [] | Application Period: 6/1/2026 - 7/10/2026
  small-matching                             unknown    open=2026-06-01 close=2026-07-10 direct       [] | Application Period: 6/1/2026 - 7/10/2026
  special-category                           unknown    open=2026-06-01 close=2026-07-10 direct       [] | Application Period: 6/1/2026 - 7/10/2026
  library-services-and-technology-act        unknown    open=2026-06-01 close=2026-07-10 pass_through ['nonprofit'] | Application Period: 6/1/2026 - 7/10/2026
  public-library-construction                unknown    open=2026-06-01 close=2026-07-10 direct       ['municipality', 'county'] | Application Period: 6/1/2026 - 7/10/2026
```

`fl_dep`: the probe ran live once on 2026-11-24 against the first page list (six GETs, all 200); LWCF and RTP were then
moved to their cycle pages (fetched live the same hour, one GET each) and the status rules written. The lines below are
the finished module over those same live pages as saved; the probe was **not** run a second time, to stay inside the
request budget for the host:

```
== fl_dep
  frdap                                      closed     open=None close=2026-10-15 direct       ['municipality', 'county', 'special_district'] | The 2027-2028 FRDAP Application Cycle Closed Oct. 15, 2026
  lwcf                                       unknown    open=2025-11-15 close=2025-12-15 pass_through ['municipality', 'county'] | November 15 - December 15, 2025
  rtp                                        closed     open=2026-04-13 close=2026-05-28 pass_through ['municipality', 'county', 'nonprofit', 'tribe'] | FY2025-2026 RTP Grant Submission Cycle (Closed): April 13, 2026-May 28, 2026
  fct-parks                                  unknown    open=None close=None direct       ['municipality', 'county', 'nonprofit'] | 2026-27 Grant Submission Cycle and Webinar: TBD
  srf                                        open       open=None close=None pass_through ['municipality', 'county', 'special_district'] | The first step in the process for SRF funding, both Clean Water and Drinking Wat
  srf#drinking-water                         open       open=None close=None pass_through ['municipality', 'county', 'special_district'] | The first step in the process for SRF funding, both Clean Water and Drinking Wat
  water-quality                              unknown    open=None close=None direct       ['municipality', 'county'] |
```

| Record | Status on 2026-11-24 | closes_at |
|---|---|---|
| Florida Recreation Development Assistance Program | closed ("Cycle Closed Oct. 15, 2026") | 2026-10-15 |
| Land and Water Conservation Fund Program | unknown (FY2025-2026 window past, not called closed) | 2025-12-15 |
| Recreational Trails Program | closed ("Submission Cycle (Closed)") | 2026-05-28 |
| Parks and Open Space Florida Forever Grant Program | unknown ("Grant Submission Cycle: TBD") | — |
| Clean Water State Revolving Fund | open, rolling (Request for Inclusion any time during the year) | — |
| Drinking Water State Revolving Fund | open, rolling | — |
| Water Quality Improvement Grant Program | unknown (no round stated) | — |

## Gaps and follow-ups

- **FloridaCommerce** (the state CDBG, Rural Infrastructure Fund, Community Planning Technical Assistance) is Florida's
  municipal core and is walled. Reopen only if a runner probe gets through or the agency gives permission.
- DOS Grants: the arts and historic preservation rows do not say who applies; the program pages they link are on
  `dos.fl.gov` / `dos.myflorida.com` (not on the allowlist, not fetched). A follow-up could read applicants there.
- DOS Grants prints no round for the next year until the Department edits the row: every record is "Status not confirmed"
  between rounds, with last round's dates.
- `fl_dep` not built: ORLP, the Readiness and Recreation Initiative, Stan Mayfield Working Waterfronts (three more
  `PAGES` lines under the same section), 319 / State Water Quality Assistance (`/wra/319-tmdl-fund`), Springs and
  Watershed Restoration (`/wra/wra`), Water Supply Restoration, and Resilient Florida (under `/rcp`; its page was not
  located in this session).
- The Drinking Water SRF's "private utilities" gets no tag from the shared tagger (the text is stored).
- The live `fl_dep` run of the finished module (see above) is the first daily run's job.
