# Mid-Atlantic portal survey (milestone 8)

Live survey 2026-10-17. Six neighbouring states plus Maryland as the control row. **No code.** The question was: before
writing any parser for a second state, where does each state list its pass-through money, on what platform, and does
the listing carry status and dates or only a login?

Method: every URL below was fetched on the survey date with `curl`, user agent
`funding-atlas-survey/0.1 (+https://github.com/saj-sudo/funding-atlas)`, through the session's HTTPS proxy. The status
code next to each URL is the final response that day after following redirects (a `→` names the landing URL; the first
hop on those is a 301 or 302), re-checked once more at the end of the session. `robots.txt` was read before any program page on every host that
made the table (the GOCPP lesson). Web search was used only to find candidate URLs; every cell comes from a fetch.
Raw fetches were kept in the session scratchpad; the excerpts that matter are in the per-state sections.

Three hosts did not resolve through the proxy at all and are marked as such rather than guessed at: `grants.delaware.gov`,
`www.grants.pa.gov` (the bare `grants.pa.gov` does), `grants.dc.gov`, `egms.dc.gov`.

## The table

"Status field" means a labelled value the page or API states (the DHCD rule), not a date the reader has to compare.

| State | Central grants portal | Platform / vendor | What it lists | robots.txt and sitemap | Top agencies for local governments | Verdict for milestone 9 |
|---|---|---|---|---|---|---|
| **MD** (control) | `https://grants.maryland.gov/` → `/Pages/Grants-Office.aspx` (200). An "About" page and a resource library of outbound links; no listing (`connectors/md_dhcd.md`) | SharePoint on-prem 16 (`MicrosoftSharePointTeamServices: 16.0.0.10417`). Agencies: Drupal 11 (DHCD, Commerce, MHT), SharePoint (MEA, DNR, MDEM, MDOT, MDE), WordPress (GOCPP) | Nothing. Program status lives on agency pages: a labelled box on Drupal, prose on SharePoint | `grants.maryland.gov/robots.txt` (200) disallows only `/_vti_bin/`, `/_layouts/`, `/_catalogs/`. DHCD `sitemap.xml` (200, 633 KB, `lastmod` per URL). GOCPP `robots.txt` (200) disallows everything | DHCD, MEA, DNR, Commerce, MHT (built); GOCPP (blocked) | **Built.** 7 connectors, milestones 3 to 7 |
| **PA** | `https://www.pa.gov/grants` (200), "Discover State Grants", with the search hub at `https://www.pa.gov/grants/search` (200) and one page per grant at `/grants/search/grant-details/<agency>/<n>` (e.g. `pema/10`, 200) | Adobe Experience Manager site (`copapwp` component namespace); the listing is a **Coveo** search index, org `commonwealthofpennsylvaniaproductiono8jd9ckm`, search hub `All Grants`, public search key in the page markup. Application system `https://grants.pa.gov/` → `Login.aspx` (200), "Enterprise eGrants System", ASP.NET, Keystone Login; `esa.dced.state.pa.us` redirects there | **Programs with status and dates.** 377 grants from 17 agencies on the survey date. Facets: Application status (`Accepting applications` 84, `Closed` 293), Applicant type (`Municipality` 132), Funding agency, Funding type, Funding source (State 189, Federal 75), Category, Population served. Index fields include `copapwpopendate`, `copapwpclosedate` (epoch ms, on 100 of 100 sampled), `copapwpgrantcycle`, min/max award. The detail page embeds the whole record as JSON (`openDate`, `closeDate`, `applicantType`, `applicantCategory`, `eligibility`, `matchingFundsRequirements`, `linkToApply`, `pointOfContact`, `processSteps`, `last_modified`) | `www.pa.gov/robots.txt` (200): three unrelated `Disallow` paths, no crawl delay; `Sitemap: https://www.pa.gov/en.sitemap.xml` (200) but the grant-details pages are not in it (26 `/grants/` URLs there are agency pages). DCED's own site `dced.pa.gov/robots.txt` (200) allows all, `Crawl-delay: 0`, `programs-sitemap.xml` (200, 319 URLs with `lastmod`, archived programs included) | Not needed: the portal covers DCED (88), DEP (47), PCCD (67), PennDOT (24), PEMA (21), DCNR (10) and eleven more. DCED's WordPress `dced.pa.gov/programs/` (200, 144 programs, prose pages, no status field) is the fallback | **Build first.** Labelled status, dates, applicant types, eligibility, change signal (`last_modified`), one REST call to enumerate, server-rendered JSON per record. 22 records are open to municipalities today |
| **VA** | None single. `https://www.governor.virginia.gov/constituent-services/grants/` (200), "Grant List", a hand-maintained HTML table: 59 state rows from 18 agencies, columns State Agency / Grant Opportunity / Application Period, each row linking to the agency's page | Custom Apache site. Agencies: Drupal 10 (DHCD `www.dhcd.virginia.gov`, DCJS `www.dcjs.virginia.gov`), custom (DCR). Application systems: DHCD CAMS `dmz1.dhcd.virginia.gov/camsportal/Login.aspx` (login), DCJS OGMS `ogms.dcjs.virginia.gov` (200, meta-refresh to `index.jsp`, login) | **Programs with free-text periods, no status.** Application Period values: `Ongoing` (12), `TBA` (12), `June - October 13` (3), `March 31 deadline` (3), stale `Close: November 3, 2023` (3) and `Close: November 18, 2022`. DHCD program pages (`/cdbg-community-improvement-grants`, 200) are prose ("spring of every year, with a second round conducted in the fall"), no box. DCJS `/grants` (200) is a Drupal view of 59 solicitations with Title / Application Due Date / Date Posted | Governor: `robots.txt` (200) disallows CMS paths only; no sitemap (404). DHCD: standard Drupal `robots.txt` (200); `sitemap.xml` 404. DCJS: standard Drupal robots (200); `sitemap.xml` 404. DEQ: **403 from Akamai** to this user agent (`robots.txt` too). VDEM `vdem.virginia.gov`: TLS verification failed through the proxy, not verified | DHCD (CDBG, Virginia Main Street, IRF, water and sewer), VDEM (hazard mitigation, not verified), DCJS (law-enforcement and local court rounds, solicitation list with due dates) | **Defer.** The Governor's table is a seed list of agency pages, not a record source: the status rule cannot be met from "TBA". DCJS's solicitation view and DHCD's Drupal pages are agency connectors in the Maryland mould when outreach asks |
| **DC** | `https://opgs.dc.gov/` and every path under it (200) redirect to `https://communityaffairs.dc.gov/servedc`; the old District Grants Clearinghouse is now the "Grants and funding" topic listing `https://communityaffairs.dc.gov/topic/grants-and-funding` (200), 924 pages at one notice per page, with RSS at `/taxonomy/term/5531/feed` (200) | Drupal 7 (Mayor's Office of Community Affairs). Agency sites Drupal 10 behind Cloudflare | **Notices, not programs.** Each item is a `publication` node: title, `Date Released`, a PDF. No status, deadline, eligibility or agency field. Audience is nonprofits and providers (Ryan White Part B, AmeriCorps formula, TAP RFAs for the District's own DDOT) | `communityaffairs.dc.gov/robots.txt` (200): `Crawl-delay: 10`, standard Drupal disallows; `sitemap.xml` 404. `opgs.dc.gov/robots.txt` (200): same plus SemrushBot and bytespider blocked. Agency grant pages: `dhcd.dc.gov/service/grants-program` **403 "Access denied"** (Drupal), `dmhhs.dc.gov/page/grants` 403, `doee.dc.gov/grants` 404 | Not applicable: the District has no municipalities or counties; "local government" is the District's own agencies | **Out of scope** for the municipal navigator. The RSS feed is a cheap change-log signal for a later nonprofit-facing view |
| **WV** | `https://grants.wv.gov/` → `/Pages/default.aspx` (200); the listing is "Funding Opportunities" at `https://grants.wv.gov/grants/Pages/default.aspx` (200), with per-grant pages `/grants/Pages/grantdetails.aspx?grantid=<n>` (200) and per-agency pages `agency.aspx?agencyname=<name>` | SharePoint on-prem 16 (`16.0.0.10417`, same release as Maryland's SharePoint agencies). The list is filled client-side from a state-run JSON API: `POST https://apps.wv.gov/SharePoint/api/search` with `siteurl=grants.wv.gov`, `listname=AvailableGrants` (200, 693 KB). Application system wvOASIS Vendor Self Service `prd311.wvoasis.gov/PRDVSS1X1ERP/Advantage4` (200, CGI Advantage single-page app, "View Grant Opportunities") | **Programs with dates; status is derived, not labelled.** 124 items. Fields: `Title`, `Division`, `TypeOfGrant` (Competitive 56, Non-Competitive 49, Formula 9, Pass-through 4, Renewal 3, Entitlement 1), `PostedDate`, `DueDate1`, `Forecasted` (free text, mostly 2022 to 2024 wording), `EntityEligible`, `Details`, `FullDetails`, `HowToApply`, `LinkToApply`, `ReadMoreLinkURL`, two contacts, `Modified`. The page's own filter defines Active as `PostedDate <= today <= DueDate1`. On the survey date: 5 active (all DEP non-competitive), 83 past due, 35 with no due date, 1 posted in the future; 31 mention counties or municipalities in `EntityEligible`, 1 of them active. `Modified` runs 2022-06-07 to 2026-05-18; 14 items touched in 2026 | `grants.wv.gov/robots.txt` **404** and `sitemap.xml` 404 (no restrictions stated). `/grants/_api/web/lists` (200) is anonymously readable; `/_vti_bin/listdata.svc/` 401. `dep.wv.gov/robots.txt` 404 | WV Community Advancement and Development `wvcad.org` (200, Craft CMS, CDBG; `robots.txt` disallows `/craft/` only), DEP `dep.wv.gov` (200, SharePoint), WV Water Development Authority (listed as a division on the portal) | **Build second.** The cleanest raw data in the survey (one POST, JSON, dates, eligibility text, contacts) but thin and stale: most rows are 2022 to 2023 rounds nobody re-posted. Cheap to run daily; the diff pipeline is what makes it worth having |
| **NJ** | None. A statewide "GrantsNJ" portal is a bill (A415, introduced 2026-01-13), not a site. The grants system SAGE has two instances: `https://sage.nj.gov/` → `njsage.intelligrants.com/Login2.aspx` (200, login only; `/Opportunities.aspx` redirects to login) and DCA's `https://dcasage.intelligrants.com/Portal.asp` (200) whose "View available grant opportunities" link is a **public** list, `https://dcasage.intelligrants.com/RFPMailingRequest_List.asp` (200, "no registration is required") | **IntelliGrants** (Agate Software), classic ASP ("Copyright 2000-2005 Agate Software"). nj.gov agency pages are static `.shtml`. NJDOT Local Hub `njdotlocalhub.nj.gov` WordPress | **DCA: RFPs with deadlines and eligible applicants, no explicit status** (listed = open). 8 RFPs on the survey date, all Division of Housing and Community Resources, labelled fields: Grant Period Start/Stop, Deadline for Submission, Eligible Applicant, Dollar Range for Award Min/Max, Estimate of Total Funds, Population to be Targeted, Allowable Costs, Purpose, contact. AHTF 2027: deadline 11/19/2026, "Municipalities, for-profit and non-profit affordable housing developers". DLGS (`www.nj.gov/dca/dlgs/programs/`, 200) is prose with a sidebar of local-government grants (LEAP, FY 2023 LRIG, SREP, ARPFFG, LGAP) | `www.nj.gov/robots.txt` (200) allows `/dca`; no sitemap. `dcasage.intelligrants.com/robots.txt` 404. **`dep.nj.gov` serves an Incapsula bot challenge** (212-byte shell, `noindex,nofollow`) to this user agent, `robots.txt` 404: blocked for automated reads. `njdotlocalhub.nj.gov/robots.txt` (200) allows all, Yoast sitemap. `njeda.gov/robots.txt` (200) `Crawl-delay: 10` | DCA (SAGE RFP list, DLGS), DEP (Green Acres and the grant and loan programs, blocked), NJDOT Local Aid (`njdotlocalhub.nj.gov`, program pages by prose) | **Defer, small build when asked.** The DCA RFP page is 8 structured records and one GET; worth a connector the day New Jersey outreach starts. Watch for a second state exposing IntelliGrants' `RFPMailingRequest_List.asp`: that would make it a platform connector |
| **DE** | None. `grants.delaware.gov` does not resolve. The de-facto portal is the University of Delaware IPA "Master Grant Portal", a Google Looker Studio report (`lookerstudio.google.com/reporting/0b3196e2-...`, 200, JavaScript only, not state-run, not fetchable). Statewide announcements: `news.delaware.gov` (200, WordPress, RSS per agency category, e.g. `/category/dnrec/feed/`, 300 items) | WordPress (DNREC 7.1.2 with Yoast sitemaps, DSHA `destatehousing.com`, `news.delaware.gov`), custom (DelDOT, DEMA, OMB) | **Agency prose.** DNREC's Environmental Finance section (`/environmental-finance/`, 200) names the local-government grants and loans (Community Water Quality Improvement, Surface Water Matching Planning, Wastewater Matching Planning, Asset Management Incentive, Project Planning Advances; four loan programs). Program pages carry cycle sentences: ORPT (`/parks/planning/recreation-parks-trails/`, 200) "The 2026 grant cycle is now closed to new pre-applications ... received by Sept. 15, 2026"; CWQI (200) "Submission deadline: Oct. 30" with no year. DEMA `/about/grants/` (200) lists BRIC, HMGP, FMA, EMPG, HSGP, cybersecurity as links. DelDOT `/Programs/tap/` (200) is prose | `dnrec.delaware.gov/robots.txt` (200) allows all, `sitemap_index.xml` (200). `destatehousing.com/robots.txt` (200) allows all, sitemap. `news.delaware.gov/robots.txt` (200) disallows `/wp-admin` only. `delaware.gov/robots.txt` (200) disallows `/contact /admin /pages /sso /courtsearch`. `deldot.gov/robots.txt` (200) disallows several `/information/*` paths, not `/Programs`. `dema.delaware.gov/robots.txt` 404 | DNREC (Environmental Finance, Parks), DEMA, DelDOT (TAP); DSHA's "Local Municipalities" page (200) is zoning technical assistance, not grants | **Defer.** About ten municipal programs across three small WordPress or custom sites, all prose; a DNREC WordPress connector when a Delaware town asks. The Looker Studio portal would need a headless browser: not without asking |

## Platform connectors to build, ranked

The roadmap asked for one connector per platform found in two or more states. **No commercial grants-management vendor
from the watch list (WebGrants, AmpliFund, eCivis / Euna, SmartSimple, Submittable, Fluxx) has a public listing in any
of the six states.** Where a vendor appears at all (IntelliGrants in NJ, CGI Advantage in WV, the Commonwealth's own
eGrants in PA, CAMS and OGMS in VA) its public face is a login page. What repeats across states is the CMS under the
agency sites, and what has structure is state-run central indexes. Ranked by records unlocked, then by whether status
is a labelled field:

| # | Connector | States | What the source exposes | Parseable without a browser | Records on the survey date |
|---|---|---|---|---|---|
| 1 | **`pa_grants`: pa.gov Coveo grants index + grant-details JSON** | PA | Labelled `Application status`, open and close dates, applicant type and category, agency, funding type and source, category, grant cycle, min and max award, eligibility, match requirement, link to apply, contact, `last_modified` | Yes. `POST https://platform.cloud.coveo.com/rest/search/v2` with the page's public key and `searchHub: "All Grants"` enumerates everything (377 results, 100 per page); each detail page is server-rendered with the record as JSON in a data attribute | 377 (84 accepting applications, 22 of them open to municipalities) |
| 2 | **`wv_grants`: grants.wv.gov `AvailableGrants` via `apps.wv.gov/SharePoint/api/search`** | WV | Title, agency, grant type, posted and due dates, forecast text, eligibility text, details, how to apply, links, contacts, `Modified` | Yes. One POST returns the whole list as JSON; no HTML parsing | 124 (5 active, 31 naming local governments, 1 both) |
| 3 | **`nj_dca_sage`: IntelliGrants public RFP list** | NJ (DCA only today) | Deadline for submission, grant period, eligible applicant text, award range, purpose, population, contact | Yes, classic ASP table markup; listed means open | 8 (1 municipal) |
| 4 | **Agency connectors on existing bases** | VA (DHCD Drupal 10, DCJS Drupal 10 solicitation view), DE (DNREC WordPress), NJ (DLGS static pages) | Prose with cycle sentences; DCJS has due dates in a table | Yes, but every page is a new parsing problem and status comes from sentences (the MEA and DNR situation) | tens per agency |
| 5 | **Notice feeds as change signals** | DC (MOCA RSS), DE (`news.delaware.gov` RSS), VA Governor's table | Titles and release dates; no program records | Yes | not records |

The Drupal count is worth stating plainly: MD DHCD, Commerce and MHT (11), VA DHCD and DCJS (10), DC agencies (10) and
MOCA (7) are all Drupal, but on different themes with different markup. `maryland_drupal.py` is a theme parser, not a
CMS parser, and will not transfer. SharePoint is the same story: WV's portal and DEP run the same SharePoint release as
MEA and DNR, but the portal's data comes from a JSON API, not from page text, so `maryland_sharepoint.py` does not apply
either. New bases are extracted when the second site forces them, as before.

## What this changes for milestone 9

Milestone 9 starts with **`pa_grants`**, one state and one connector. It is the only source in the survey that meets the
registry's status rule from a labelled field, and it unlocks more records than the seven Maryland connectors together.
**`wv_grants`** is second: a small, cheap connector whose value is the diff over time rather than the list on day one.
The "platform in two or more states" rule is not met by any vendor; the roadmap should say so and let the state-run
central index be the platform. VA, NJ and DE wait for outreach to name a town; DC is out of the municipal scope.

## Per-state notes and raw samples

### Pennsylvania

URLs fetched: `https://www.pa.gov/grants` 200; `https://www.pa.gov/grants/search` 200; `https://www.pa.gov/grants/search/grant-details/pema/10` 200;
`https://grants.pa.gov/` → `/Login.aspx` 200; `https://www.esa.dced.state.pa.us/` → `grants.pa.gov/Login.aspx` 200; `https://www.grants.pa.gov/` did not resolve;
`https://www.pa.gov/robots.txt` 200; `https://www.pa.gov/en.sitemap.xml` 200; `https://dced.pa.gov/programs/` → `/program/` 200; `https://dced.pa.gov/programs/act-47/` 200;
`https://dced.pa.gov/robots.txt` 200; `https://dced.pa.gov/programs-sitemap.xml` 200; `https://www.pa.gov/agencies/pda/grants/state-programs/dirt-gravel-and-low-volume-road` 200.

Search hub markup (`/grants/search`), the facets the connector would read:

```html
<atomic-facet label="Application status" field="copapwpapplicationstatus" ...>
<atomic-facet label="Applicant type" field="copapwpapplicanttype" ...>
<atomic-facet label="Funding type" field="copapwpfundingtype" ...>
<atomic-facet label="Funding agency" field="copapwpfundingagency" ...>
<atomic-facet label="Funding source" field="copapwpfundingsource" ...>
<atomic-sort-expression label="Deadline" expression="copapwpclosedate ascending" ...>
organizationId: 'commonwealthofpennsylvaniaproductiono8jd9ckm'
```

One Coveo result, `raw` fields (query `{"q":"","searchHub":"All Grants"}`, 377 results):

```json
{"copapwppagetitle": "Hazard Mitigation Grant Program (HMGP)",
 "copapwpapplicationstatus": "Closed",
 "copapwpapplicanttype": ["Municipality", " Public Agency"],
 "copapwpfundingagency": ["Emergency Management Agency"],
 "copapwpfundingtype": ["Grant"], "copapwpfundingsource": "Federal",
 "copapwpcategory": ["Community & economic development"],
 "copapwpurl": "https://www.pa.gov/en/grants/search/grant-details/pema/10"}
```

Facet counts on the survey date: status `Accepting applications` 84, `Closed` 293; agencies DCED 88, PCCD 67, DEP 47,
L&I 33, PennDOT 24, DDAP 22, PEMA 21, DHS 19, PDA 16, DOH 16, tax credits 16, loans 22; applicant type `Municipality`
132, `Public Agency` 81, `Nonprofit` 124, `School` 90, `Business` 98, `Individual` 28, plus a tail of free-text values
(`Local government` 3, `municipalities, including counties or district attorneys' offices` 1). Field presence over 100
results: `copapwpopendate`, `copapwpclosedate`, `copapwpapplicationstatus`, `copapwpminimumaward`, `copapwpmaximumaward`
100 of 100; `copapwpapplicanttype` 71; `copapwpmatchingrequirements` 27; `copapwpdecisiondate` 6.

The detail page carries the record server-side in a data attribute (HTML-escaped JSON), then fills `${closeDate}` and
friends with JavaScript. The connector reads the attribute, not the rendered text:

```json
{"slug":"pema10","last_modified":"2026-10-16T17:01:29Z","title":"Hazard Mitigation Grant Program (HMGP)",
 "status":"Closed","category":"Community & economic development","issuingAgency":"Emergency Management Agency",
 "shortIssuingAgency":"pema","openDate":"2022-01-01T12:00:00-00:00","closeDate":"2022-03-25T12:00:00-00:00",
 "grantCycle":"Upon Disaster Declaration",
 "applicantType":"Cities; Townships; Counties; Special district governments; State agencies. ",
 "applicantCategory":"Municipality; Public Agency",
 "eligibility":"https://www.fema.gov/grants/mitigation/hazard-mitigation/before-you-apply",
 "fundingType":"Grant","matchingFundsRequirements":"75% federal share\n25% local share",
 "totalFundsToBeAwarded":"Pending","fundingSource":"Federal",
 "linkToApply":"https://www.esa.dced.state.pa.us/Login.aspx","issuingAgencyGrantNumber":10.0,
 "pointOfContact":{"name":"Richard Deal\nState Hazard Mitigation Officer\n..."},
 "processSteps":[{"stepNumber":1.0,"description":"Project must be cost-effective"}]}
```

Open to municipalities on the survey date (22), the first by close date: Coastal Zone Management (DEP, closes
2026-10-19), Multimodal Transportation Fund (PennDOT, 2026-10-30), AML/AMD Grant (DEP, 2026-11-30), VIP and BCJI (PCCD,
2026-12-10), 904 Recycling Performance Grant (DEP, 2026-12-31), then continuous and placeholder-dated rows (Act 47 and
Municipal Assistance Program close "2035-12-31", Main Street Matters "2035-08-31"). Those far-future dates are how the
portal encodes "no deadline"; a connector should treat a close date more than, say, five years out as rolling, and
record the decision. Not everything is a grant: `copapwpfundingtype` has `Tax credit` (16), `Loan` (22),
`Reimbursement`, `tax refund`.

Things to settle in the connector doc (`docs/connectors/pa_grants.md`, next session): whether the Coveo key is stable
(it is a public search token in page markup, so it rotates when the site rebuilds; read it from `/grants/search` at run
time rather than hard-coding it); `source_id` = `<shortIssuingAgency>/<issuingAgencyGrantNumber>`; applicant tags from
`applicantCategory` with `applicantType` free text kept verbatim; ALN is not on the record (`fundingSource: Federal`
only).

DCED's own WordPress site is the fallback, not the plan: `dced.pa.gov/programs/` lists 144 programs as
`<div class="programs_wrapper">` entries filtered by type and category, each a prose page (Act 47 sample: no status or
deadline markup anywhere on the page). Its Yoast sitemap carries `lastmod` and includes archived programs
(`...-archived/`). If a DCED program is missing from the portal, this is where to look.

### Virginia

URLs fetched: `https://www.governor.virginia.gov/constituent-services/grants/` 200; `/robots.txt` 200; `/sitemap.xml` 404;
`https://www.dhcd.virginia.gov/` 200; `/cdbg` 200; `/cdbg-community-improvement-grants` 200; `/communities` 200; `/grants` 404; `/programs` 404; `/robots.txt` 200; `/sitemap.xml` 404;
`https://dmz1.dhcd.virginia.gov/camsportal/Login.aspx` (linked, login); `https://www.dcjs.virginia.gov/grants` 200; `/robots.txt` 200; `/sitemap.xml` 404;
`https://ogms.dcjs.virginia.gov/` 200 (meta refresh to `index.jsp`); `https://www.dcr.virginia.gov/` 200; `/robots.txt` 200 (sitemap declared);
`https://www.deq.virginia.gov/robots.txt` 403 (Akamai "Access Denied"); `https://vdem.virginia.gov/robots.txt` TLS failure through the proxy; `https://dmme.virginia.gov/` connection reset; `https://www.virginia.gov/services/grants/` 404.

Governor's table, first rows (59 rows, 18 agencies; links go to agency pages):

```html
<table class="grants" ...><thead><tr><th>State Agency</th><th>Grant Opportunity</th><th>Application Period</th></tr></thead>
<tr><td>Alcoholic Beverage Control Authority</td><td><a href="https://www.abc.virginia.gov/education/grants">Alcohol Education and Prevention</a></td><td>March - January</td></tr>
<tr><td>Department of Agriculture and Consumer Services</td><td><a href="...afid-facility-grants.shtml">AFID - Facilities Grants</a></td><td>Ongoing</td></tr>
<tr><td>Department of Emergency Management</td><td>Hazard Mitigation Grant Program</td><td>June - October 13</td></tr>
<tr><td>Department of Transportation</td><td>Smart Scale</td><td>April - August (even years only)</td></tr>
```

Application Period values: `Ongoing` 12, `TBA` 12, three stale `Close: November 3, 2023`, one `Close: November 18,
2022`, one typo `TBAsecur`. The page also has a City and County Grants section, a dropdown of local grant contacts,
and two tables of private foundations. It is a maintained directory, not a status source.

DHCD (`/cdbg-community-improvement-grants`): "Non-entitlement units of local government are the only eligible
recipients ... The timeline for submission of competitive grant applications to DHCD is the spring of every year, with a
second round conducted in the fall if funding remains." No dates, no box. `/communities` links about 25 program pages
(`/downtown-revitalization`, `/water-sewer-and-drainage`, `/flood-mitigation`, `/cdbg-regionalism`, ...).

DCJS `/grants` is the one structured thing in Virginia: a Drupal view, 59 rows, `Title | Application Due Date | Date
Posted`, e.g. `CY 2027-2029 Virginia Opioid Use Reduction ... Grant Program | 10/13/2026 - 12:00 | 11 September,
2026`. Law enforcement and courts; the GOCPP gap's Virginia cousin, and open to a connector.

### District of Columbia

URLs fetched: `https://opgs.dc.gov/` 200 → `communityaffairs.dc.gov/servedc`; `https://opgs.dc.gov/page/district-grants-clearinghouse`, `/service/district-grants-clearinghouse`, `/sitemap.xml` all → `/servedc` 200;
`https://opgs.dc.gov/robots.txt` 200; `https://communityaffairs.dc.gov/topic/grants-and-funding` 200 (`?page=1` 200, last page `?page=923`); `/taxonomy/term/5531/feed` 200;
`/publication/2026-2027-americorps-formula-grants` 200; `/content/community-grant-program` 200; `/robots.txt` 200; `/sitemap.xml` 404; `/page/district-grants-clearinghouse` 404;
`https://dhcd.dc.gov/` 200; `/service/funding-opportunities` → `/service/grants-program` 403; `/page/dhcd-funding-opportunities` 404; `https://dmhhs.dc.gov/page/grants` 403; `https://doee.dc.gov/grants` 404; `https://grants.dc.gov/` and `https://egms.dc.gov/` did not resolve.

One listing item (Drupal 7 teaser, the whole of what a notice carries):

```html
<article about="/publication/fy27-high-need-healthcare-career-scholarship-program-rfa" class="node node-publication node-teaser ...">
  <h2 class="node-title"><a href="/publication/fy27-high-need-healthcare-career-scholarship-program-rfa">FY27 High-Need Healthcare Career Scholarship Program RFA</a></h2>
  <div class="field field-name-field-date"><div class="field-label">Date Released:</div>
    <span class="date-display-single" content="2026-10-09T00:00:00-04:00">Fri, 10/09/2026</span></div>
</article>
<a href="/taxonomy/term/5531/feed" class="feed-icon" title="Subscribe to RSS - Grants and funding">
```

RSS titles on the survey date: FY27 High-Need Healthcare Career Scholarship Program RFA (2026-10-09), Ryan White Part
B: Status Neutral Care Continuum (10-06), PrEP Housing Program (10-02), FY27 National School Lunch Program Equipment
Assistance Grant (10-01), Columbia Heights & Mount Pleasant Public Realm Improvement Grant (10-01), FY27-FY28
Transportation Alternatives Program (09-29). A publication page is a title, a date and a PDF ("2026-2027 ServeDC
AmeriCorps Formula NOGO FINAL.pdf"). Agency Drupal 10 sites answer `Access denied` on their grants pages to anonymous
requests; that is a Drupal node-access response, not a bot block, and it was not worked around.

### West Virginia

URLs fetched: `https://grants.wv.gov/Pages/default.aspx` 200; `https://grants.wv.gov/grants` → `/grants/Pages/default.aspx` 200; `/grants/Pages/grantdetails.aspx?grantid=1` 200 (empty shell, filled client-side);
`/grants/Pages/agency.aspx?agencyname=Homeland%20Security` 200; `/funding-sources-2/Pages/default.aspx` 200; `/resources/Pages/Grant-Resources.aspx` 200; `/robots.txt` 404; `/sitemap.xml` 404;
`/grants/_api/web/lists` 200 (Atom, anonymous); `/grants/_vti_bin/listdata.svc/` 401; `https://apps.wv.gov/SharePoint/api/Scripts/QuerySearch.js` 200; `POST https://apps.wv.gov/SharePoint/api/search` 200 (JSON, 693 KB);
`https://prd311.wvoasis.gov/PRDVSS1X1ERP/Advantage4` 200; `https://wvcad.org/` 200; `/robots.txt` 200; `https://dep.wv.gov/` → `/Pages/default.aspx` 200; `/robots.txt` 404; `https://wvdep.gov/` did not resolve; `https://swmb.wv.gov/...Grants.aspx` 404 (site is Drupal 11 now).

How the list is fetched (inline script on `/grants/Pages/default.aspx` plus `QuerySearch.js`):

```js
const searchConfig = { "Site": "grants.wv.gov", "ListName": "AvailableGrants", "MaxItems": 1000, "Params": [
  { "Name": "Title", "Method": "substringof", ... },
  { "Name": "DueDate1", "Method": "ge", "DataType": "datetime", "Source": "ActiveDueDate",
    "GroupParams": [{ "Name": "PostedDate", "Method": "le", "DataType": "datetime", ... }] },   // "Active"
  { "Name": "Forecasted", "Method": "ne", "DataType": "literal", ... } ] };                      // "Forecasted"
$.ajax({ type: "POST", url: "https://apps.wv.gov/SharePoint/api/search",
         data: { siteurl: searchConfig.Site, listname: searchConfig.ListName, query: query, maxItems: 1000 } });
// row template:
<a href="https://grants.wv.gov/grants/Pages/grantdetails.aspx?grantid=${item.Id}">${item.Title}</a> ${item.Division} ${item.TypeOfGrant} ${item.PostedDate} ${item.DueDate1} ${item.Forecasted}
```

One item from the JSON (`properties[]`, 124 items):

```json
{"Id":"76","Title":"Chesapeake Bay Implementation Grant (CB)",
 "PostedDate":"2027-01-01T05:00:00Z","DueDate1":"2027-06-01T04:00:00Z",
 "Details":"Grant to provide program funds to help states manage their regulatory, assessment, compliance and enforcement efforts in the Chesapeake Bay region.",
 "FullDetails":"<div class=\"ExternalClass...\">Project funds are available to implement projects that reduce nitrogen, phosphorous and sediment pollution in the area.</div>",
 "EntityEligible":"State governments in the Chesapeake Bay watershed can apply. ...",
 "TypeOfGrant":"Non-Competitive","Forecasted":"Ongoing",
 "Division":"Department of Environmental Protection Division of Water and Waste Management/Office of Water Resources",
 "ReadMoreLinkURL":"https://dep.wv.gov/wwe/watershed/wqmonitoring/pages/chesapeakebay.aspx",
 "HowToApply":"","LinkToApply":"","ContactName1":"","ContactEmail1":"","Modified":"...","Created":"..."}
```

Divisions: DHHR Bureau for Family Assistance 24, Homeland Security 22, Arts Office 13, Economic Development /
Community Advancement 11, Behavioral Health 10 + 5, DEP 5 + 5, Rehabilitation Services 4, Broadband 4, Solid Waste
Management Board 3, Workforce WV 2. `Forecasted` values: empty 88, `May 2023` 7, `Annual deadline of April 1st` 5,
`Spring 2023` 3, `Summer 2023` 3, `Ongoing` 2, `rolling deadline` 1, `No further solicitations for applications
expected due to grant timelines.` 1. Active on the survey date, all DEP: In Lieu Fee Program (to 2026-12-15),
Abandoned Mine Land Reclamation (to 2027-06-30), Chesapeake Bay Regulatory/Accountability (to 2027-06-01), CWSRF
Assistance (to 2026-12-31), Brownfield Revolving Loan Funds (to 2027-03-30).

Status rule for the connector: `PostedDate <= today <= DueDate1` → open (the page's own definition); `DueDate1` behind
→ closed with `closes_at` kept; `PostedDate` ahead → forecasted; no `DueDate1` → unknown, `Forecasted` text to
`closes_at_text`. The rows the municipal page wants (CDBG, Community Advancement rounds, Homeland Security's local
rounds) are in the list but past due; the diff will show when they are re-posted. The `Modified` field is the change
signal, so the hash can be over the item minus `Modified`, with `Modified` stored.

### New Jersey

URLs fetched: `https://www.nj.gov/dca/` 200; `/dca/dlgs/` 200; `/dca/dlgs/programs/` 200; `/dca/dlgs/programs/LOSAP.shtml` 200; `/dca/dlgs/resources/` 200; `/dca/home/grants.shtml` 200; `/dca/dhcr/grants/index.shtml` 200;
`/dca/grants/` 404; `/dca/dlgs/programs/grants.shtml` 404; `https://www.nj.gov/robots.txt` 200; `https://sage.nj.gov/` → `njsage.intelligrants.com/Login2.aspx?APPTHEME=NJSAGE` 200; `njsage.intelligrants.com/Opportunities.aspx` → login; `/Portal.asp`, `/RFPMailingRequest_List.asp` 404 on the statewide instance;
`https://dcasage.intelligrants.com/Portal.asp` 200; `/RFPMailingRequest_List.asp` 200; `/robots.txt` 404; `https://dep.nj.gov/grantandloanprograms/` 200 (Incapsula shell); `/greenacres/` 200 (same); `https://dep.nj.gov/robots.txt` 404;
`https://www.nj.gov/transportation/business/localaid/` 200 (585-byte redirect page); `https://www.njdotlocalaidrc.com/` → `https://njdotlocalhub.nj.gov/` 200; `/robots.txt` 200; `https://www.njeda.gov/robots.txt` 200; `https://www.njstart.gov/` → `/bso/` 200 (procurement, not grants).

DCA SAGE public RFP page (text as rendered; the markup is nested classic-ASP tables, `class="TableCellNeutral"`):

```
Request more information about available RFPs
Instructions: Use this page to find grant opportunities online. Please note that no registration is required.
Available RFPs
Division of Housing and Community Resources
  Affordable Housing Trust Fund 2027
    Grant Period Start: 7/1/2026        Grant Period Stop: 6/30/2027
    Deadline for Submission: 11/19/2026  Deadline for Initiation: 11/19/2026
    Population to be Targeted: Households that are low and moderate income as defined by the Council on Affordable Housing
    Dollar Range for Award Minimum: $50,000.00   Maximum: $3,000,000.00   Estimate of Total Amount of Funds to be Awarded: $30,000,000.00
    Eligible Applicant: Municipalities, for-profit and non-profit affordable housing developers
    Purpose of Grant: ... THIS IS A LOAN PROGRAM.
    Contact Information: Colleen Velez (609) 300-2963 Colleen.Velez@dca.nj.gov
  HOME Community Housing Development Organizations 2027 ... Deadline for Submission: 6/30/2027
  National Housing Trust Fund 2027 ... Neighborhood Revitalization Tax Credit Planning 24 (12/31/2026) ...
  New Jersey Healthy Homes Initiative 2027 ... NJHOMES LAUNCHPAD PREDEVELOPMENT FUND 2026 / 2027 ...
  Volunteer Emergency Service Organization Loan 2027 (Eligible: Fully and partially volunteer fire companies, first aid squads and rescue squads)
```

Eight RFPs, six with the fiscal-year-end `6/30/2027` deadline (rolling in practice). The DLGS local-government grants
(LEAP, Local Recreation Improvement Grant, SREP, ARPFFG, LGAP) are not on this list on the survey date; their pages
under `/dca/dlgs/programs/` are prose and the sidebar still says "FY 2023". NJDOT's Local Hub lists Local Aid programs
(Transportation Alternatives, Safe Routes to School, Local Safety, Local Concept Development, Rail Freight Assistance)
as WordPress pages with a Yoast sitemap. DEP is the gap: `dep.nj.gov` answers automated requests with an Incapsula
challenge and no `robots.txt`, so Green Acres and the grant and loan programs page were not read; per CLAUDE.md, say
so and stop.

### Delaware

URLs fetched: `https://grants.delaware.gov/` did not resolve; `https://www.udel.edu/.../ipa/public-service/gap/` 200 (Grant Assistance Program, links the portal); `https://lookerstudio.google.com/reporting/0b3196e2-eed8-4999-a75a-769132b034f9` 200 ("Master Grant Portal", script shell);
`https://dnrec.delaware.gov/` 200; `/robots.txt` 200; `/sitemap_index.xml` 200 (post, page, public-notices sitemaps); `/grants/` → `/water/resource-protection/grants/` 200 (a division's own federal awards, not a listing); `/environmental-finance/` 200; `/environmental-finance/community-water-quality-improvement/` 200; `/environmental-finance/surface-water-matching-planning/` 404 (linked under another slug); `/parks/planning/recreation-parks-trails/` 200;
`https://www.destatehousing.com/` 200; `/robots.txt` 200; `/local-municipalities/` 200; `https://dema.delaware.gov/about/grants/` 200 (first attempt connection reset, second 200); `/robots.txt` 404; `https://deldot.gov/Programs/tap/` 200; `/robots.txt` 200;
`https://omb.delaware.gov/` 200 (no grants links); `https://stateplanning.delaware.gov/` 200; `https://news.delaware.gov/robots.txt` 200; `/category/dnrec/feed/` 200 (300 items); `https://news.delaware.gov/2026/03/09/dnrec-now-soliciting-community-water-quality-improvement-grant-project-proposals/` 200; `https://www.delaware.gov/robots.txt` 200; `/topics/grants` 404.

DNREC Environmental Finance, the closest thing to a Delaware local-government grants index (rendered text):

```
Assistance For Local Governments
Grants: Community Water Quality Improvement Grants | Surface Water Matching Planning Grants |
        Wastewater Matching Planning Grants | Asset Management Incentive Program | Project Planning Advances
Loans:  Publicly Owned Wastewater Treatment Project Loans | Water Quality Improvement Loan Program |
        Stormwater Infrastructure Loans | Land Conservation Loan Program
```

Cycle sentences, the only status the pages state: ORPT, "The 2026 grant cycle is now closed to new pre-applications.
Pre-applications have been reviewed and invitations to submit full applications have been sent to eligible Sponsors.
Applications ... received by Sept. 15, 2026, will be reviewed"; CWQI, "Nonprofit organizations, conservation districts,
community organizations and homeowners' associations can submit proposals ... Submission deadline: Oct. 30." (no
year). DEMA's grants page lists six FEMA pass-throughs by name with no dates. The UD IPA portal advertises "funding
program title, eligible project category, project amount, grant match or loan interest" per row, but it is a Looker
Studio dashboard: JavaScript only, Google-hosted, and not the state's. Not fetched beyond its shell, not worked around.

### Maryland (control)

Re-verified on the survey date: `https://grants.maryland.gov/` → `/Pages/Grants-Office.aspx` 200; `/robots.txt` 200;
`https://dhcd.maryland.gov/sitemap.xml` 200 (`last-modified` 2026-10-16); `https://gocpp.maryland.gov/robots.txt` 200
(still `User-agent: * / Disallow: /`). Nothing changed since `md_dhcd.md` and `md_gocpp.md`.

## Not found, stated plainly

- A Mid-Atlantic state on WebGrants, AmpliFund, eCivis / Euna, SmartSimple, Submittable or Fluxx with a public listing.
- A sitemap for `grants.wv.gov`, `governor.virginia.gov`, `dhcd.virginia.gov`, `dcjs.virginia.gov`, `communityaffairs.dc.gov`, or the pa.gov grant-details pages.
- A DLGS (New Jersey) grants page with current dates; the sidebar is FY 2023.
- Any Delaware state-run listing; the UD portal is the only index and is not readable.
- Virginia DEQ and VDEM, New Jersey DEP: not readable by this client (Akamai 403, TLS through the proxy, Incapsula). Recorded, not circumvented.
