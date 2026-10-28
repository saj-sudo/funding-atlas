# funding-atlas: roadmap and decisions

What is done, what is next, and why. One session per item. The spec is in `SPEC.md`; operating rules in `CLAUDE.md`.

## Done

| # | Milestone | Shipped | What | Doc |
|---|---|---|---|---|
| 1 | Grants.gov connector, schema, diff output | 2026-10-15 | `search2` + `fetchOpportunity`, eligibility codes 01/02/99, 957 notices on the first full run; hash-compare upsert, missing-record resolution, markdown diff | `connectors/grants_gov.py` docstring |
| 2 | SAM Assistance Listings, ALN link | 2026-10-15 | catalog connector (~2,900 listings, 15 to 30 min cold), `v_opportunity_listing`, `v_aln_coverage`, `cli.py aln` | migration 0003 |
| 3 | First Maryland agency | 2026-10-15 | DHCD, 33 records, chosen over GGO, MDOT, DNR, MEA after a live survey | `connectors/md_dhcd.md` |
| 4 | Second and third Maryland agencies, shared base | 2026-10-15 | Commerce (34) and MHT (11) on `MarylandDrupalConnector`; line-level applicant scan | `connectors/maryland_drupal.md`, `md_commerce.md`, `md_mht.md` |
| 5 | Static page | 2026-10-15 | `v_municipal_page`, `scripts/export_html.py`, `cli.py export`; 133 rows (83 likely, 50 possible), 696 unlikely excluded | this file, decisions log |
| 7.1 | Between rounds | 2026-10-16 | migration 0006: `v_navigator_between` (state programs for local governments that are closed or past their stated deadline, within 15 months of it) and `n_between_rounds` on the coverage view; a third, collapsed group on every state page with the last deadline, the source's cycle wording and an observed reopening date once the change log has one; the count on the index tile and the coverage line. Maryland shows 14 today (CDBG, Technical Assistance Grant, Circuit Rider, L-GEM, CPP, MHT's annual grants) | migration 0006 header, this file |
| 7 | Maryland depth | 2026-10-16 | `md_mea` (28 records) and `md_dnr` (20) on a new `MarylandSharePointConnector` base (`connectors/maryland_sharepoint.py`); shared applicant table gains `municipal`; GOCPP surveyed and stopped on its robots.txt; MDEM, MDOT, MDE surveyed, no listing to read. Maryland open municipal rows 6 → 13 on the day (the roadmap's "from 5" baseline had grown to 6 that morning when MHT's Maritime round opened). Acceptance was 15: the shortfall is seasonal (CPP's and GOCPP's rounds are closed in October) and the GOCPP block, not a loosened rule | `connectors/md_mea.md`, `md_dnr.md`, `md_gocpp.md`, `maryland_sharepoint.md` |
| 6 | Navigator UI and hosting | 2026-10-15 | `LICENSE` + `LICENSE-DATA`; migration 0005 (`v_navigator_program`, `v_navigator_change`, `v_navigator_coverage`); `scripts/build_site.py` + `web/`: index with a tile-grid state map, 51 state pages with the new / closing / status-changed strip, faceted filters with counts, card list, detail panel, change log; `.github/workflows/site.yml` publishing to `gh-pages` daily; Lighthouse accessibility 100 on both page types; the Maryland page carries exactly the `v_municipal_page` rows | this file, decisions log, README |
| 8 | Mid-Atlantic portal survey | 2026-10-17 | DE, PA, VA, DC, WV, NJ surveyed live, Maryland as control; one table, every URL fetched on the day. No commercial grants vendor has a public listing in any of the six; the structured sources are state-run indexes: pa.gov's Coveo grants index (377 grants, 17 agencies, labelled status, dates, applicant types, 22 open to municipalities) and grants.wv.gov's `AvailableGrants` JSON (124 items, dates, eligibility text, 5 active). NJ DCA's IntelliGrants RFP page is public (8 structured RFPs); VA has a hand-kept Governor's table and Drupal agencies; DE has no state listing; DC has no municipalities and a notice feed | `docs/surveys/mid_atlantic.md` |
| 9.1 | Pennsylvania: `pa_grants` | 2026-10-17 | the first state outside Maryland, fed by pa.gov's Coveo grants index plus the JSON record each grant page embeds; labelled status (`Accepting applications` / `Closed`, a closed record with a future open date is forecasted), dates, applicant categories plus the shared keyword tagger over the free-text applicant line, award range, match, cycle wording as `closes_at_text`, `rolling` from the cycle. first live run 377 added (84 open, 2 forecasted, 291 closed), second run 0 changed; the Pennsylvania page shows 29 open municipal rows (26 likely) and 68 between rounds; search key read from the page each run; every detail page refetched (about ten minutes) | `connectors/pa_grants.md` |
| 8.2 | 50-state portal census (light) | 2026-10-18 | every state plus DC, one row each: portal, vendor, public listing, access, verdict; folds in the WebGrants spot-check (8.1). Three states are one connector away (CA: an open-data CSV of 2,023 grants with a labelled status; IL: the CSFA opportunity and program lists; IA: a WebGrants storefront with a Status column), WebGrants is the one vendor with a public listing in two states (IA, MT agencies), NJ and TX are small builds, NY needs a deeper look behind a PeopleSoft shell, 18 states are agency-by-agency, 10 hosts block this client, 7 states have no state-run index at the URLs found | `docs/surveys/state_portals.md` |
| 9.2 | West Virginia: `wv_grants` | 2026-10-18 | grants.wv.gov's `AvailableGrants` list through the state's JSON API: one POST, 124 records, no HTML. Status by the page's own date rule (active, future-posted), then the MEA rules for `Forecasted` text (a month or season still ahead is a forecast, a past one is a stale page, dateless wording is cycle text for the between-rounds group); `Pass-through` is the only funding-source claim; categories by division keyword with the division as source code. First run 124 added (5 open, 1 forecasted, 83 closed, 35 unknown), second run 0 changed; 1 open municipal row on the WV page, 0 between rounds (the county-only solid-waste rounds do not carry a `municipality` tag) | `connectors/wv_grants.md` |
| 9.3 | California: `ca_grants` | 2026-10-27 | the California Grants Portal's daily open-data CSV on data.ca.gov: one GET (6.6 MB) through the dataset download path, because data.ca.gov's robots.txt disallows `/api/`; no HTML. The portal's labelled status taken as is (active, closed, forecasted); `Public Agency` and `Other Legal Entity` tag nothing and `ApplicantTypeNotes` goes through the shared keyword tagger (fourth reuse); `Ongoing` deadlines are rolling; text open dates (`Fall 2026`) are kept as text. First run 2,025 added (164 open, 3 forecasted, 1,858 closed) in five seconds, second run 0 changed; the California page shows 28 open municipal rows (all likely) from 73 agencies and 52 between rounds | `connectors/ca_grants.md` |
| 9.4 | Illinois: `il_csfa` | 2026-10-28 | the Catalog of State Financial Assistance's opportunity list (GATA, omb.illinois.gov): one static table of the rounds posted now, 119 rows, plus a native opportunity page and its program page for the 35 that have one (eligibility, funding source, match, CSFA number) and the list alone for the 84 GMS rows that link out to AmpliFund (never fetched). Status from the list's own dates; `No end date` is rolling; `Government Organizations` tags nothing and the program's free-text eligibility decides. First run 119 added in 27 seconds, second run 0 changed; the Illinois page shows 11 open municipal rows (all likely) from 16 agencies, 0 between rounds | `connectors/il_csfa.md` |
| 9.5 | WebGrants storefronts: `webgrants` | 2026-10-28 | the one vendor platform with a public listing in two states: Iowa (`iowagrants.gov`) and Montana's Agriculture and Fish, Wildlife and Parks hosts (`webgrantscloud.com`) as configuration, columns read by header name. One static list per host plus one detail page per round, 41 requests. `Posted` and the round's own final date give the status; `Not Applicable` is rolling; `Recurring Opportunity: Yes` goes to the cycle text the between-rounds group reads. Applicants only from a page's eligibility section, judged sentence by sentence (a negated sentence beside the applicant statement is dropped, the statement stays). First run 40 added in 20 seconds (29 IA, 11 MT), second run 0 changed; the Iowa page shows 2 open municipal rows (CDBG disaster recovery), Montana 0 | `connectors/webgrants.md` |
| 9.6 | Texas: `tx_egrants` | 2026-10-28 | the Office of the Governor's eGrants announcements: the Active page plus the archive (six pages by offset, 147 rounds back to 2023), one server-rendered card markup, plain GETs. Status from each card's dates, never from the page that lists it (the Active page lists a round eight months past due). Applicants from the Eligible Organizations text, sentence by sentence; Total Funds kept as the source's words, never read as an award; a round's own page is empty to a plain GET, so only the cards are read. First run 147 added in 7 seconds (3 open, 144 closed), second run 0 changed; the Texas page shows 1 open municipal row and 29 between rounds | `connectors/tx_egrants.md` |
| 10.1 | One tagger, one vocabulary, DHCD cleanup | 2026-10-28 | the applicant tagger and funding-type rule moved to `connectors/text.py` (pa, wv, ca, il no longer import a Maryland module); `city`, `village`, `township`, `borough` and `local jurisdiction` tag a municipality, a named city (`Baltimore City`, `City of Philadelphia`) and `the local jurisdiction` do not; pa.gov, California and Illinois portal labels read from one table (economic development is infrastructure in every state, California's compound housing, community and economic development carries both housing and infrastructure). Measured on all 3,700 stored records: 389 hashes move, 378 of them California, none in Maryland. DHCD: Housing Leadership Awards takes its applicants from "Award categories", State Revitalization Programs takes them from its six sub-program pages (local governments, nonprofit community development organizations, institutions of higher education). **Found on the way:** the Maryland site now serves some pages on a different body markup, which `_prose()` read as empty; Maritime Heritage Grant was showing closed while open (deadline Nov 13) and Community Schools Rental Assistance had lost its renter eligibility. Both fixed. On the live data: Maryland open municipal rows 12 → 14, California 28 → 39 | `connectors/text.py`, `connectors/md_dhcd.md`, `connectors/maryland_drupal.md` |
| 9.7 | New Jersey: `nj_dca_sage` | 2026-10-28 | DCA's public SAGE (IntelliGrants) RFP list: one classic-ASP page, 10 RFPs from two divisions, every value in a `<span id="<field>_<n>_text">` read by id and document order (the page's HTML is not well formed, so a tree parser mis-nests it). No ID on the page, so the slug of the title is the key; a listed RFP is open until its own deadline passes; award minimum and maximum fill the amounts, the estimate of total funds stays in the structured field; the program contact is dropped before the payload is stored. The run aborts if the RFP count and the deadline-label count disagree. The second SAGE instance (`njsage`) was checked and is login-only. First run 10 added in 2.5 seconds, second run 0 changed; the New Jersey page shows 3 open municipal rows | `connectors/nj_dca_sage.md` |

## Next

### 6. Navigator UI and hosting (shipped, see Done)

Live at https://saj-sudo.github.io/funding-atlas/. Left for a later session, none blocking: shareable filter links
are in the URL hash already; a per-state RSS or JSON feed of the change log; the Grants.gov data-cleanup items under
milestone 10 show on the page as they are in the database (`&quot;` in deadline text, contact names as agencies).

### 7. Maryland depth (shipped 2026-10-16, see Done; two items remain)

Shipped: MEA and DNR, and the SharePoint base they share. Still open, none blocking:

- **GOCPP** (gocpp.maryland.gov): 43 grant programs on WordPress with a clean taxonomy (`eligible_apply-*` classes)
  and an open list, but `robots.txt` ends with `User-agent: * / Disallow: /`. Stopped per CLAUDE.md. Next step is a
  request to the office for crawl permission or a feed; the survey and the connector design are in
  `connectors/md_gocpp.md`. The municipal law-enforcement rounds (BARM, SAPP, PRAR, GVRG, ...) are the known gap.
- **MDEM** (mdem.maryland.gov, SharePoint): `/Pages/grants.aspx` says it is "still in development" and lists two
  programs with structured `Applications Open?` and deadline fields (NSGP, "open" with a 2023 deadline; FMA, closed,
  local governments eligible). `/community/Pages/Mitigation.aspx` redirects to `/Pages/hazard-mitigation.aspx`, which
  names no programs (a request-info form, the Resilient MD Revolving Loan Fund, FAQs). Two records is not a connector;
  revisit when the index grows. The base class fits it when that day comes.
- **MDOT** and **MDE**: no listing to enumerate from (survey in `connectors/md_dhcd.md`); three to five hand-written
  pages each. Candidates for a hand-listed `HAND_ADDED`-style connector on the SharePoint base if outreach asks for
  Bikeways, Urban Tree, or the water and sewer financing rows by name.

### 8. Mid-Atlantic portal survey (shipped 2026-10-17, see Done)

`docs/surveys/mid_atlantic.md`. Left open, none blocking: Virginia DEQ and VDEM and New Jersey DEP could not be read by
this client (Akamai 403, TLS through the proxy, Incapsula challenge) and are recorded as not verified; the Delaware index
is a University of Delaware Looker Studio dashboard, JavaScript only, not fetched; DC agency grants pages answer Drupal
"Access denied" to anonymous requests.

### 8.1 / 8.2 WebGrants spot-check and 50-state census (shipped 2026-10-18, see Done)

`docs/surveys/state_portals.md`. Open, none blocking: the ten blocked hosts (AK, CO, ID, KS, ME, MI, MN's listing, NM, RI,
OK's OGX) need a check from an ordinary browser to tell a bot wall from a proxy block; the JS shells (NY SFS, UT Looker
Studio, WY hub, KY DLG Portal, NV discovery) were recorded, not reverse-engineered; WebGrants was looked for only where a
state turned it up, so a third storefront state may exist.

### 9. Platform connectors

The survey found no commercial grants-management vendor with a public listing in two or more states, so the "platform" is
the state-run central index. One connector per session, in this order:

1. **`pa_grants`** (Pennsylvania, shipped 2026-10-17, see Done): enumerate from the pa.gov Coveo index (`searchHub: "All Grants"`, public search key
   read from `/grants/search` at run time), one record per `/grants/search/grant-details/<agency>/<n>` page, whose
   server-rendered JSON carries `status`, `openDate`, `closeDate`, `applicantType`, `applicantCategory`, `eligibility`,
   `matchingFundsRequirements`, `linkToApply`, `pointOfContact`, `last_modified`. 377 records, 84 accepting applications,
   22 open to municipalities on the survey date. Doc first: `docs/connectors/pa_grants.md` with the field mapping; decide
   there how far-future placeholder close dates (`2035-12-31`) become `rolling`, and that `Tax credit` and `Loan` rows
   keep their funding type.
2. **`wv_grants`** (West Virginia, shipped 2026-10-18, see Done): one `POST https://apps.wv.gov/SharePoint/api/search` with `siteurl=grants.wv.gov`,
   `listname=AvailableGrants`; JSON, no HTML. Status from dates by the page's own rule (`PostedDate <= today <= DueDate1`
   is active), `Forecasted` text to `closes_at_text`, `Modified` stored and excluded from the hash. 124 records, most of
   them stale 2022 to 2023 rounds; the diff is the product.
3. **`ca_grants`** (California, shipped 2026-10-27, see Done): one CSV from `data.ca.gov` (`california-grants-portal-data.csv`), 2,023 rows with a labelled
   `Status` (active / closed / forecasted), open date, deadline, applicant type, funding source, match, amounts, `LastUpdated`
   and `GrantURL`. No HTML. Doc question: the applicant-type vocabulary and the free-text notes that name cities and counties.
4. **`il_csfa`** (Illinois, shipped 2026-10-28, see Done): the CSFA opportunity list (title, agency, application date range, award range) and program list
   as HTML tables on `omb.illinois.gov/public/gata/csfa/`. Listed means open; "No end date" is rolling.
5. **`webgrants`** (Iowa, Montana agencies, shipped 2026-10-28, see Done): the WebGrants storefront, `storefrontFOList.do` plus one detail page per
   opportunity, a labelled `Status`; states and agency hosts as configuration. Decide in the doc what a round that leaves
   the storefront becomes.
6. **`tx_egrants`** (Texas Governor's Office) and **`nj_dca_sage`** (New Jersey DCA), both shipped 2026-10-28, see Done.
7. New York SFS: a deeper look for the Grant Opportunity Portal's endpoint. Agency connectors (VA, MA, OR, and the rest)
   only when a town asks; NC's and WA's seed lists and VA's Governor's table say which agencies first.

### 10. Data cleanup (small, rides any session)

Done 2026-10-18 (polish before outreach):
- Grants.gov `administering_agency` now comes from the record's `agencyDetails` (Grants.gov's agency table), then the
  search hit's agency, and only then the free-text synopsis field that held contact names and office codes. On the live
  database that corrects 89 of 955 records (14 of the 128 federal rows on the Maryland page); the one odd name left,
  "69A345 Office of the Under Secretary for Policy", is how Grants.gov's own agency table spells that office.
- Grants.gov close-date text is unescaped (`&quot;` and friends), the way titles already were.
- The SAM catalog runs in full in the daily workflow: 2,869 listings on the live database, every one of the 955
  Grants.gov opportunities with an ALN resolves to a listing (`v_aln_coverage`: 2,532 ALN references, 0 unmatched).
- Placeholder close dates (pa.gov's 2035-12-31 and 2999-07-01) render as "no deadline stated" with the source's date
  beside it, sort with the undated rows and leave the Deadline facet's "Has a date" bucket; the record keeps the date.
  `PLACEHOLDER_YEARS = 5` in `scripts/build_site.py`.

Done 2026-10-28 (10.1): the shared tagger matches `city`, `village`, `township`, `borough` and `local jurisdiction`; portal
labels share one table; the DHCD records the source names an applicant for (Housing Leadership Awards, State Revitalization
Programs) are tagged.

Still open, none of them fixable without inventing a fact (and, from 10.1 on, two tagger items found by `webgrants`: "local units of government" in that word order is not matched, and `residents` tags a household on a business grant):
- Main Street Improvement Grant lists "Main Street Maryland communities" and "community development organizations" as
  eligible and never says municipality, so it stays untagged. The 2026-10-16 note that it is a municipal round was an
  assumption; ask DHCD, or Saj decides to read "Main Street Maryland communities" as municipal.
- 13 of the 23 Illinois rounds that list only `Government Organizations` carry no municipal tag (their free text is `N/A`
  or `SEE NOFO`); several are plausibly town programs. Reading each round's NOFO attachment is the fix.
- Homelessness Solutions, Housing Choice Voucher, Lead Hazard Reduction and Tier Structure name no applicant type.
- The tagger reads `Baltimore City` as a named place, so a program for "county governments, including Baltimore City"
  tags county only.

### Outreach (tracked, not a milestone)

Gated on milestone 6 going live. Routes, in order: five small-town administrators whose towns recently received
DHCD or MHT awards; Maryland Municipal League staff; rural COGs (Tri-County Councils, Mid-Shore and Upper Shore
Regional Councils); Grant Professionals Association Maryland chapter and ELGL; Governor's Grants Office. Ask the
four questions in the page footer. Answers decide what milestone 11 is.

## Decisions log

| Date | Decision | Why | Recorded in |
|---|---|---|---|
| 2026-10-15 | Tier filter lives on the page, not in `v_municipal_relevance` | cheapest way to let a reader judge the business-program rows; the primary-applicant signal needs connector changes | `SPEC.md` relevance tiers |
| 2026-10-15 | The page carries likely + possible, excludes unlikely with a count | research notices on a municipal page cost credibility; the exclusion stays visible | migration 0004 header |
| 2026-10-15 | UI and hosting before Maryland depth | outreach needs something people want to open; a thin state side is a known, stated gap | this file |
| 2026-10-15 | Host on GitHub Pages | a live link outperforms an attachment in outreach; no server to run | milestone 6 |
| 2026-10-15 | License: MIT code, ODbL records | open data for the records, permissive for the code; files land with milestone 6 | `SPEC.md` licensing |
| 2026-10-15 | Expansion is platform-first, Mid-Atlantic first | agency-by-agency does not scale to 50 states for one person; neighbours share COGs and media | milestones 8 and 9 |
| 2026-10-15 | Agency-by-agency across 50 states rejected | 150+ hand-built parsers is the DSIRE trap the project exists to avoid | this file |
| 2026-10-15 | Repo goes public | GitHub Pages on a free account needs it; the pitch is open connectors and SQL-auditable rules, which a private repo undercuts; nothing sensitive in the tree | milestone 6 |
| 2026-10-15 | The database rides the `gh-pages` branch with the site | it must persist between runs for change detection; one git push is one mechanism; an Actions cache evicts after 7 idle days; as a bonus `/atlas.db.gz` is a public data download; gzipped because the raw file is 84 MB on day one and GitHub refuses blobs over 100 MB | `site.yml` |
| 2026-10-15 | Daily schedule; a push to `main` rebuilds without re-reading sources | deadlines and new notices move daily; UI changes go live on merge without hammering the agencies | `site.yml` |
| 2026-10-15 | Tile-grid cartogram, not a geographic map | no map asset, every tile is a plain link with the state's coverage as its name, reads at phone width | `web/app.js` |
| 2026-10-15 | "New" means first seen after the source's first full read | on a connector's first run every record is `added`; a page saying "134 new this week" on launch day is true and useless | `scripts/build_site.py` |
| 2026-10-15 | Single-file Maryland export retired | each state page is still one self-contained file; two exporters is one too many for a solo operator | milestone 6 |
| 2026-10-15 | Likely tier checked by default, possible one click away | same choice as milestone 5; counts on the facet make the second tier visible | `web/app.js` |
| 2026-10-16 | Shared applicant table gains `municipal` | "county and municipal governments" (MEA) and "governing bodies of municipal corporations" (DNR) matched nothing; one DHCD record changed, correctly | `connectors/maryland_drupal.md` |
| 2026-10-16 | SharePoint base extracted at the second mdgov site, with MEA's fixture hashes as the gate | same rule that produced `maryland_drupal.py`; MDEM, MDOT and MDE are on the same theme | `connectors/maryland_sharepoint.md` |
| 2026-10-16 | Text hash, not markup hash, and every page every run on SharePoint | the CDN stamps one `Last-Modified` on every page and Cloudflare rewrites the e-mail markup per response; the sites are small | `connectors/maryland_sharepoint.md` |
| 2026-10-16 | A stated deadline with no status wording: open while ahead, `unknown` after | the source says applications are due on a date; a past date on a page that says nothing else is a stale page, not a closure; the views drop it either way | `connectors/md_mea.md` decision 4 |
| 2026-10-16 | A future launch or FOA issue date turns a closed page into `forecasted` | DHCD's rule applied to MEA's labels (Megawatts for Maryland) | `connectors/md_mea.md` decision 3 |
| 2026-10-16 | Index facts are stamped on records, the index page is not a record | the pipeline normalizes every RawRecord into a Program; added and missing already show additions and removals | `connectors/maryland_sharepoint.md` |
| 2026-10-16 | "No longer accepting" is not a closed phrase on DNR | the Grants Gateway says it about another program; an open phrase inside a negated sentence does not open a page either | `connectors/md_dnr.md` decision 1 |
| 2026-10-16 | GOCPP stopped on robots.txt | `User-agent: * / Disallow: /`; CLAUDE.md says say so and stop; ask the office | `connectors/md_gocpp.md` |
| 2026-10-16 | MEA's FY27 General Notice PDF not parsed | the table flattens badly and every launch date is on the program page | `connectors/md_mea.md` decision 7 |
| 2026-10-16 | Between rounds is a separate, collapsed group, not a status or a tier | a town prepares months before a round opens; the open list must keep meaning "apply now or soon"; closed or past-deadline state programs within 15 months of their last deadline go in an appendix, off by default like the possible tier | migration 0006 |
| 2026-10-16 | Federal notices are never "between rounds" | Grants.gov closes a notice with a real date when it leaves the search, so hundreds of one-off numbers would land on all 51 pages; the recurring federal thing is the Assistance Listing | migration 0006 header |
| 2026-10-16 | Reopening dates are observed, never computed | `last_reopened` is the change log's last closed-to-open flip and stays null until one has happened; no "expected next round" is derived from a calendar | migration 0006 |
| 2026-10-16 | A keyword tags an applicant only in noun position | `individual` matched the adjective ("individual school facilities", "individual private lands"); plural always, singular only before punctuation or a function word; four records lose a wrong tag, none gains one | `connectors/maryland_drupal.md` |
| 2026-10-16 | No `connectors/text.py` yet | the SharePoint base imports the text helpers from the Drupal module, as `md_mht` already imported `parse_date` from Grants.gov; a third platform base forces the move | `connectors/maryland_sharepoint.md` |
| 2026-10-17 | Milestone 9 starts with pa.gov's grants index, not a vendor platform | the survey found no WebGrants, AmpliFund, eCivis, SmartSimple, Submittable or Fluxx public listing in any of the six states; vendor systems (IntelliGrants, CGI Advantage, eGrants, CAMS, OGMS) are logins; the structured, status-bearing source is Pennsylvania's state-run Coveo index, 377 records from 17 agencies | `docs/surveys/mid_atlantic.md` |
| 2026-10-17 | West Virginia second, as a JSON connector | one POST returns the whole list with dates and eligibility text; the list is thin and stale, so the value is the diff when rounds are re-posted | `docs/surveys/mid_atlantic.md` |
| 2026-10-17 | DC out of the municipal scope | the District has no municipalities; its clearinghouse is a feed of RFA notices with a release date and a PDF, no status or deadline field | `docs/surveys/mid_atlantic.md` |
| 2026-10-17 | Blocked or unreadable hosts recorded, not worked around | VA DEQ (Akamai 403), VDEM (TLS through the proxy), NJ DEP (Incapsula challenge), DC agency grants pages (Drupal access denied), the Delaware Looker Studio portal (JavaScript only); same rule as GOCPP | `docs/surveys/mid_atlantic.md` |
| 2026-10-17 | CMS is not a platform | MD, VA and DC agencies are all Drupal and MD and WV share a SharePoint release, but the markup differs per theme and WV's data comes from an API; `maryland_drupal.py` and `maryland_sharepoint.py` do not transfer, and no CMS base is extracted ahead of a second site | `docs/surveys/mid_atlantic.md` |
| 2026-10-17 | pa.gov's Coveo search key is read from the search page every run | it is a public token in the page markup and rotates on site rebuilds; a hard-coded key is a connector that silently returns nothing one day | `connectors/pa_grants.md` decision 1 |
| 2026-10-17 | `Public Agency` and `Other Legal Entity` tag no applicant type | one category covers counties, state agencies, authorities and special districts; tagging all four would invent eligibility; the free-text applicant line names the real ones and the shared keyword tagger reads it (third reuse, still no `connectors/text.py`) | `connectors/pa_grants.md` decision 2 |
| 2026-10-17 | Placeholder close dates (2035-12-31, 2999-07-01) are kept; `rolling` comes from the cycle wording | the record keeps what the source states; `Reoccurring`, `Continuous`, `Revolving Loan Fund` say rolling, a far-off date does not | `connectors/pa_grants.md` decision 3 |
| 2026-10-17 | A closed record with a future open date is forecasted only when its close date is not before the open date | `dmva/1` opens 2026-11-02 (forecasted); `pema/14` opens 2028 and closed 2018, an inconsistent record kept as closed | `connectors/pa_grants.md` status rules |
| 2026-10-17 | Every pa.gov detail page is refetched each run | the Coveo hit carries only the indexer's dates; the record's `last_modified` is stored in the payload, outside the hash, as the future gate | `connectors/pa_grants.md` |
| 2026-10-17 | WebGrants spot-check after Pennsylvania, not before | Montana and Iowa serve public WebGrants listings, the first vendor platform seen with a public face; Pennsylvania is the neighbour with the biggest labelled-status source, so it ships first | this file, 8.1 |
| 2026-10-18 | California next after West Virginia, then Illinois, then a `webgrants` connector | the census ranked public indexes by records per session: CA is one CSV with a labelled status (2,023 rows), IL two HTML tables, WebGrants two states on one parser | `docs/surveys/state_portals.md` |
| 2026-10-18 | WebGrants storefront is the one vendor platform worth a connector | public in Iowa and on Montana's agency hosts with identical columns and a `Status` field; every other vendor's public face is a login or a JS shell | `docs/surveys/state_portals.md` |
| 2026-10-18 | Blocked hosts and JS shells are recorded, not circumvented | ten states refuse this client (Akamai, CloudFront, Cloudflare, DataDome, Radware, Azure WAF, proxy resets); whether a browser sees the same is for the operator to check once; the GOCPP rule | `docs/surveys/state_portals.md` |
| 2026-10-18 | ADECA's `ClaudeBot` disallow is flagged for the operator | the only robots file in the census naming an AI crawler; the connector's agent is not ClaudeBot and the file has no rule for other agents, but the operator decides whether to read the site at all | `docs/surveys/state_portals.md` |
| 2026-10-18 | A close date more than five years out is shown as "no deadline stated", never dropped | pa.gov writes 2035-12-31 and 2999-07-01 to mean no deadline; a reader seeing "closes in 110 months" would think the page is broken; the record keeps the source's date and the rule lives in the exporter, not the connector | `scripts/build_site.py` |
| 2026-10-18 | Grants.gov agency names come from the agency table, not the typed synopsis field | the synopsis field held contact names ("Teresa M Parker-Reeser Grants Officer") on 14 of 128 federal rows on the Maryland page | `connectors/grants_gov.py` |
| 2026-10-18 | West Virginia's `Forecasted` text is read like MEA's cycle sentences | the page calls any item with text "Forecasted", including "Spring 2023"; a date still ahead is a forecast, a past one is a stale page (closed if the due date passed, else unknown), dateless wording ("Annual deadline of April 1st") is cycle text kept in `closes_at_text` | `connectors/wv_grants.md` decision 1 |
| 2026-10-18 | `Formula` and `Entitlement` are not pass-through on grants.wv.gov | `TypeOfGrant` says how the money is competed, not whose it is; only the four items that say `Pass-through` get the tag | `connectors/wv_grants.md` decision 2 |
| 2026-10-18 | The live site is down because the repository is private | GitHub Pages on a free account serves public repositories only (the 2026-10-15 decision); `saj-sudo.github.io/funding-atlas` answers 404 on every path while `gh-pages` holds a build from 2026-10-17 18:48 and the daily workflow succeeds; making the repository public again, or moving Pages to a paid plan, is the operator's call | this file |
| 2026-10-27 | California's CSV is read through the dataset download path, not the CKAN API | `data.ca.gov/robots.txt` disallows `/api/`; the download path is allowed and 302s to signed storage; the resource id is a constant, so a replaced resource fails the run loudly | `connectors/ca_grants.md` decision 1 |
| 2026-10-27 | California's `Public Agency` tags no applicant type | the pa_grants rule: it covers state departments, JPAs, special districts, cities and counties, and 149 of 164 active rows carry it; the notes tag 28 active rows `municipality` | `connectors/ca_grants.md` decision 2 |
| 2026-10-27 | One estimated award amount is both the minimum and the maximum | `EstAmounts` is the per-award estimate; a single figure is the source's one number, not a ceiling; total funds stay in the payload | `connectors/ca_grants.md` decision 3 |
| 2026-10-27 | "Housing, Community and Economic Development" maps to housing | the label leads with housing; the portal word stays as `source_code` | `connectors/ca_grants.md` decision 4 |
| 2026-10-28 | Illinois GMS rows are read from the list alone; AmpliFund pages are not fetched | 84 of 119 rows link out to a second vendor host that serves no robots rules; the list already gives a title, agency, dates and award range; the 60 DNR rows are the open question once someone has looked at the Illinois page | `connectors/il_csfa.md` decision 1 |
| 2026-10-28 | A round that leaves Illinois's list is `unknown`, closed only if its native page still shows an ended range | the list is "posted now" and a round that ends is dropped, which the source does not state as a closure; the WebGrants question answered the same way | `connectors/il_csfa.md` |
| 2026-10-28 | `Government Organizations`, `Education Organizations` and `Other` tag no applicant type | the pa_grants and ca_grants rule again; 13 of the 23 native rounds that carry `Government Organizations` get no municipal tag, several plausibly town programs, because the source does not say | `connectors/il_csfa.md` decision 2 |
| 2026-10-28 | `connectors/text.py` exists now | supersedes 2026-10-16 "No `connectors/text.py` yet": the tagger and funding-type rule served six connectors in five states from a Maryland module; moved verbatim, every stored record re-normalized to the same hash, the Maryland modules import the names back | `connectors/text.py` |
| 2026-10-28 | Portal labels are one table, a label naming two topics carries both | pa.gov's "Community & Economic Development", Illinois's "Economic Development" and California's "Housing, Community and Economic Development" are one subject; DHCD's energy-home-repair already carried two categories | `connectors/text.py` `PORTAL_CATEGORIES` |
| 2026-10-28 | A named city does not tag a municipality; `the local jurisdiction` does not either | `Baltimore City` and `City of Philadelphia` are one place, and "takes the letter to the local jurisdiction" names the reviewer, not the applicant; without the guards Philadelphia's Local Share Account and Maryland's county formula would have landed on every town's page | `connectors/text.py` |
| 2026-10-28 | State Revitalization Programs takes its applicants from its sub-program pages | the umbrella page says "for eligibility, review the funding programs"; each run reads the six linked pages once, and a page that cannot be read leaves the stored copy standing | `connectors/md_dhcd.md` |
| 2026-10-28 | Main Street Improvement Grant stays untagged | the page names "Main Street Maryland communities" and never says municipality; the 2026-10-16 "municipal round" was an assumption, not the source | `connectors/md_dhcd.md` |
| 2026-10-28 | The body selector accepts both Maryland markups, the old exact form first | the site serves `<div class="usa-prose maryland-toc-target">` on older pages and nested `maryland-toc-target` > `usa-prose` on new ones; the old form is tried first so nothing that parsed before parses differently | `connectors/maryland_drupal.md` |
| 2026-10-28 | WebGrants applicants come from the eligibility section only, negation judged per sentence | 13 of 40 pages have an eligibility heading; reading the whole description finds four more municipal rows and tags incidental text (a potato research program tags `municipality`); a paragraph with "cities, counties are not eligible" beside the applicant sentence must lose the one sentence, not the paragraph, and a first sentence must not be lost to a later "not" | `connectors/webgrants.md` decision 2 |
| 2026-10-28 | A round that leaves a WebGrants storefront is `unknown`, with no request | the storefront drops an ended round and answers HTTP 500 for an id it no longer lists, and a detail key cannot be derived from the visible ID; unverified against a real removal, to be settled by the first one | `connectors/webgrants.md` |
| 2026-10-28 | A WebGrants host list that cannot be read aborts the run | otherwise every round on that host would look missing and be marked `unknown`; a detail page that cannot be read falls back to the stored copy | `connectors/webgrants.md` decision 6 |
| 2026-10-28 | The program officer's name, phone and e-mail are dropped before the payload is stored | the database is published on `gh-pages`; the state shows them on its page, there is no reason for us to redistribute them | `connectors/webgrants.md` |
| 2026-10-28 | Texas status comes from the card's dates, not from the page that lists it | the Active page lists the Violence Against Women round with a due date of 2026-02-12; "listed" is not "open" here, unlike Illinois and the WebGrants storefronts | `connectors/tx_egrants.md` decision 1 |
| 2026-10-28 | Texas Total Funds is kept as the source's words and never read as an award | `$TBD`, `$15 Million` and `$TBD - at least N% of available SHSP funding` are program totals in no common unit; `amount_min` and `amount_max` stay null | `connectors/tx_egrants.md` decision 3 |
| 2026-10-28 | The Texas archive is read in full every run, and a page that cannot be read (or an archive past the 20-page cap) aborts the run | closed rounds are the history the between-rounds group needs, and a partial read would mark every unread archived round `unknown` | `connectors/tx_egrants.md` decisions 5 to 7 |
| 2026-10-28 | A round's own eGrants page is not read | to a plain GET it holds none of the round's content (only site chrome and the contact block); the card is the whole public record, and no browser workaround is attempted | `connectors/tx_egrants.md` |
| 2026-10-28 | A New Jersey RFP is keyed by the slug of its title, and a retitled RFP is a new record | the page has no ID and `n` is positional; titles carry the year, so a new cycle is a new round and the old one goes `unknown`, which is the correct picture | `connectors/nj_dca_sage.md` |
| 2026-10-28 | The New Jersey run aborts when the RFP count and the deadline-label count disagree, or an empty page lacks the instruction text | an error page or a changed layout must fail loudly rather than mark every RFP missing; the empty-list shape is a guess, and a wrong guess aborts, the safe direction | `connectors/nj_dca_sage.md` decision 3 |
| 2026-10-28 | A `tax_credit` title is not a funding type on the New Jersey page | "Neighborhood Revitalization Tax Credit Planning" is a planning grant (the page gives it a grant period) named for the program it supports; the connector keeps `loan` and `grant` from the title and leaves the rest null | `connectors/nj_dca_sage.md` decision 4 |
| 2026-10-28 | The second New Jersey SAGE instance (`njsage.intelligrants.com`) is login-only and out of scope | its opportunities URL redirects to a login and the RFP list path answers 404; DCA's page is the only public New Jersey listing | `connectors/nj_dca_sage.md` |

## Open questions (do not resolve in code yet)

- Who pays: state contract vs association license vs data feed. Decide after outreach feedback.
- Rules-as-code partner for the individual side (PolicyEngine / OpenFisca). Not before the registry is proven.
