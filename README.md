# funding-atlas

A jurisdiction-indexed registry of public funding programs with change detection, and a navigator site on top.
What it is and the record model: [docs/SPEC.md](docs/SPEC.md). Plan and decisions: [docs/ROADMAP.md](docs/ROADMAP.md).
How to work in the repo: [CLAUDE.md](CLAUDE.md).

**Live site:** https://saj-sudo.github.io/funding-atlas/ (one page per state; Maryland is the one with state sources).

```
uv sync
uv run python cli.py init-db
uv run python cli.py run grants_gov --limit 25
uv run python cli.py run sam_assistance_listings --limit 25   # full run: ~2,900 listings, 15 to 30 min cold, ~3 requests warm
uv run python cli.py run md_dhcd                              # Maryland DHCD: ~200 page fetches, about 2 minutes
uv run python cli.py run md_commerce                          # Maryland Commerce: ~40 pages, under a minute
uv run python cli.py run md_mht                               # Maryland Historical Trust: ~35 pages, under a minute
uv run python cli.py diff
uv run python cli.py aln 97.106                               # one listing + the opportunities that cite it
uv run python cli.py export                                   # site/: the navigator (index + 51 state pages)
python -m http.server --directory site                        # then open http://localhost:8000/md/
sqlite3 atlas.db "SELECT * FROM v_aln_coverage;"              # how many opportunities resolve to a listing
sqlite3 atlas.db "SELECT * FROM v_navigator_program;"         # every state page as data
```

Connectors: `grants_gov` (federal notices), `sam_assistance_listings` (the program catalog underneath them,
joined by ALN through `v_opportunity_listing`), and three Maryland agencies on the state's Drupal platform:
`md_dhcd`, `md_commerce`, `md_mht`. They share `connectors/maryland_drupal.py` (sitemap enumeration, lastmod
refetch gate, page parsing, applicant tagging) and each keeps only its own status rules. Docs per connector and for
the shared base are in `docs/connectors/`.

## The site

`cli.py export` builds `site/` (gitignored) from three views in migration 0005: `v_navigator_program` (every open or
forecasted program a local government can apply to, any state), `v_navigator_change` (the change log) and
`v_navigator_coverage` (what was read per state). Each state page is one self-contained HTML file with its data
embedded as JSON and no external requests, so `site/md/index.html` also works as an email attachment or offline.
The page markup, stylesheet and script live in `web/`; `scripts/build_site.py` only queries SQL and fills them in.

Hosting is GitHub Pages from the `gh-pages` branch. `.github/workflows/site.yml` runs daily: it restores `atlas.db`
from `gh-pages`, runs every connector (a failing source is logged, not fatal), rebuilds the site, and force-pushes
`site/` plus a vacuumed, gzipped copy of the database as a single orphan commit. A push to `main` rebuilds from the stored
database without touching the sources. Nothing generated is committed to `main`. One-time setup: in the repository's
Settings, Pages, set the source to "Deploy from a branch", branch `gh-pages`, folder `/ (root)`.

The database behind the live site is downloadable at `/atlas.db.gz` on the site (SQLite; about 84 MB unpacked today, most of it the raw payloads that let warm runs skip unchanged records).

## Licenses

Code: MIT ([LICENSE](LICENSE)). Records and exports: Open Database License ([LICENSE-DATA](LICENSE-DATA)).
