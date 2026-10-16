"""Build the navigator site: one page per state plus an index, from the navigator views (migration 0005).

  uv run python cli.py export                     # writes site/ from atlas.db
  uv run python scripts/build_site.py --out site

Each state page is one self-contained HTML file: the state's data as JSON in a <script type="application/json">
block, the stylesheet and script from web/ inlined, no external requests, so it works at a URL, as an email
attachment, and offline. Python here only queries SQL and shapes JSON; the page logic lives in web/app.js.

Nothing here reads a source or invents a value: a NULL in the database is null in the JSON and blank on the page.
The only derived fields are display rules about the registry's own metadata (is_new, is_updated, days_to_close),
and the rules are stated in the page footer.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402

WEB = Path(__file__).resolve().parents[1] / "web"
DEFAULT_OUT = Path("site")
SITE_URL = "https://saj-sudo.github.io/funding-atlas/"
REPO_URL = "https://github.com/saj-sudo/funding-atlas"

NEW_DAYS = 7           # first seen (after the source's first full read) within this many days -> "new"
UPDATED_DAYS = 7       # source changed within this many days -> "updated"
CLOSING_DAYS = 30      # closes within this many days -> "closing soon"
FEED_N = 200           # change-feed rows per state page: the newest N federal plus the newest N of that state
INDEX_FEED_N = 20      # change-feed rows on the index

CONNECTOR_LABEL = {
    "grants_gov": "Grants.gov",
    "sam_assistance_listings": "SAM.gov Assistance Listings",
    "md_dhcd": "Maryland DHCD",
    "md_commerce": "Maryland Commerce",
    "md_mht": "Maryland Historical Trust",
    "md_mea": "Maryland Energy Administration",
}
READER_QUESTIONS = (
    "What is open right now that is not on this page?",
    "Which rows should not be here, and why?",
    "Which columns do you actually use when deciding whether to apply? Which are noise?",
    "Where do you look for this today, and what does that source get right that this one does not?",
)

# (code, name, tile row, tile column): the 50 states and DC on the familiar tile-grid cartogram
# (11 columns, 8 rows). Rendered as a CSS grid on the index; no map asset needed.
STATES: tuple[tuple[str, str, int, int], ...] = (
    ("AK", "Alaska", 0, 0), ("ME", "Maine", 0, 10),
    ("VT", "Vermont", 1, 9), ("NH", "New Hampshire", 1, 10),
    ("WA", "Washington", 2, 0), ("ID", "Idaho", 2, 1), ("MT", "Montana", 2, 2), ("ND", "North Dakota", 2, 3),
    ("MN", "Minnesota", 2, 4), ("IL", "Illinois", 2, 5), ("WI", "Wisconsin", 2, 6), ("MI", "Michigan", 2, 7),
    ("NY", "New York", 2, 8), ("MA", "Massachusetts", 2, 9),
    ("OR", "Oregon", 3, 0), ("NV", "Nevada", 3, 1), ("WY", "Wyoming", 3, 2), ("SD", "South Dakota", 3, 3),
    ("IA", "Iowa", 3, 4), ("IN", "Indiana", 3, 5), ("OH", "Ohio", 3, 6), ("PA", "Pennsylvania", 3, 7),
    ("NJ", "New Jersey", 3, 8), ("CT", "Connecticut", 3, 9), ("RI", "Rhode Island", 3, 10),
    ("CA", "California", 4, 0), ("UT", "Utah", 4, 1), ("CO", "Colorado", 4, 2), ("NE", "Nebraska", 4, 3),
    ("MO", "Missouri", 4, 4), ("KY", "Kentucky", 4, 5), ("WV", "West Virginia", 4, 6), ("VA", "Virginia", 4, 7),
    ("MD", "Maryland", 4, 8), ("DE", "Delaware", 4, 9),
    ("AZ", "Arizona", 5, 1), ("NM", "New Mexico", 5, 2), ("KS", "Kansas", 5, 3), ("AR", "Arkansas", 5, 4),
    ("TN", "Tennessee", 5, 5), ("NC", "North Carolina", 5, 6), ("SC", "South Carolina", 5, 7),
    ("DC", "District of Columbia", 5, 8),
    ("OK", "Oklahoma", 6, 3), ("LA", "Louisiana", 6, 4), ("MS", "Mississippi", 6, 5), ("AL", "Alabama", 6, 6),
    ("GA", "Georgia", 6, 7),
    ("HI", "Hawaii", 7, 0), ("TX", "Texas", 7, 3), ("FL", "Florida", 7, 8),
)
STATE_NAME = {code: name for code, name, _, _ in STATES}


# ---------- data ----------

def runs(conn: sqlite3.Connection) -> dict[str, dict[str, str | None]]:
    """Per connector: first and last successful run (finished_at). The first one drives the 'new' rule."""
    return {
        r["connector"]: {"first_ok": r["first_ok"], "last_ok": r["last_ok"]}
        for r in conn.execute(
            "SELECT connector,"
            " MIN(CASE WHEN status = 'ok' THEN finished_at END) AS first_ok,"
            " MAX(CASE WHEN status = 'ok' THEN finished_at END) AS last_ok"
            " FROM run GROUP BY connector ORDER BY connector"
        )
    }


def load_programs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM v_navigator_program")]


def load_changes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM v_navigator_change")]


def load_coverage(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {r["state"]: dict(r) for r in conn.execute("SELECT * FROM v_navigator_coverage")}


def state_connectors(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Which connectors feed which jurisdiction ('US' or a state code), from the records themselves."""
    out: dict[str, list[str]] = {}
    for r in conn.execute(
        "SELECT DISTINCT CASE WHEN jurisdiction = 'US' THEN 'US' ELSE substr(jurisdiction, 1, 2) END AS j,"
        " source_connector FROM program ORDER BY 1, 2"
    ):
        out.setdefault(r["j"], []).append(r["source_connector"])
    return out


def excluded_unlikely(conn: sqlite3.Connection, state: str) -> int:
    """Open, municipality-eligible, not past deadline, federal or this state, but tier 'unlikely': the rows a
    state page leaves off. Counted so the exclusion is visible in the footer, not silent."""
    return conn.execute(
        "SELECT COUNT(*) FROM program p JOIN v_municipal_relevance r ON r.program_id = p.id"
        " WHERE p.status IN ('open', 'forecasted')"
        "   AND (p.closes_at IS NULL OR p.closes_at >= date('now'))"
        "   AND (p.jurisdiction = 'US' OR substr(p.jurisdiction, 1, 2) = ?)"
        "   AND r.municipal_tier = 'unlikely'"
        "   AND EXISTS (SELECT 1 FROM program_applicant_type a"
        "               WHERE a.program_id = p.id AND a.applicant_type = 'municipality')",
        (state,),
    ).fetchone()[0]


# ---------- shaping ----------

def split_list(value: str | None, sep: str = ", ") -> list[str]:
    return [v for v in (value or "").split(sep) if v]


def split_listings(value: str | None) -> list[dict[str, str]]:
    out = []
    for line in (value or "").split("\n"):
        if " · " in line:
            aln, name = line.split(" · ", 1)
            out.append({"aln": aln, "name": name})
    return out


def flag(value: int | None) -> bool | None:
    return None if value is None else bool(value)


def days_to(iso: str | None, today: date) -> int | None:
    return None if not iso else (date.fromisoformat(iso[:10]) - today).days


def shape_program(row: dict[str, Any], run_info: dict[str, dict[str, str | None]], today: date) -> dict[str, Any]:
    first_ok = (run_info.get(row["source_connector"]) or {}).get("first_ok")
    # 'new' means new to the registry after the source's first full read: on the first run everything is
    # 'added', and a page claiming 133 new programs on day one would be true and useless.
    is_new = (
        row["days_since_first_seen"] is not None
        and row["days_since_first_seen"] <= NEW_DAYS
        and bool(first_ok)
        and row["first_seen"] > first_ok
    )
    is_updated = (
        not is_new
        and row["days_since_changed"] is not None
        and row["days_since_changed"] <= UPDATED_DAYS
        and row["last_changed"] != row["first_seen"]
    )
    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "number": row["external_number"],
        "level": row["level"],
        "state": row["state"],
        "agency": row["administering_agency"],
        "agency_code": row["agency_code"],
        "connector": row["source_connector"],
        "funding_type": row["funding_type"],
        "funding_source": row["funding_source"],
        "status": row["status"],
        "opens_at": row["opens_at"],
        "closes_at": row["closes_at"],
        "closes_text": row["closes_at_text"],
        "rolling": flag(row["rolling"]),
        "amount_min": row["amount_min"],
        "amount_max": row["amount_max"],
        "match_required": flag(row["match_required"]),
        "match_pct": row["match_pct"],
        "summary": row["summary"],
        "eligibility": row["eligibility_text"],
        "applicant_types": split_list(row["applicant_types"]),
        "categories": split_list(row["categories"]),
        "alns": split_list(row["alns"]),
        "listings": split_listings(row["listings"]),
        "first_seen": row["first_seen"],
        "last_changed": row["last_changed"],
        "source_url": row["source_url"],
        "tier": row["municipal_tier"],
        "is_new": is_new,
        "is_updated": is_updated,
        "days_to_close": days_to(row["closes_at"], today),
    }


def shape_change(row: dict[str, Any], listed_ids: set[int]) -> dict[str, Any]:
    raw = json.loads(row["changed_fields"]) if row["changed_fields"] else {}
    fields = [{"field": k, "old": v.get("old"), "new": v.get("new")} for k, v in raw.items()]
    return {
        "id": row["change_id"],
        "at": row["changed_at"],
        "type": row["change_type"],
        "program_id": row["program_id"],
        "slug": row["slug"],
        "name": row["name"],
        "level": row["level"],
        "state": row["state"],
        "agency": row["administering_agency"],
        "connector": row["source_connector"],
        "status": row["status"],
        "closes_at": row["closes_at"],
        "source_url": row["source_url"],
        "tier": row["municipal_tier"],
        "fields": fields,
        "status_flip": "status" in raw,
        "listed": row["program_id"] in listed_ids,
    }


def sources_for(codes: list[str], run_info: dict[str, dict[str, str | None]]) -> list[dict[str, Any]]:
    return [
        {"connector": c, "label": CONNECTOR_LABEL.get(c, c), "last_ok": (run_info.get(c) or {}).get("last_ok")}
        for c in codes
    ]


def state_payload(
    code: str,
    *,
    programs: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    coverage: dict[str, dict[str, Any]],
    connectors: dict[str, list[str]],
    run_info: dict[str, dict[str, str | None]],
    excluded: int,
    generated_at: str,
) -> dict[str, Any]:
    rows = [p for p in programs if p["state"] is None or p["state"] == code]
    listed = {p["id"] for p in rows}
    # Newest N federal plus newest N state rows, merged: a day of 1,000 federal changes must not push the
    # state's own log off its page.
    fed = [c for c in changes if c["state"] is None][:FEED_N]
    own = [c for c in changes if c["state"] == code][:FEED_N]
    merged = sorted(fed + own, key=lambda c: (c["changed_at"], c["change_id"]), reverse=True)
    feed = [shape_change(c, listed) for c in merged]
    cov = coverage.get(code)
    federal_open = sum(1 for p in rows if p["state"] is None)
    return {
        "generated_at": generated_at,
        "site_url": SITE_URL,
        "repo_url": REPO_URL,
        "state": {"code": code, "name": STATE_NAME[code]},
        "states": [{"code": c, "name": n} for c, n, _, _ in STATES],
        "rules": {"new_days": NEW_DAYS, "updated_days": UPDATED_DAYS, "closing_days": CLOSING_DAYS, "feed_n": FEED_N},
        "coverage": {
            "federal": {
                "open": federal_open,
                "sources": sources_for(connectors.get("US", []), run_info),
            },
            "state": None if cov is None else {
                "agencies": cov["n_agencies"],
                "programs": cov["n_programs"],
                "open": cov["n_open_municipal"],
                "last_ok": cov["last_ok"],
                "sources": sources_for(connectors.get(code, []), run_info),
            },
        },
        "excluded_unlikely": excluded,
        "questions": list(READER_QUESTIONS),
        "programs": rows,
        "changes": feed,
    }


def index_payload(
    *,
    programs: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    coverage: dict[str, dict[str, Any]],
    connectors: dict[str, list[str]],
    run_info: dict[str, dict[str, str | None]],
    generated_at: str,
) -> dict[str, Any]:
    listed = {p["id"] for p in programs}
    states = []
    for code, name, row, col in STATES:
        cov = coverage.get(code)
        states.append({
            "code": code, "name": name, "row": row, "col": col,
            "agencies": cov["n_agencies"] if cov else 0,
            "programs": cov["n_programs"] if cov else 0,
            "open": cov["n_open_municipal"] if cov else 0,
            "last_ok": cov["last_ok"] if cov else None,
        })
    return {
        "generated_at": generated_at,
        "site_url": SITE_URL,
        "repo_url": REPO_URL,
        "rules": {"new_days": NEW_DAYS, "closing_days": CLOSING_DAYS},
        "federal": {
            "open": sum(1 for p in programs if p["state"] is None),
            "closing_soon": sum(
                1 for p in programs
                if p["state"] is None and p["days_to_close"] is not None and 0 <= p["days_to_close"] <= CLOSING_DAYS
            ),
            "new": sum(1 for p in programs if p["state"] is None and p["is_new"]),
            "sources": sources_for(connectors.get("US", []), run_info),
        },
        "states": states,
        "changes": [shape_change(c, listed) for c in changes[:INDEX_FEED_N]],
        "questions": list(READER_QUESTIONS),
    }


# ---------- rendering ----------

def embed_json(data: Any) -> str:
    """JSON safe inside a <script> block: '</' can never close the tag, U+2028/9 never break a parser."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def fill(template: str, **slots: str) -> str:
    for key, value in slots.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def render_state(data: dict[str, Any], css: str, js: str, template: str) -> str:
    name = data["state"]["name"]
    return fill(
        template,
        TITLE=f"{name}: open funding for local governments · Funding Atlas",
        DESCRIPTION=f"Federal and {name} public funding programs that are open or forecasted and name local governments as eligible, with what changed and what closes soon.",
        ROOT="../",
        CSS=css,
        JS=js,
        DATA=embed_json(data),
        GENERATED=data["generated_at"][:10],
    )


def render_index(data: dict[str, Any], css: str, js: str, template: str) -> str:
    return fill(
        template,
        TITLE="Funding Atlas: open public funding for local governments, by state",
        DESCRIPTION="A registry of federal and state funding programs open to towns, cities and counties, with change detection. Pick a state.",
        ROOT="",
        CSS=css,
        JS=js,
        DATA=embed_json(data),
        GENERATED=data["generated_at"][:10],
    )


def build(conn: sqlite3.Connection, *, generated_at: str | None = None) -> dict[str, Any]:
    """Everything the site needs, as data: {'index': {...}, 'states': {code: {...}}}."""
    generated_at = generated_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = date.fromisoformat(generated_at[:10])
    run_info = runs(conn)
    programs = [shape_program(r, run_info, today) for r in load_programs(conn)]
    changes = load_changes(conn)
    coverage = load_coverage(conn)
    connectors = state_connectors(conn)
    unknown = sorted({p["state"] for p in programs if p["state"] and p["state"] not in STATE_NAME})
    if unknown:
        typer.echo(f"warning: records with a jurisdiction that is not a state page: {', '.join(unknown)}", err=True)
    states = {
        code: state_payload(
            code, programs=programs, changes=changes, coverage=coverage, connectors=connectors,
            run_info=run_info, excluded=excluded_unlikely(conn, code), generated_at=generated_at,
        )
        for code, _, _, _ in STATES
    }
    index = index_payload(
        programs=programs, changes=changes, coverage=coverage, connectors=connectors,
        run_info=run_info, generated_at=generated_at,
    )
    return {"index": index, "states": states}


def write(conn: sqlite3.Connection, out: Path = DEFAULT_OUT, *, generated_at: str | None = None) -> tuple[Path, dict[str, int]]:
    """Build the site into `out` (wiped first). Returns (out, {state code: program rows})."""
    site = build(conn, generated_at=generated_at)
    css = (WEB / "app.css").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    state_tpl = (WEB / "state.html").read_text(encoding="utf-8")
    index_tpl = (WEB / "index.html").read_text(encoding="utf-8")

    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / ".nojekyll").write_text("")
    (out / "index.html").write_text(render_index(site["index"], css, js, index_tpl), encoding="utf-8")
    counts: dict[str, int] = {}
    for code, data in site["states"].items():
        d = out / code.lower()
        d.mkdir()
        (d / "index.html").write_text(render_state(data, css, js, state_tpl), encoding="utf-8")
        counts[code] = len(data["programs"])
    return out, counts


app = typer.Typer(add_completion=False)


@app.command()
def main(
    db_path: Annotated[str, typer.Option("--db", help="SQLite file")] = db.DEFAULT_DB,
    out: Annotated[Path, typer.Option(help="directory to write the site into (wiped first)")] = DEFAULT_OUT,
) -> None:
    conn = db.connect(db_path)
    db.apply_schema(conn)
    path, counts = write(conn, out)
    md_page = conn.execute("SELECT COUNT(*) FROM v_municipal_page").fetchone()[0]
    typer.echo(f"{path}: index + {len(counts)} state pages")
    typer.echo(f"  federal rows on every page: {counts.get('VA', 0)}")
    typer.echo(f"  MD: {counts.get('MD', 0)} rows (v_municipal_page: {md_page})")
    for code, n in counts.items():
        if n != counts.get("VA", 0) and code != "MD":
            typer.echo(f"  {code}: {n} rows")


if __name__ == "__main__":
    app()
