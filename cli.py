"""funding-atlas CLI.  uv run python cli.py --help"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

import db
from pipeline.diff import latest_run_id, render
from pipeline.run import CONNECTORS, run_connector
from scripts import export_html

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


@app.command()
def aln(
    number: Annotated[str, typer.Argument(help="Assistance Listing Number, e.g. 97.106")],
    db_path: DbOpt = db.DEFAULT_DB,
) -> None:
    """Show one Assistance Listing and the opportunities that cite it."""
    conn = db.connect(db_path)
    db.apply_schema(conn)
    listing = conn.execute(
        "SELECT * FROM program WHERE source_connector = 'sam_assistance_listings' AND source_id = ?", (number,)
    ).fetchone()
    if listing is None:
        typer.echo(f"{number}: no listing stored (run `run sam_assistance_listings` first, or the number is not in SAM.gov)")
    else:
        types = [r[0] for r in conn.execute(
            "SELECT DISTINCT applicant_type FROM program_applicant_type WHERE program_id = ? ORDER BY 1", (listing["id"],))]
        amt = " to ".join(f"{listing[c]:,}" for c in ("amount_min", "amount_max") if listing[c] is not None)
        match = {None: "unknown", 0: "no", 1: "yes"}[listing["match_required"]]
        typer.echo(f"{number} · {listing['name']}")
        typer.echo(f"  agency: {listing['administering_agency'] or ''} ({listing['agency_code'] or ''})")
        typer.echo(f"  type: {listing['funding_type'] or ''} · award range: {amt or 'n/a'} · match required: {match}")
        typer.echo(f"  applicants: {', '.join(types) or 'n/a'}")
        typer.echo(f"  deadlines: {listing['closes_at_text'] or 'n/a'}")
        typer.echo(f"  {listing['source_url']}")
    rows = conn.execute(
        "SELECT * FROM v_opportunity_listing WHERE aln = ? ORDER BY opportunity_closes_at IS NULL, opportunity_closes_at",
        (number,),
    ).fetchall()
    typer.echo(f"\n{len(rows)} opportunities cite {number}")
    if rows:
        typer.echo("| name | status | closes | source |")
        typer.echo("|---|---|---|---|")
        for r in rows:
            name = r["opportunity_name"].replace("|", "/")
            name = name if len(name) <= 70 else name[:69] + "…"
            url = conn.execute("SELECT source_url FROM program WHERE id = ?", (r["opportunity_id"],)).fetchone()[0]
            typer.echo(f"| {name} | {r['opportunity_status']} | {r['opportunity_closes_at'] or ''} | {url} |")


@app.command()
def export(
    out: Annotated[Path, typer.Option(help="where to write the page")] = export_html.DEFAULT_OUT,
    db_path: DbOpt = db.DEFAULT_DB,
) -> None:
    """Write the open-programs page (v_municipal_page) as one self-contained HTML file."""
    conn = db.connect(db_path)
    db.apply_schema(conn)
    path, n = export_html.write(conn, out)
    typer.echo(f"{path}: {n} programs")


if __name__ == "__main__":
    app()
