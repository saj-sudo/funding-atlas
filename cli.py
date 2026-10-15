"""funding-atlas CLI.  uv run python cli.py --help"""

from __future__ import annotations

from typing import Annotated

import typer

import db
from pipeline.diff import latest_run_id, render
from pipeline.run import CONNECTORS, run_connector

app = typer.Typer(no_args_is_help=True, add_completion=False)
DbOpt = Annotated[str, typer.Option("--db", help="SQLite file")]


@app.command("init-db")
def init_db(db_path: DbOpt = db.DEFAULT_DB) -> None:
    """Create the SQLite database and schema."""
    conn = db.connect(db_path)
    db.apply_schema(conn)
    typer.echo(f"{db_path}: schema version {db.schema_version(conn)}")


@app.command()
def run(
    connector: Annotated[str, typer.Argument(help=f"one of: {', '.join(CONNECTORS)}")],
    limit: Annotated[int | None, typer.Option(help="fetch at most N records; skips the missing-record check")] = None,
    db_path: DbOpt = db.DEFAULT_DB,
) -> None:
    """Fetch a connector, upsert, and print the diff."""
    if connector not in CONNECTORS:
        raise typer.BadParameter(f"unknown connector {connector!r}; choose from {', '.join(CONNECTORS)}")
    conn = db.connect(db_path)
    db.apply_schema(conn)
    run_id = run_connector(connector, conn, limit=limit)
    typer.echo(render(conn, run_id))


@app.command()
def diff(
    run_id: Annotated[int | None, typer.Option(help="defaults to the latest run")] = None,
    db_path: DbOpt = db.DEFAULT_DB,
) -> None:
    """Print the change report for a run."""
    conn = db.connect(db_path)
    rid = run_id if run_id is not None else latest_run_id(conn)
    if rid is None:
        typer.echo("No runs yet.")
        raise typer.Exit(1)
    typer.echo(render(conn, rid))


@app.command("open")
def open_programs(
    tier: Annotated[str, typer.Option(help="likely, possible, unlikely, or all (comma-separate to combine)")] = "likely",
    db_path: DbOpt = db.DEFAULT_DB,
) -> None:
    """List open and forecasted programs a municipality can apply for, best signal first."""
    conn = db.connect(db_path)
    db.apply_schema(conn)
    tiers = ["likely", "possible", "unlikely"] if tier == "all" else [t.strip() for t in tier.split(",")]
    rows = conn.execute(
        f"SELECT * FROM v_open_for_municipalities WHERE municipal_tier IN ({','.join('?' * len(tiers))})", tiers
    ).fetchall()
    typer.echo(f"{len(rows)} programs · tier {', '.join(tiers)}\n")
    typer.echo("| tier | name | agency | status | closes | max award | source |")
    typer.echo("|---|---|---|---|---|---|---|")
    for r in rows:
        name = r["name"].replace("|", "/")
        name = name if len(name) <= 70 else name[:69] + "…"
        amt = f"{r['amount_max']:,}" if r["amount_max"] is not None else ""
        typer.echo(f"| {r['municipal_tier']} | {name} | {r['agency_code']} | {r['status']} | {r['closes_at'] or ''} | {amt} | {r['source_url']} |")


if __name__ == "__main__":
    app()
