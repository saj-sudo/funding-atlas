# Arkansas's agency pages: survey, scope and field mapping

Milestone 12.6h, the seventh agency state in the 12.6 cost ranking (after Vermont, Connecticut, North Dakota, Kentucky,
Missouri and Nebraska). Written 2026-11-14 from a read-only survey of the candidate agencies' hosts and pages, before any
parser. Arkansas has no state index (`docs/surveys/state_portals.md`: "none found"), so this is an agency state. Agencies
are built one at a time, each its own commit; this doc grows with them.

## Survey (2026-11-14, the connectors' own User-Agent, one GET per page, the robots file's delay where it sets one)

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Agriculture, Natural Resources Division (the former ANRC: water and wastewater financing, dam safety, Section 319) | `agriculture.arkansas.gov` | the state's WordPress (Elementor, Yoast; shared post types `alert-banner`, `dashboard-info-panel`) | `User-agent: *`, only `/wp-content/uploads/` disallowed | **build** |
| Emergency Management (ADEM, a division of Public Safety) | `dps.arkansas.gov/emergency-management/adem/grants-funding/` | the same state WordPress | `User-agent: *` open, **`Crawl-delay: 10`** | **build**, ten seconds between GETs |
| Office of Outdoor Recreation (Parks, Heritage and Tourism) | `adpht.arkansas.gov/office-of-outdoor-recreation/arkansas-outdoor-grants/` | the same state WordPress (its body is a Dynamic Content for Elementor widget, not the theme's post-content widget) | `User-agent: *` open, **`Crawl-delay: 10`** | **build**, ten seconds between GETs |
| Economic Development Commission (AEDC: CDBG, Rural Services, Site Development) | `www.arkansasedc.com` | Sitefinity 15.2 (bare `div`s for paragraphs inside `.page-content`) | `User-agent: *`; disallows one loan page and `/_self` | **build**, its own reader (no second Sitefinity agency) |
| Transportation (ARDOT: TAP, RTP, Safe Routes) | `ardot.gov` | | **`ClaudeBot: Disallow: /`** (with a list of AI crawlers) | **not read**, the ADECA rule (decision 2026-10-18), as Nebraska's Game and Parks and NIFA |
| Energy and Environment (ADEQ) | `adeq.state.ar.us`; `energy.arkansas.gov` redirects to the `portal.arkansas.gov` home page | | open | **defer**: the home page links one fund, the petroleum storage tank trust fund (tank owners, not local governments); no grants page found |
| Heritage (historic preservation, county courthouse restoration grants) | `www.arkansasheritage.com` | not surveyed further | no robots file | **follow-up**: county courthouse grants name counties; a session of its own if a reader asks |

Three of the four built agencies run one WordPress platform, so Arkansas gets a base: `connectors/arkansas_wordpress.py`
(the third-case rule: three agencies on one platform force it). The page's `h1` on Agriculture's pages is the division
("Natural Resources") and ADEM's pages have none, so the title is the `<title>` tag with its " - site name" cut.

## Candidate programs and scope calls (each one line in a module's `PAGES`)

**Agriculture** (`ar_anrd`, three records)

- **Water and Wastewater Funding**, one record, `loan`. One page covers five funds (CWSRF, DWSRF, the Water Development
  Fund, the Water, Sewer and Solid Waste Fund, the General Obligation Bond Program) with one applicant list, one
  application process and one status line; its `h3` sections are rate tables, not programs, so it is not split. Status from
  the page's own "Application Status" paragraph: "Applications for Arkansas Department of Agriculture funding are currently
  closed." The Project Priority List table ("Noon, November 16, 2026") is a list-ranking deadline in a table, not an
  application deadline, and table cells are not read. `direct`: the page says "state and federal programs" without naming
  the federal funder (the Missouri and Nebraska CWSRF rule).
- **High Hazard Potential Dam Grant**, `pass_through` (FEMA, named). No round: "funding timelines are determined
  annually", so `unknown`. Applicants are a paragraph under "Eligible Applicants" (State, County and Municipal governments,
  special purpose districts, 501(c)(3) nonprofits).
- **Section 319 Nonpoint Source grants**, from the Nonpoint Source Management page, `pass_through` ("federal funding
  through the Environmental Protection Agency"). The annual timeline names months with no year: `unknown`.
- Out: the department's `/resources/grants/` page (specialty crops, farmers, food systems: producers and processors, all
  closed); the Agricultural Water Quality Loan Program (farmers); tax credits.

**Emergency Management** (`ar_adem`, four records)

- **Hazard Mitigation Grant Program** (its own page), `pass_through`.
- The **Hazard Mitigation Grants** page holds three things under `h2`s: the **State of Arkansas Hazard Mitigation Grant
  Program** (state money, 75/25, Notices of Intent "May 26, 2026 through June 15, 2026" for FY2027) and **BRIC**, one record
  each through `SPLITS`; the Shelter Rebate section ("ended in 2016") and its HMGP section (the same program as the HMGP
  page) are tails that belong to no record. The state program keeps the page's own `source_id`.
- **Homeland Security Grant Program**, `pass_through`, `closed` ("not accepting additional applications").
- Out: EMPG (the page is a list of quarterly forms, no program text), NEHRP and EHP (links to FEMA), the Non-Profit
  Security Grant (nonprofits), FY26 SBSRF (two links and "CLOSED", no applicant named), Pre-Disaster Mitigation (FEMA
  replaced PDM with BRIC; the page describes the retired program), the DPS Public Safety Equipment Grant ("will not be
  funded for Fiscal Year 2026"; reopen if it is funded).

**Outdoor Recreation** (`ar_ooo`, three records)

- **Outdoor Recreation Matching Grants**, **FUN Park Grants**, **Trails for Life** (the Great Strides grant): one page
  each, each opening with "Opens: May 1, 2026 Due: August 28, 2026" (Trails: March 9 to June 30, 2026), then a list whose
  first item is "Eligible applicants: ...". All three windows have passed: `unknown`, the window kept. `direct`.
- Not read: the index page (it repeats the three programs' lists), the FAQ page.

**AEDC** (`ar_aedc`, five records)

- **Community Development Block Grant** (ACEDP), one record, `pass_through` (HUD). Applicants from "Who is eligible?";
  deadlines sit in the guidelines PDF, so `unknown`. The page's CAPER notice at the top, the plan and report lists, the
  CDBG-DR history (ADFA runs DR now) and the quarterly report lists are not program text: the CAPER lines are dropped and
  the read stops at "Administrative Procedures Manual".
- **Arkansas Site Development Program**: cities, towns and counties, economic development organizations, chambers of
  commerce; "Applications Close: November 6, 2026, 5pm CT" has passed: `unknown`, the date kept.
- Rural Services: **Rural Community Grant** (towns under 3,000, 50/50 match; "Fiscal Year 2027 Deadlines are: Cycle I -
  August 13, 2026 Cycle II - March 11, 2027"), **Rural Services Block Grant** (towns under 3,000, 51% LMI; deadline October
  16, 2026), **Wildlife Education Grant** (K-12 schools and conservation districts; deadline November 12th, 2026). Their
  pages have no `h1`; names are set in the module.
- Out: the EDA Statewide Planning Grant (a one-time ARPA consultant study, sites not money), Arkansas Rural Connect (the
  2020 broadband program; the State Broadband Office runs broadband now), CDBG-DR (ADFA's).

## Field mapping (the agency-page table in `connectors/hand_list.py`)

| Program field | From |
|---|---|
| `name` | `<title>` with " - Arkansas Department of ..." cut (WordPress), the `h1` (AEDC), or the module's `NAMES` |
| `summary` | the first paragraph that is not a status, deadline or metadata line |
| `status`, `opens_at`, `closes_at`, `closes_at_text` | `round_for`: a deadline still ahead, then closed wording, then a past deadline (`unknown`), then undated open wording |
| `eligibility_text`, `applicant_types` | list items under an eligibility label, applicant sentences anywhere, and (Arkansas base) each sentence of a paragraph under an eligibility heading, the DWEE rule |
| `funding_source` | the module's `FUNDING_SOURCES` where the page names the federal funder in words the shared regex does not know (EPA), else the shared rule |
| `funding_type` | the name's keyword, else `grant`; Water and Wastewater Funding is `loan` |

## Sample of the raw data

Agriculture's Water and Wastewater Funding page (`div.elementor-widget-theme-post-content`):

```
p   The Arkansas Department of Agriculture offers financial assistance through multiple state and federal programs. ...
p   <strong>Eligible Applicants:</strong>
li  Cities, towns, and counties
li  Rural development authorities and improvement districts
...
h3  Application Status
p   Applications for Arkansas Department of Agriculture funding are currently closed.
```

Outdoor Recreation's Matching Grants page (`div.elementor-widget-dyncontel-content`):

```
p   Opens: May 1, 2026 Due: August 28, 2026
li  Eligible applicants: All municipalities and counties in Arkansas
li  Maximum award: No maximum limit* ...
```

AEDC's Site Development page (`.page-content`, Sitefinity):

```
h3  Who can apply?
div   <p>Eligible applicants:</p>
ul    <li>Cities, towns, and counties in Arkansas</li> ...
h3  What sites are eligible for consideration?
div   Greenfield industrial sites
div   Minimum of 30 acres contiguous land
```
