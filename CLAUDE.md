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
  `connectors/maryland_drupal.py`; a second platform base is extracted only when a second state on the same platform
  forces it.
- `pipeline/`: run a connector, normalize, hash, upsert, log changes, write the diff.
- `db/`: `schema.sql` plus numbered migrations. Views carry the analytical logic; SQL stays visible.
- `tests/`: fixtures per connector, never the network. CI runs `ruff check .` and `pytest -q`.
- `scripts/export_html.py` (`cli.py export`): renders `v_municipal_page` to `export/maryland-municipal.html`.

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

## Current state (2026-10-15)

Connectors: `grants_gov`, `sam_assistance_listings`, `md_dhcd`, `md_commerce`, `md_mht`. Milestones 1 to 5 shipped.
Next up, each its own session: navigator UI and hosting, Maryland depth, Mid-Atlantic portal survey. See the roadmap.
