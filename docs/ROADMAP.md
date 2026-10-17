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

### 8.1 WebGrants spot-check (half a session, no code)

Montana (`funding.mt.gov`, "WebGrants - State of Montana") and Iowa (`iowagrants.gov`) serve public WebGrants listings; Euna's
AmpliFund and eCivis public pages redirect to a login. Check what a WebGrants opportunity page states (status? dates?
eligibility?), find two more WebGrants states, and decide whether one `webgrants` connector unlocks several states or
stays a per-state job. State-run indexes seen in passing, each a `pa_grants`-shaped connector of its own: California
(`grants.ca.gov`, open-data API), Illinois (GATA CSFA catalog), New York (Grants Management), Texas (eGrants).

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
2. **`wv_grants`** (West Virginia): one `POST https://apps.wv.gov/SharePoint/api/search` with `siteurl=grants.wv.gov`,
   `listname=AvailableGrants`; JSON, no HTML. Status from dates by the page's own rule (`PostedDate <= today <= DueDate1`
   is active), `Forecasted` text to `closes_at_text`, `Modified` stored and excluded from the hash. 124 records, most of
   them stale 2022 to 2023 rounds; the diff is the product.
3. **`nj_dca_sage`** (New Jersey DCA): `dcasage.intelligrants.com/RFPMailingRequest_List.asp`, 8 structured RFPs, when
   New Jersey outreach starts. Becomes a platform connector if a second IntelliGrants instance exposes the same page.
4. Agency connectors (VA DHCD Drupal 10, VA DCJS solicitation view, DE DNREC WordPress) only when a town asks. A state
   is configuration where the platform allows it; a new parsing base is extracted at the second site that forces it.

### 10. Data cleanup (small, rides any session)

- Grants.gov `administering_agency` sometimes holds a contact name or an office code ("Jeffrey Brown Management and
  Program Analyst", "69A345 Office of the Under Secretary for Policy"). Prefer the agency derived from `agencyCode`.
- Grants.gov close-date text keeps HTML entities (`&quot;`). Unescape it the way titles are.
- Run the full SAM catalog before any outreach so listing lines fill in (2 of 128 federal rows today, from a
  60-listing test run).
- Nine DHCD records have no applicant tags (State Revitalization Programs, Main Street Improvement Grant, others
  listed in `connectors/md_dhcd.md`); SRP and MIP are municipal rounds and will not surface when they reopen.

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

## Open questions (do not resolve in code yet)

- Who pays: state contract vs association license vs data feed. Decide after outreach feedback.
- Rules-as-code partner for the individual side (PolicyEngine / OpenFisca). Not before the registry is proven.
