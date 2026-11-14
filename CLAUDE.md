# funding-atlas

A jurisdiction-indexed registry of public funding programs with open connectors and change detection, plus a
municipal grant navigator on top. Product scope, record model and status rules: `docs/SPEC.md`. Plan, decisions
and what comes next: `docs/ROADMAP.md`. Per-source field mappings: `docs/connectors/`.

## Operator

Saj, solo, alongside a full-time data job. Expert SQL, learning Python. ADHD: keep the task surface small, one
connector or one feature per session, no abstractions before the third real case forces them.

## Architecture

- Python 3.12, `uv`, SQLite via `sqlite3` (Postgres later), `httpx`, `pydantic` for the record model, `typer` CLI.
- `connectors/`: one module per source exposing `fetch(limit, prior) -> list[RawRecord]`,
  `normalize(raw) -> Program`, `resolve_missing(source_id)`. Keep them dumb. Maryland's Drupal agencies share
  `connectors/maryland_drupal.py` and its SharePoint agencies `connectors/maryland_sharepoint.py`; a few hand-listed pages of one agency (Virginia DCR, Delaware DNREC, DelDOT, DSHA,
  Maryland MDOT) go on `connectors/hand_list.py`, Vermont's four agencies on `connectors/vermont_drupal.py`, Connecticut's four on `connectors/connecticut_portal.py`, North Dakota's four on `connectors/north_dakota_drupal.py`, Kentucky's four on `connectors/kentucky_sharepoint.py` and Missouri's four on `connectors/missouri_drupal.py` (Nebraska's three, `ne_ded`, `ne_dwee` and `ne_dot`, each carry a small reader of their own in the module, WordPress, Drupal and Umbraco, because no two share a platform) (each a state CMS's page reader over the agency-page table and `AgencyPageConnector` in `hand_list.py`; a page that holds several programs is one record per program through its `SPLITS`) (`HandListConnector`: a page dict, `parse_page`, `fields`, a default status
  table; `docs/connectors/hand_list.md` says how a new agency goes on it in forty lines); `pa_grants` reads a
  search index plus one JSON record per page; a new platform base is extracted only when the second site on that
  platform forces it.
- `connectors/text.py`: the rules every state shares: the applicant tagger, the funding-type keyword, and the tables that
  turn a portal's own applicant and topic labels into ours. A rule that is wrong for one source is wrong for all and is
  fixed there; a portal label is added to the table once, not per connector. A rule change is measured on every stored
  record with `scripts/measure_tagger.py` (snapshot before and after on the database restored from `gh-pages`, then diff), and on every fixture of every agency-page connector (the stored database does not hold connectors no daily run has read yet).
- `pipeline/`: run a connector, normalize, hash, upsert, log changes, write the diff.
- `db/`: `schema.sql` plus numbered migrations. Views carry the analytical logic; SQL stays visible.
- `tests/`: fixtures per connector, never the network. CI runs `ruff check .` and `pytest -q`.
- `scripts/build_site.py` (`cli.py export`): builds `site/` (index + one page per state) from the navigator views
  (migrations 0005 and 0006). The markup, stylesheet and script are real files in `web/` with `{{SLOT}}` placeholders; Python
  only queries SQL and fills them in. No framework, no build step, no external requests from the pages.
- `.github/workflows/site.yml`: daily connector runs + rebuild, published to the `gh-pages` branch together with
  `atlas.db` (the database is restored from there at the start of each run). Generated files never land on `main`.

## How to work in this repo

- Plan before coding. For any new connector: URL, a sample of the raw data, and the field mapping, in a doc under
  `docs/connectors/`, before writing the parser.
- One connector or one feature per session. Finish it, test it against fixtures, commit.
- Never invent program data. If the source does not say it, the field is null. Status is what the source says on
  the run date; `unknown` beats a guess.
- When a source blocks scraping or has no structured listing, say so and stop. No headless-browser workaround
  without asking.
- Prefer SQL for anything analytical. Python fetches and shapes.
- Record decisions in `docs/ROADMAP.md` (decisions log) rather than in code comments or chat.
- Commit messages: `connector(md-dhcd): ...`, `pipeline: ...`, `schema: ...`, `export: ...`, `docs: ...`.
- Commit author: `Saj Chandoo <263086808+saj-sudo@users.noreply.github.com>` (the GitHub noreply identity), never the
  account e-mail; the repository is public and its history is the record.

## Current state (2026-11-14)

Connectors: `grants_gov`, `sam_assistance_listings`, `md_dhcd`, `md_commerce`, `md_mht` (Drupal base), `md_mea`,
`md_dnr`, `md_mdem` (the MDEM grant roster plus two hand-added pages, 4 records) and `md_mde` (MWIFA's seven financing
rows, status from the index banner) on the SharePoint base (`connectors/maryland_sharepoint.py`), `md_mdot` (three hand-listed
MDOT pages, comments stripped, 3 records), `pa_grants` (pa.gov Coveo index, 377 records), `wv_grants`
(grants.wv.gov JSON API, 124 records), `ca_grants` (data.ca.gov CSV, 2,025 records), `il_csfa` (Illinois CSFA list plus its AmpliFund pages, 125 records), `webgrants` (Iowa, Montana and, since 2026-11-05, North Dakota storefronts), `tx_egrants` (Texas Governor's eGrants, 147 records), `nj_dca_sage` (New Jersey DCA SAGE list, 10 records), `ny_sfs` (New York SFS
Grant Opportunity Portal, PeopleSoft read through its own form posts, 257 records), `va_dcjs` (Virginia DCJS, 59 records),
`va_dhcd` (Virginia DHCD, a crawl of its menus, 30 records), `va_dcr` (six DCR grant pages) and `va_vdot` (six VDOT Local
Assistance programs): Virginia's municipal five, VDEM excepted (unreachable); `de_dnrec` (twelve DNREC Environmental Finance
pages), `de_dema` (ten FEMA pass-throughs), `de_deldot` (TAP and Safe Routes) and `de_dsha` (Housing Delaware's Build & Develop
pages, 18 programs): Delaware's four; `ma_onestop` (Massachusetts's Community One Stop for Growth, 14 programs under one round, 2026-11-04); `or_biz` (Business Oregon's whole Programs index, 99 records, most `unknown` with the cycle sentence kept, 2026-11-04); `nc_grants` (nc.gov's grant table, 75 directory rows) and `wa_fund_directory` (the Treasurer's Fund Directory, 128 directory rows), both every row `unknown` (2026-11-04); `ky_dlg` (Kentucky's DLG Portal, the grid's own JSON plus one page per round, 4 records, 2026-11-04); `vt_accd`, `vt_vtrans`, `vt_fpr`, `vt_vem` (Vermont's municipal four on one base, `connectors/vermont_drupal.py`, 20 records since the split rule, 2026-11-04); `ct_doh`, `ct_dot`, `ct_deep`, `ct_demhs` (Connecticut's municipal four on one portal.ct.gov base, 14 records, 2026-11-05); `nd_commerce`, `nd_dot`, `nd_des`, `nd_parks` (North Dakota's municipal four on one `ndit_base` Drupal 11 reader, `connectors/north_dakota_drupal.py`, 20 records since the split rule, 2026-11-11); `ky_dlgfed`, `ky_tc`, `ky_eec`, `ky_kia` (Kentucky's agency pages on one SharePoint reader, 24 records, the EEC's Grants and Loans index as six, 2026-11-11); `mo_ded`, `mo_dnr`, `mo_modot`, `mo_sema`, `mo_parks` (Missouri's five agencies on one `mo.gov` Drupal reader, SEMA on its older CMS through `#main-content`, State Parks' ORLP read from the Grant Opportunities hub through `SPLITS`: 7, 20, 2, 4 and 5 records, 2026-11-11); `ne_ded` (DED's CDBG as six records plus CCCFF, the Trust Fund, RCRP and SBDF: 10, WordPress, three seconds between GETs for its `Crawl-delay`), `ne_dwee` (the merged environment agency's nine aid pages, Drupal 10) and `ne_dot` (NDOT's local programs and the transit page as four: 8, Umbraco), Nebraska's three, each with its own reader because no two share a platform: 10, 9 and 8 records, 2026-11-14).
Milestones 1 to 8.2 (with 6.1, the Atom + JSON change feed beside every page, 2026-11-03), 9.1 to 9.8 (with 9.4.1 Illinois
depth and 9.6.1 Texas funding sources), 10.1 to 10.6 (10.6 the recorded gaps across every state, measured, 2026-11-11), 7.2 to 7.4 (Maryland's MDEM, MDOT and MDE, 2026-11-03) and 11.1 to 11.8
shipped; milestone 12 began on 2026-11-04 (12.0 the `probe-hosts` workflow, 12.1 the hand-list base, 12.2 AmpliFund has no public list, 12.3
Massachusetts, 12.3b Oregon, 12.4 the NC and WA seed lists, 12.5 the JavaScript shells: Kentucky built, UT, WY and DE stopped, NV's NOFOs to NEVADA ePro, 12.6a Vermont's municipal four, 12.6b Connecticut's, 12.6c North Dakota: part 1 its WebGrants storefront with 10.5 "political subdivisions", part 2 its municipal four, 12.6d Kentucky's agency pages, 12.6e Missouri's four agencies, 12.6f Missouri State Parks, 12.6g Nebraska's three agencies); the blocked ten were settled from the daily runner (eight blocked for good, MN and NM to 12.8); Maryland has eight agencies, Virginia and Delaware their municipal five, and the roadmap's next session is 12.6h, the next agency state in the ranking (AR, SD, TN, NV, AZ), outreach alongside; Nebraska's calls, settled 2026-11-14 in the decisions log (Game and Parks and NIFA disallow `ClaudeBot` and are not read; a month and a day with no year stays `unknown`; a "local public agencies" tagger rule moved 34 California records and was not kept) and Missouri's scope calls (the CDBG disaster pages left out, SEMA's Mitigation as one record, the State Parks Bus Grant in) are noted for Saj in the decisions log. The repository is public and the site is live at
https://saj-sudo.github.io/funding-atlas/ (2026-11-03); `gh-pages` holds the build. GOCPP is blocked by its robots.txt (ask the office). The census (`docs/surveys/state_portals.md`) is spent:
every public state index with structured rows is built; Virginia and Delaware have their municipal five
(decision 2026-11-03, milestone 11); elsewhere agency connectors only when outreach names a town. New York's
`Governmental Entity` rows read their Solicitation Profile for governmental applicants (decision 2026-11-03). **Start with the "Start here" block at the top of the roadmap's Next section**: the next
action, what waits on Saj, and the open follow-ups in one place.
