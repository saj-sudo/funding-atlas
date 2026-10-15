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

## Next

### 6. Navigator UI and hosting

Goal: a page people want to use and that screenshots well, live at a public URL.

Brief:
- State picker for all 50 states and DC. Federal rows are national already (jurisdiction `US`); every state gets them
  on day one. State coverage is shown per state, honestly: "Maryland: 3 agencies, 78 programs. Virginia: no state
  sources yet."
- Landing view leads with change and time: new this week, closing within 30 days, status flipped since the last run.
  These come from `first_seen`, `closes_at` and `program_change`; no new data is needed.
- Faceted filters: tier, level, agency, category, funding type, status, rolling, text. Counts on every facet.
- Detail panel per program: summary, verbatim eligibility, applicant tags, categories, Assistance Listings cited,
  first seen / last changed, source link. Nothing invented, blanks stay blank.
- A changes feed: the last N `program_change` rows across connectors, readable as a log.
- Print and screenshot friendly; works at phone width; accessible (keyboard, contrast, labels).
- No framework or build step unless the session decides it is worth it; one generated page per state plus an index
  is the default architecture. Data embedded as JSON, rendered client-side, so the generator stays small.
- Hosting: GitHub Pages. A workflow runs the connectors and the export on a schedule and commits the built site to a
  `gh-pages` branch or `site/` directory. Generated files are never committed to `main`.
- First action of the session: add `LICENSE` (MIT) and `LICENSE-DATA` (ODbL), per the decisions log.

Acceptance: live URL; screenshots of the landing view, a filtered list and a detail panel; the Maryland page shows
the same 133 rows as `v_municipal_page`; Lighthouse accessibility pass; no external requests from the page.

Must not: touch the connectors or the relevance view; invent fields the sources do not provide.

### 7. Maryland depth

Goal: the state side of the Maryland page covers the agencies that fund towns, not just the three Drupal sites.

Order, from the surveys in `connectors/md_dhcd.md` and `connectors/maryland_drupal.md`:
1. **MEA** (energy.maryland.gov). Survey runner-up. `all-incentives.aspx` tables, program pages with a parseable
   "Program Status:" sentence, FY27 General Notice PDF with launch dates. SharePoint, no sitemap.
2. **DNR** grants and loans index (`/Pages/grantsandloans.aspx`), ~30 programs across sub-sites; Program Open Space
   Local, Community Parks and Playgrounds, Waterway Improvement are the municipal ones.
3. **GOCPP** (Governor's Office of Crime Prevention and Policy): the local law-enforcement and victim-services rounds.
4. **MDEM**: FEMA pass-throughs (HMGP, BRIC, EMPG).
5. **MDOT** (Bikeways, Urban Tree, SHA programs on roads.maryland.gov) and **MDE** (water and sewer financing,
   Bay Restoration Fund).

Approach for SharePoint sites: enumerate from the hand-curated index page, store the index payload so additions and
removals show in the diff, per-page prose status with the same closed-beats-active rule Commerce uses, change signal
from the `Last-Modified` header or a hash of the main content. Each connector gets its own doc, fixtures and
expected-result section before the parser. Ask before any headless-browser workaround.

Acceptance: open municipal state rows at least triple (from 5); every new connector has a second-run "no changes"
result recorded in its doc.

### 8. Mid-Atlantic portal survey

Goal: know where each neighbouring state lists its pass-through money, before writing any parser.

States: DE, PA, VA, DC, WV, NJ. Maryland as the control row.

For each: central grants portal URL (if any); platform vendor (recognise WebGrants, AmpliFund, eCivis / Euna,
SmartSimple, Submittable, Fluxx, custom); whether it lists programs with status and dates or only awards and
applications; robots.txt and sitemap; the top three agencies for local governments if there is no portal; one raw
sample per promising source.

Output: `docs/surveys/mid_atlantic.md`, one table, every cell filled or marked "not found", every URL verified live on
the survey date. No code.

Acceptance: the table, plus a ranked list of platform connectors to build and the states each one unlocks.

### 9. Platform connectors

One connector per platform the survey finds in two or more states. A state is configuration (base URL, agency map,
jurisdiction code), not a module. Extract a shared platform base only when the second state on that platform forces
it, the same rule that produced `maryland_drupal.py`. One platform per session.

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

## Open questions (do not resolve in code yet)

- Who pays: state contract vs association license vs data feed. Decide after outreach feedback.
- Rules-as-code partner for the individual side (PolicyEngine / OpenFisca). Not before the registry is proven.
