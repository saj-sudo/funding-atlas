# funding-atlas

A jurisdiction-indexed registry of public funding programs with change detection.
See [CLAUDE.md](CLAUDE.md) for scope, schema, and how to work in this repo.

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
sqlite3 atlas.db "SELECT * FROM v_aln_coverage;"              # how many opportunities resolve to a listing
```

Connectors: `grants_gov` (federal notices), `sam_assistance_listings` (the program catalog underneath them,
joined by ALN through `v_opportunity_listing`), and three Maryland agencies on the state's Drupal platform:
`md_dhcd`, `md_commerce`, `md_mht`. They share `connectors/maryland_drupal.py` (sitemap enumeration, lastmod
refetch gate, page parsing, applicant tagging) and each keeps only its own status rules. Docs per connector and for
the shared base are in `docs/connectors/`.
