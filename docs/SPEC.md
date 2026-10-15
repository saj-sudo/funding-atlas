# funding-atlas: product spec

Living document. Operating rules for working in the repo are in `CLAUDE.md`; the plan and decisions log are in
`ROADMAP.md`. This file says what the thing is, who it is for, and what a record means.

## What it is

A jurisdiction-indexed registry of public funding programs (federal, state, and later county, city and utility),
built from open connectors that read the sources directly, with change detection on every record. Two front ends sit
on the same records: a **municipal grant navigator** (this repo, in progress) and an **individual benefits finder**
(later, nothing individual-facing yet). The registry is the product; the navigator is how it is seen.

## Why it exists

- Grants.gov lists direct federal awards only. Roughly 60% of state grant dollars are federal pass-throughs that
  appear only on state agency sites. No free national index of those exists.
- The Bloomberg/NLC Local Infrastructure Hub shut down in March 2026. Lexipol GrantFinder is the paid incumbent and
  does not cover pass-through well.
- Maintenance is the moat and the trap (DSIRE, Down Payment Resource). Every design choice favours change detection
  over re-crawls, and honest nulls over inferred values.

## What it does that a person cannot

A town administrator can open fifteen agency sites by hand. The registry earns its place by doing four things across
all of them at once:

1. **Change since you last looked.** Every record is hashed; `first_seen`, `last_changed` and the `program_change`
   log say what is new, what moved, and what disappeared. Nobody re-reads 150 pages a week to find the three that
   changed.
2. **Status truth with a date.** Open, forecasted, closed, paused, exhausted, or unknown, as the source said it on the
   run date. Source pages often say "posted" years after the deadline; the registry does not.
3. **Deadlines in one list.** Federal notices and state pass-through rounds sorted by close date, with the verbatim
   timeline wording kept when the source gives a month and no year.
4. **Eligibility filtered to local governments**, with the reasoning auditable in SQL (the relevance tiers).

The navigator UI should lead with 1 and 3. A plain table shows only 4.

## Users

- **Town administrator or clerk with no grants staff.** Needs: what is open, when it closes, am I eligible, where do I
  apply. Reads on a phone between meetings.
- **COG or regional council planner.** Needs: everything their member towns could apply for this quarter, by
  category, to push out in a newsletter.
- **Grant consultant.** Needs: the change feed, to be first to a reopened round.

## Scope

**v0.1 (Maryland, shipped 2026-10-15):** CLI, SQLite, five connectors, relevance tiers, one static page.

**v0.2 (in progress):**
- A navigator UI that people want to use: state picker for all 50 states (federal rows everywhere, state coverage
  stated honestly per state), a landing view of new / closing soon / status changes, faceted filters, detail panel,
  change feed. Hosted on GitHub Pages, rebuilt on a schedule.
- Maryland depth: the big municipal funders (DNR, MDOT, MDE, MEA, GOCPP, MDEM) are not yet connected.
- Expansion beyond Maryland, platform-first: survey each state's central grants portal, build one connector per
  platform, treat a state as configuration. Mid-Atlantic first.

**Non-goals, still in force:** individuals, foundations, AI matching, auth. Deployment is no longer a non-goal.

## Record model

The schema as it is in `db/schema.sql` (not the original draft; the draft drifted and this is the truth).

`program`, one row per source record:

| Column | Notes |
|---|---|
| `source_connector`, `source_id`, `source_url` | identity; `(source_connector, source_id)` is unique |
| `external_number` | e.g. the Grants.gov opportunity number |
| `name`, `slug` | slug is `slugify(name)[:80]-connector-source_id` |
| `level` | `federal`, `state`, `county`, `city`, `utility` |
| `jurisdiction` | `US`, a state code, or `MD:Baltimore` style |
| `administering_agency`, `agency_code` | agency name and the source's code for it |
| `funding_type` | `grant`, `cooperative_agreement`, `rebate`, `loan`, `tax_credit`, `forgivable_loan`, `formula`, `voucher`, `other` |
| `funding_source`, `parent_program_id` | `direct` or `pass_through`; parent reserved for pass-through lineage |
| `amount_min`, `amount_max`, `match_required`, `match_pct` | whole dollars; match NULL means unknown |
| `status` | see Status semantics |
| `opens_at`, `closes_at`, `closes_at_text`, `rolling` | ISO dates; verbatim deadline wording when no date; rolling NULL means unknown |
| `summary`, `eligibility_text`, `eligibility_structured` | description, verbatim eligibility, JSON (NULL in v0.x) |
| `record_hash`, `first_seen`, `last_seen`, `last_changed` | change detection |

Junction tables: `program_applicant_type` (13 values: municipality, county, state, tribe, special_district, school,
higher_ed, housing_authority, nonprofit, business, household, individual, utility; `source_code` keeps the raw code
or matched phrase), `program_category` (11 values: infrastructure, housing, energy, water, transportation, broadband,
public_safety, parks, health, workforce, other), `program_aln` (Assistance Listing Numbers, the join key to the
SAM.gov catalog).

Operational tables: `raw_record` (latest raw payload per source record, so a connector can skip what has not
moved), `run` (one row per connector run with counts), `program_change` (added / changed / missing, with the
field-level diff as JSON).

Drift from the original draft, so nobody re-argues it: `funding_type` gained `cooperative_agreement` and `other`;
applicant types went from 10 to 13; `closes_at_text`, `summary`, `agency_code` and `external_number` were added;
household and individual are tagged now even though no front end uses them, because retrofitting means re-crawling.

## Status semantics

`open`, `forecasted`, `closed`, `paused`, `exhausted`, `unknown`. A record's status is what its source said on the
run date, mapped by that connector's documented rules. When the source does not say, the status is `unknown`, never
inferred from a calendar (MHT's "Application opens: February" is kept as text, not turned into a date). A record that
vanishes from its source is re-resolved by the connector; if the page cannot be read it becomes `unknown`. The open
views drop records whose `closes_at` is in the past even if the source still says posted.

## Relevance tiers

`v_municipal_relevance` (migration 0002) grades every record `likely`, `possible` or `unlikely` for a municipality
with named boolean rules: local-government wording in the text, municipal category on a targeted notice, breadth of
the eligibility list, research-notice markers, foreign-facing agencies, requests for information. Known weakness:
`likely` includes business programs that merely admit local governments (Advantage Maryland). A "primary applicant"
signal (local government named in the first applicant line) is the fix and needs the connectors to record line
position; deferred until a reader says the business rows bother them.

## Views

| View | Migration | Purpose |
|---|---|---|
| `v_municipal_relevance` | 0002 | the tier and every rule behind it, per program |
| `v_open_for_municipalities` | 0002 | open or forecasted, municipality eligible, US or MD, not past deadline |
| `v_opportunity_listing` | 0003 | federal notices joined to SAM.gov listings by ALN |
| `v_aln_coverage` | 0003 | how many notices resolve to a listing, per connector |
| `v_municipal_page` | 0004 | the static page as data: likely + possible, with text columns and flattened tags |

## Connector contract

Each connector module exposes `fetch(limit, prior)`, `normalize(raw)` and `resolve_missing(source_id)`, is
registered in `pipeline/run.py`, has a fixture directory under `tests/fixtures/` and a doc under `docs/connectors/`
written before the parser (URL, raw sample, field mapping, decisions, expected result). Change signals used so far:
`lastmod` in a sitemap plus `og:updated_time` (Maryland Drupal), the record hash itself (everything). The three
Maryland agencies share `connectors/maryland_drupal.py`; the platform-first expansion plan assumes the same shape, one
base per platform with per-state configuration.

## Licensing

Decided 2026-10-15: MIT for the code, ODbL for the records. Verbatim eligibility text is public government text and is
republished as such with the source URL on every row. LICENSE files land with the hosting session.
