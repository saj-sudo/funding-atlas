# 50-state portal census (milestone 8.2), light depth

Census date 2026-10-18. Every state plus DC, one row each, asking the Pennsylvania question 51 times: does the state run
a public central index of its grant programs, and does that index state a status or at least dates, so that one
connector would bring the state onto the navigator? The Mid-Atlantic rows (MD, DE, PA, VA, DC, WV, NJ) carry over from
`docs/surveys/mid_atlantic.md` with their status codes re-checked; everything else is new.

**Light** means three to five fetches a state: the candidate portal's landing page, one listing page, `robots.txt`.
No agency-by-agency work and no raw samples, except for the one vendor question the roadmap carried (8.1, WebGrants),
where one list page and one opportunity page per state were read. Candidate URLs came from web search; every cell comes
from a fetch with `curl`, user agent `funding-atlas-survey/0.1 (+https://github.com/saj-sudo/funding-atlas)`, through
the session's HTTPS proxy. The status code is the final response after redirects. Hosts that refused this client
(Akamai, CloudFront, Cloudflare challenge, DataDome, Radware captcha, Azure WAF, TLS or connection failures through the
proxy) are recorded as `blocked` with the cause and were not worked around. A `JS shell` is a page whose data is loaded
by script and whose endpoint was not visible in the HTML; it was not reverse-engineered.

## The table

Verdicts: **one connector away** (a public index with a labelled status or with dates); **vendor candidate** (a shared
vendor with a public listing); **agency connectors** (no index; the agencies would be surveyed one by one); **seed list**
(a state-run directory of programs with no status or dates: an enumeration aid, not a record source); **blocked**;
**not found**; **built**.

| State | Central grants portal | Platform / vendor | Public listing | Access | Code | Verdict | Note |
|---|---|---|---|---|---|---|---|
| **MD** | `https://grants.maryland.gov/` → `/Pages/Grants-Office.aspx` | SharePoint on-prem; agencies Drupal 11, SharePoint, WordPress | none (a link list); status lives on agency pages | robots restricts CMS paths; GOCPP disallows all | 200 | built | 7 connectors, milestones 3 to 7 |
| **AL** | `https://adeca.alabama.gov/about/funding-opportunities/` | WordPress (ADECA) | programs, prose: "currently open opportunities only", a grant calendar | `robots.txt` is one rule: `User-agent: ClaudeBot / Disallow: /`; no rule for other agents | 200 | agency connectors | the only robots file in the census that names an AI crawler; a decision for the operator, not the connector |
| **AK** | `https://www.commerce.alaska.gov/web/dcra/` | DataDome | blocked | 403 on every path, `robots.txt` included | 403 | blocked | DCCED runs CDBG and the Community Assistance Program |
| **AZ** | `https://grants.az.gov/` → `https://ospb.az.gov/grants-resources` | Drupal 11; eCivis / Euna Grants Network | login only: "Arizona Funding Opportunities" links to `gn.ecivis.com` (login page) | `robots.txt` redirects to the page; no robots served | 200 | agency connectors | the state pays for Euna Grants Network research access; nothing public |
| **AR** | none found; `https://www.arkansasedc.com/community-resources/division/community-development/grants` | ASP.NET (AEDC); DFA WordPress | programs, prose (CDBG pages) | DFA robots allows, sitemap | 200 | agency connectors | DFA Intergovernmental Services page 404 at the searched URL |
| **CA** | `https://www.grants.ca.gov/` with the open-data export `california-grants-portal-data.csv` on `data.ca.gov` (CKAN) | WordPress site; CKAN dataset, daily CSV | **programs with labelled status**: 2,023 rows; `Status` active 167, closed 1,853, forecasted 3; `OpenDate`, `ApplicationDeadline`, `ApplicantType`, `FundingSource`, `MatchingFunds`, `EstAmounts`, `LastUpdated`, `GrantURL`, 37 columns | robots allows all, Yoast sitemap; CSV via CKAN redirect to object storage | 200 | **one connector away** | the largest and cheapest source in the census: one file |
| **CO** | `https://dlg.colorado.gov/local-community-funding-guide` | CloudFront | blocked | 403 "request could not be satisfied" on every `colorado.gov` path, robots included | 403 | blocked | the Local Community Funding Guide (DOLA) is the index, per search |
| **CT** | `https://portal.ct.gov/opm/igpp/grants` | Sitecore | programs, prose: three IGPP grants (LoCIP, Mashantucket Pequot/Mohegan Fund, Municipal Grants in Aid); `/grants` 404 | robots restricts Sitecore paths | 200 | agency connectors | no statewide index |
| **DE** | none; UD IPA "Master Grant Portal" is Looker Studio | WordPress agencies | agency prose | allows | 200 | agency connectors | carried over |
| **DC** | `https://communityaffairs.dc.gov/topic/grants-and-funding` | Drupal 7 | notices only | `Crawl-delay: 10` | 200 | out of scope | carried over; no municipalities |
| **FL** | `https://dosgrants.com/` (Department of State only); FloridaCommerce `floridajobs.org` | ASP.NET (DOS Grants); Azure WAF on FloridaCommerce | an application system for one department's culture, history, library and elections grants; FloridaCommerce 403 | dosgrants robots served as an HTML page | 200 / 403 | agency connectors; FloridaCommerce blocked | no statewide index |
| **GA** | none found; `https://dca.georgia.gov/` | Drupal 10 | not found: `/funding-opportunities` 404, home carries no grants link, `grants.georgia.gov` does not resolve | standard Drupal robots | 200 | not found | DCA CDBG awards are announced as news |
| **HI** | `https://grants.hawaii.gov/` → `https://federalawards.hawaii.gov/` | WordPress | none: an Office of Federal Awards Management page, no listing; the Legislature's Grant-in-Aid pages answer a Cloudflare challenge | | 200 / 403 | not found | |
| **ID** | `https://commerce.idaho.gov/incentives-and-financing/grants/` | Cloudflare challenge | blocked ("Just a moment"), robots included | | 403 | blocked | Commerce lists CDBG, Gem Grant, RCIF per search |
| **IL** | `https://gata.illinois.gov/grants/csfa.html`, an iframe of `https://omb.illinois.gov/public/gata/csfa/` (Catalog of State Financial Assistance) | state-run ASP.NET catalog; applications in AmpliFund (`GMS` prefix) | **programs with dates**: Funding Opportunities list 123 rows (Opportunity Title, Agency, Application Date Range, Award Range); Program list 1,562 rows; agency list; weekly mailing list | GATA robots standard; `omb.illinois.gov/robots.txt` answers a BIG-IP logout page | 200 | **one connector away** | listed on the opportunities page means open; HTML tables |
| **IN** | `https://www.in.gov/sba/grants/state-agency-grant-opportunities/` | Euna Grants (AmpliFund) | "Click Here for Opportunities listed with Euna Grants Powered by AmpliFund"; the link is not in the static HTML | in.gov robots allows, sitemap | 200 | vendor candidate, unverified | AmpliFund's public opportunities page was not reached |
| **IA** | `https://www.iowagrants.gov/storefrontFOList.do` | **WebGrants** (Dulles Technology) storefront | **programs with labelled status**: 27 opportunities; columns ID, Status (`Posted`), Categorical Area, Agency, Program Area, Title, Posted Date, Pre-Application Due Date, Final-Application Due Date; detail page adds Award Amount Range, Project Dates, Recurring Opportunity, Program Officer, Eligible Applicants (prose) | robots 404 (none) | 200 | **one connector away; WebGrants vendor** | the home page is a login; the storefront is public |
| **KS** | `https://www.kshub.gov/` (Kansas Infrastructure Hub) | Akamai | blocked (403, robots included); Commerce `kansascommerce.gov/program/community-programs/` is WordPress prose | | 403 / 200 | blocked (hub); agency connectors | |
| **KY** | `https://dlg.ky.gov/grants/state/Pages/default.aspx`; `https://www.dlgportal.ky.gov/en-US` (DLG Portal, state grants moved there 2026-09-28) | SharePoint; the portal is a Dynamics-style "EYGA Grants Management Portal" | programs, prose on DLG; the portal has an Opportunities tab (JS shell) | robots restricts SharePoint paths; sitemap | 200 | agency connectors; portal to revisit | `grantreadyky.org` is a curated resource, not a listing |
| **LA** | `https://www.doa.la.gov/doa/ocd/` | custom | prose; LGAP page 404; `larc.la.gov` does not resolve | robots 404 | 200 | not found | OCD is disaster recovery and LGAP |
| **ME** | `https://www.maine.gov/moca/funding` | CloudFront | blocked (403 on every `maine.gov` path) | | 403 | blocked | MOCA's Maine Community Funding Finder is the index, per search |
| **MA** | `https://www.mass.gov/info-details/community-one-stop-for-growth` | Drupal 11; One Stop applications in IntelliGrants (Agate) | programs, prose: 12 programs under one NOFA with round dates in text; the Municipal Grant Finder URLs 404 | standard Drupal robots; SemrushBot blocked | 200 | agency connectors | |
| **MI** | `https://www.michigan.gov/egrams` | Akamai | blocked (403 on every `michigan.gov` path); `egrams-mi.com` is an IIS default page | | 403 | blocked | |
| **MN** | `https://mn.gov/grants/` (landing 200); `https://mn.gov/grants/find/` | state-run (Vivisimo search) | blocked at the listing: the find page answers a Radware Bot Manager captcha | robots allows most | 200 / captcha | blocked (listing) | the one portal that blocks the listing but not the landing page |
| **MS** | `https://mississippi.org/` (MDA) | WordPress | not found: no grants listing at the tried paths | robots allows, sitemap | 200 | not found | the Municipal League publishes a PDF booklet |
| **MO** | `https://ded.mo.gov/cdbg` | Drupal 10 | programs, prose; no portal | standard Drupal robots | 200 | agency connectors | |
| **MT** | `https://funding.mt.gov/index.do` (login and search); agency storefronts `https://mtagr.webgrantscloud.com/storefrontFOList.do` (9) and `https://mtfwp.webgrantscloud.com/storefrontFOList.do` (0 on the day) | **WebGrants**: legacy Tomcat portal plus WebGrants Cloud per agency | **programs with labelled status** on the storefronts, same columns as Iowa | robots 404 (none) | 200 | **WebGrants vendor** | the statewide portal's own list is behind the login; agencies moved to the cloud product |
| **NE** | `https://opportunity.nebraska.gov/programs/` | WordPress; AmpliFund (the AmpliFund page redirects to a Zendesk help center behind a Cloudflare challenge) | programs, prose (DED list) | `Crawl-delay: 3`, query strings disallowed | 200 | agency connectors | |
| **NV** | `https://www.ofa.nv.gov/grant-discovery/`; `https://nevadaepro.com/` | custom; a federal discovery tool (NAVA); state NOFOs in NevadaEPro (Periscope procurement) | a federal grants finder (JS) and a procurement portal; no state program listing | robots served empty | 200 | agency connectors | |
| **NH** | none; `https://nhcdfa.org/` (CDFA) | WordPress | prose (CDBG); `nh.gov` 403 | | 200 / 403 | agency connectors | |
| **NJ** | DCA SAGE public RFP list | IntelliGrants | RFPs with deadlines | | 200 | small build | carried over |
| **NM** | `https://www.nmdfa.state.nm.us/` | | unreachable: 502 and connection reset through the proxy (`robots.txt` alone answered 200) | | 000 | blocked (proxy) | `grants.nm.gov` does not resolve |
| **NY** | `https://grantsmanagement.ny.gov/search-funding-sfs` → the SFS Vendor Portal's Grant Opportunity Portal | PeopleSoft (Statewide Financial System) | public per the state ("a username and password are not necessary"), but the portal is a JS shell; the old Grants Gateway host no longer resolves | robots standard | 200 | deeper look | the one public index whose endpoint needs a session to find |
| **NC** | `https://www.nc.gov/your-government/all-nc-state-services/grant-opportunities` | Drupal, static hosting | **seed list**: 86 rows (Category, Grant Program, Agency, Description); no status, no dates; `ncgrants.gov` does not resolve | robots allows, sitemap | 200 | seed list | the Maryland Grants Office pattern, done as a table |
| **ND** | `https://www.commerce.nd.gov/community-services/community-development-rural-prosperity/cdrp-resources/cdrp-grant-programs` | Drupal | programs, prose (CDRP grants) | standard Drupal robots | 200 | agency connectors | |
| **OH** | `https://grants.ohio.gov/` | static hosting | not found: 404 on the home page, `robots.txt`, and the old portal paths; `obm.ohio.gov` 404 too | | 404 | not found | OBM policy says agencies must post there; the site answered nothing on the day |
| **OK** | `https://ogx.ok.gov/` (Oklahoma Grant Exchange); `https://www.okcommerce.gov/` | | OGX: connection reset through the proxy on two tries; Commerce WordPress CDBG pages, prose | `oklahoma.gov` robots allows | 000 / 200 | blocked (OGX); agency connectors | |
| **OR** | `https://www.oregon.gov/biz/programs/` (Business Oregon) | SharePoint | programs, prose: about 90 programs by category on one page | robots restricts SharePoint paths | 200 | agency connectors | |
| **PA** | `https://www.pa.gov/grants` | Coveo index + JSON per page | labelled status | allows | 200 | built | `pa_grants`, 377 records |
| **RI** | `https://controller.admin.ri.gov/grants-management/grant-management-system-gms/subrecipients/funding-opportunities` | Drupal 11; eCivis / Euna GMS | blocked: Cloudflare challenge on the funding-opportunities page (`robots.txt` 200) | | 403 | blocked | the state's own page says it lists state grant programs with eligibility and deadlines |
| **SC** | `https://www.sccommerce.com/`; `https://ria.sc.gov/` | Drupal; WordPress | not found at the tried paths | standard | 200 | not found | |
| **SD** | `https://sdgoed.com/` | WordPress | programs, prose (CDBG, LIIP); the Municipal League's list answers a Cloudflare challenge | robots allows, sitemap | 200 | agency connectors | |
| **TN** | `https://www.tn.gov/ecd/rural-development.html` | AEM with Coveo (like pa.gov) | programs, prose; no statewide index (a state commission recommended creating one); `tennessee.thegrantportal.com` is a third-party aggregator | robots `User-agent: *` only | 200 | agency connectors | |
| **TX** | `https://egrants.gov.texas.gov/fundingopp` (Office of the Governor only) | custom eGrants | **opportunities with dates**: 8 active on the day (Name, Available, Due Date, Purpose, Eligible Organizations, Total Funds) plus an archive; one office; the statewide `txapps.texas.gov` eGrants search is 404 | robots 404 | 200 | small build | public safety and criminal justice rounds for counties and cities |
| **UT** | Utah Funding Opportunities Portal, `https://lookerstudio.google.com/.../ef90555b-7a4d-4b8e-898e-c427c996bf65` linked from `gopb.utah.gov` | Looker Studio | JS shell | gopb robots `Crawl-delay: 10` | 200 | JS shell | the Delaware pattern, state-run this time |
| **VT** | `https://accd.vermont.gov/community-development/funding-incentives`; `https://egrants.vermont.gov/` | Drupal; eGrants (connection reset, same host address as Oklahoma's OGX) | programs, prose | standard Drupal robots | 200 / 000 | agency connectors; eGrants blocked | |
| **VA** | Governor's grant table | hand-kept HTML | free-text periods | | 200 | defer | carried over |
| **WA** | `https://tre.wa.gov/financing-and-debt/other-programs/washington-fund-directory` (Treasurer); `https://www.commerce.wa.gov/` | Drupal 10; WordPress | **seed list** by topic (Treasurer's Fund Directory); Commerce's "Funding" menu leads to the contracting page | allows; Commerce `Crawl-delay: 10` | 200 | seed list | |
| **WV** | `https://grants.wv.gov/grants/Pages/default.aspx` | SharePoint + state JSON API | dates | none published | 200 | build second | carried over |
| **WI** | `https://wigrants.wi.gov/` | | not found: the host does not resolve (WiGrants is cited in 2006 to 2010 state reports) | DOA robots restricts SharePoint paths | 000 | not found | |
| **WY** | `https://sbd.wyo.gov/grants/grants-connect-hub` | Google Sites (ESF) | JS shell: the Grants Connect Hub embeds a dashboard whose source is not in the static HTML | robots 404 | 200 | JS shell | WYGAP offers free grant help to communities |

## Tallies

| Verdict | States |
|---|---|
| built | MD, PA (2) |
| one connector away | CA, IL, IA (3); WV in progress |
| WebGrants vendor | IA, MT (2) |
| small build or deeper look | NJ, TX, NY (3) |
| seed list | NC, WA (2) |
| agency connectors | AL, AR, AZ, CT, DE, FL, KY, MA, MO, ND, NE, NH, NV, OR, SD, TN, VT, VA (18) |
| JS shell, not read | UT, WY (2) |
| blocked | AK, CO, ID, KS, ME, MI, MN (listing), NM, RI, OK (OGX), plus FL Commerce and VT eGrants on otherwise-readable states (10) |
| not found | GA, HI, LA, MS, OH, SC, WI (7) |
| out of scope | DC (1) |

Vendors with a **public** listing in two or more states: **WebGrants storefront** (Iowa, Montana): same URL shape
(`storefrontFOList.do`, `viewStorefrontOpportunity.do?OIDString=…`), same nine columns, a labelled `Status`. Every
other vendor seen (eCivis / Euna in AZ and RI, AmpliFund in IL, IN and NE, IntelliGrants in NJ, MA and formerly NY,
CGI Advantage in WV, PeopleSoft SFS in NY, custom eGrants in PA and TX) is a login or a JS shell on the public side,
with two single-state exceptions: New Jersey DCA's IntelliGrants RFP page and Texas's Governor's Office eGrants list.

Blocking causes: Akamai (KS hub, MI), CloudFront (CO, ME), Cloudflare challenge (ID, RI, HI Legislature, SD League,
NE's AmpliFund help page), DataDome (AK), Radware captcha (MN listing), Azure WAF (FL Commerce), connection reset or
502 through the proxy (NM, OK OGX, VT eGrants, GA grants host, LA LARC), hostnames that do not resolve (WI, NC
`ncgrants`, NY Grants Gateway, UT `fundingportal`, NM `grants.nm.gov`). Whether a browser from a residential address
sees the same walls is unknown; none was tried.

## WebGrants findings (the 8.1 question)

WebGrants is Dulles Technology's grants system. Its public face is the **storefront**: `storefrontFOList.do` lists
posted opportunities as one table (ID, Status, Categorical Area, Agency, Program Area, Title, Posted Date,
Pre-Application Due Date, Final-Application Due Date), and `viewStorefrontOpportunity.do?OIDString=<id>|Opportunity`
gives the detail: deadlines, `Status Posted`, `Posted Date`, `Award Amount Range`, `Project Dates`, `Award Announcement
Date`, `Categorical Area`, `Recurring Opportunity`, a program officer, and prose sections (Description, Purpose,
Eligible Applicants, Eligibility Requirements, Ineligible Projects, Eligible Expenses). Iowa's storefront had 27
opportunities on the day; Montana's statewide portal keeps its list behind the login (`index.do` offers "Search Here"
to logged-in users, and the legacy `.do` list paths answer 400), but its agencies have moved to WebGrants Cloud hosts
(`mtagr.webgrantscloud.com` 9 opportunities, `mtfwp.webgrantscloud.com` 0) that serve the same storefront.

So **one `webgrants` connector fits both states**: the state is a host (or a list of hosts) and a jurisdiction code, the
parser is one table plus one detail page, and `Status` is a labelled field. What it does not give: a program registry.
A storefront lists rounds that are posted now, so a closed round disappears rather than flipping to closed; the diff
pipeline's `missing` path and `resolve_missing` (re-read the detail; 400 or gone → closed with the last known
deadline? or unknown?) would carry the status, and that rule needs the doc before the parser. Eligibility is prose and
goes through the shared keyword tagger. Two states is the bar the roadmap set for a platform connector; the census did
not look for WebGrants in the other 47 (the vendor pass ran only where a state turned up WebGrants), so a third state
may exist.

## What this changes for milestone 9

After `wv_grants`, in order of records unlocked per session:

1. **`ca_grants`** (California): one CSV from `data.ca.gov`, refreshed by the state; 2,023 rows with a labelled `Status`
   (active 167 on the day), open date, deadline, applicant type, funding source, match, amounts, a `LastUpdated`
   stamp per row and a `GrantURL`. No HTML parsing at all. The doc question is the applicant-type vocabulary
   (`Public Agency`, `Nonprofit`, `Tribal Government`, `Business`, `Individual`) and the free-text `ApplicantTypeNotes`
   that names cities and counties.
2. **`il_csfa`** (Illinois): the CSFA opportunity list (123 rows: title, agency, application date range, award range) and
   program list (1,562 rows) as HTML tables on one host. Listed means open; the date range gives `opens_at` and
   `closes_at`; "No end date" is rolling.
3. **`webgrants`** (Iowa, Montana agencies): the storefront connector above, two states as configuration.
4. **`tx_egrants`** (Texas, Governor's Office): 8 active rounds with dates and eligible organizations; small and public
   safety-heavy; the state's criminal-justice pass-throughs for counties and cities.
5. **New York SFS**: a deeper look to find the Grant Opportunity Portal's data endpoint behind the PeopleSoft shell. The
   state says it is public; the census could not read it without a browser.

Seed lists (NC, WA) and the Governor's table (VA) tell a future agency-connector session which agencies to read first.
The 18 "agency connectors" states and the 7 "not found" states wait for outreach to name a town. The 10 blocked states
are the one thing a cloud container cannot settle: a check from an ordinary browser would say whether the walls are for
bots in general or for this proxy's address range.

## Not found, stated plainly

- A state-run index in GA, HI, LA, MS, OH, SC or WI at the URLs search and guesswork produced. Ohio's portal host
  answers 404 on every path, which may be a migration rather than an absence.
- Any public AmpliFund, eCivis / Euna or SmartSimple listing; Submittable and Fluxx did not appear at all at this depth.
- The data endpoints behind New York's SFS portal, Utah's Looker Studio portal, Wyoming's Grants Connect Hub, Kentucky's
  DLG Portal and Nevada's Grant Discovery tool. Light depth records the shell and stops.
- Whether the WebGrants storefront exists in any state other than Iowa and Montana; it was looked for only where
  WebGrants turned up.
