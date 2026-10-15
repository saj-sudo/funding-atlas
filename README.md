# funding-atlas

A jurisdiction-indexed registry of public funding programs with change detection.
See [CLAUDE.md](CLAUDE.md) for scope, schema, and how to work in this repo.

```
uv sync
uv run python cli.py init-db
uv run python cli.py run grants_gov --limit 25
uv run python cli.py diff
```
