# funding-atlas

A jurisdiction-indexed registry of public funding programs (federal, state, county, city, utility), with open connectors and a change-detection pipeline. Two front ends will sit on it eventually: a municipal grant navigator and an individual benefits finder. This repo is the registry and the municipal navigator. Nothing individual-facing yet.

## Why this exists

- Grants.gov only lists direct federal awards. ~60% of state grant dollars are federal pass-throughs that only appear on state agency sites. No free national index of those exists.
- The Bloomberg/NLC Local Infrastructure Hub shut down March 2026. Lexipol GrantFinder is the paid incumbent and does not cover pass-through well.
- Maintenance is the moat and the trap (see DSIRE, Down Payment Resource). Design for change detection from day one, not re-crawls.

## Operator

Saj, solo, alongside a full-time data job. Expert SQL, learning Python. ADHD: keep the task surface small, one connector at a time, no sprawling abstractions before there are three real sources.

## v0.1 scope (Maryland only)

Ship a CLI + SQLite database + one read-only web page that answers: "I am a Maryland municipality. What is open right now that I can apply for, at the federal and state level?"

In scope:
1. Federal direct: Grants.gov `search2` + `fetchOpportunity` (no auth), filtered to eligibility codes for local governments. SAM.gov Assistance Listings as the stable program catalog underneath.
2. Maryland state: start with 3 agencies, verify each URL before building. Candidates: Governor's Grants Office (grants.maryland.gov), DHCD, MDOT, DNR, Maryland Energy Administration. Pick the 3 with the most structured listings.
3. Change detection: hash each normalized record; store first_seen, last_seen, last_changed; emit a diff on every run.
4. Status as a first-class field: open, forecasted, closed, paused, exhausted, unknown. A listing that doesn't know it's closed is worse than none.

Non-goals for v0.1: individuals, foundations, counties/cities, AI matching, auth, deployment. A markdown table or a single static HTML page is the UI.

## Schema (draft, argue with it)

program
- id, name, slug
- level: federal | state | county | city | utility
- jurisdiction: FIPS or state code + optional locality
- administering_agency
- applicant_types[]: municipality | county | state | tribe | nonprofit | business | household | individual | school | utility
- categories[]: infrastructure, housing, energy, water, transportation, broadband, public_safety, parks, health, workforce, other
- funding_type: grant | rebate | loan | tax_credit | forgivable_loan | formula | voucher
- funding_source: direct | pass_through (with parent_program_id if pass-through)
- amount_min, amount_max, match_required (pct or null)
- status, opens_at, closes_at, rolling (bool)
- eligibility_text (verbatim), eligibility_structured (json, nullable; leave null in v0.1)
- source_url, source_connector, record_hash, first_seen, last_seen, last_changed

Applicant types include household/individual now even though v0.1 ignores them. Retrofitting that later means re-crawling everything.

## Architecture

- Python 3.12, `uv` for env, SQLite via `sqlite3` (Postgres later), `httpx`, `pydantic` for the record model, `typer` for the CLI.
- `connectors/` : one module per source, each exposes `fetch() -> list[RawRecord]` and `normalize(raw) -> Program`. Keep them dumb. No shared base class until the third connector forces one.
- `pipeline/` : run connectors, normalize, hash, upsert, write diff.
- `db/` : schema.sql, migrations as numbered SQL files. SQL stays visible; this is Saj's strength.
- `tests/` : one fixture (saved HTML/JSON) per connector so tests never hit the network.
- `scripts/export_html.py` : dumps open programs to a single static page.

## How to work in this repo

- Plan before coding. For any new connector: show me the URL, a sample of the raw data, and the field mapping before writing the parser.
- One connector per session. Finish it, test it against its fixture, commit.
- Never invent program data. If a field isn't on the source page, it is null.
- When a source blocks scraping or has no structured listing, say so and stop; don't build a headless browser workaround without asking.
- Prefer SQL for anything analytical. Python is for fetching and shaping.
- Commit messages: `connector(md-dhcd): ...`, `pipeline: ...`, `schema: ...`.

## Milestones

1. Grants.gov connector + schema + diff output. (First session.)
2. SAM Assistance Listings connector; link opportunities to programs by ALN.
3. First Maryland agency connector.
4. Second and third MD connectors; now extract the shared base class.
5. Static HTML export; share with one person at a Maryland municipal league or COG and ask what's missing.
   - Page shipped (`scripts/export_html.py`, `v_municipal_page` in migration 0004, `cli.py export`). Decision
     taken: the `likely` tier still includes business programs that merely admit local governments (Advantage
     Maryland, the Alcohol Manufacturing Fund); the page handles that with tier, level, agency and text filters
     and `v_municipal_relevance` is unchanged. A "primary applicant" signal (local government named in the first
     applicant line, which needs the connectors to record line position) is deferred until the reader says the
     business rows bother them. Context: `docs/connectors/maryland_drupal.md`, "Applicant lines".
   - Next: send the file, collect answers to the four questions in its footer, then decide what milestone 6 is.

## Open questions (don't resolve in code yet)

- Who pays: state contract vs association license vs data feed. Decide after milestone 5.
- Rules-as-code partner for the individual side (PolicyEngine/OpenFisca). Not before the registry is proven.
- License: open data (ODbL?) for records, Apache-2.0 or MIT for code. Decide before any public push.
