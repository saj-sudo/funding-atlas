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
  `connectors/maryland_drupal.py` and its SharePoint agencies `connectors/maryland_sharepoint.py`; `pa_grants` reads a
  search index plus one JSON record per page; a new platform base is extracted only when the second site on that
  platform forces it.
- `connectors/text.py`: the rules every state shares: the applicant tagger, the funding-type keyword, and the tables that
  turn a portal's own applicant and topic labels into ours. A rule that is wrong for one source is wrong for all and is
  fixed there; a portal label is added to the table once, not per connector.
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

## Current state (2026-10-28)

Connectors: `grants_gov`, `sam_assistance_listings`, `md_dhcd`, `md_commerce`, `md_mht` (Drupal base), `md_mea`,
`md_dnr` (SharePoint base, `connectors/maryland_sharepoint.py`), `pa_grants` (pa.gov Coveo index, 377 records), `wv_grants`
(grants.wv.gov JSON API, 124 records), `ca_grants` (data.ca.gov CSV, 2,025 records), `il_csfa` (Illinois CSFA list, 119 records). Milestones 1 to 8.2 and
9.1 to 9.4 shipped. **The live site answers 404: the
repository is private and GitHub Pages on a free account needs it public** (roadmap decision 2026-10-15); `gh-pages` holds
the build. GOCPP is blocked by its robots.txt (ask the office). Next per the census (`docs/surveys/state_portals.md`):
a `webgrants` storefront connector (IA, MT), then NJ and TX. See the roadmap.
