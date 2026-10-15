"""Dump the open programs a Maryland municipality can apply for to one self-contained HTML page.

  uv run python cli.py export                     # writes export/maryland-municipal.html from atlas.db
  uv run python scripts/export_html.py --out x.html

The page is v_municipal_page (db/migrations/0004_municipal_page.sql) rendered row by row: the likely and
possible tiers, likely shown by default, filters in plain JavaScript, no external assets so the file works as an
email attachment opened offline. Nothing here reads a source or invents a value: a field that is NULL in the
database is blank on the page.
"""

from __future__ import annotations

import html
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402

DEFAULT_OUT = Path("export") / "maryland-municipal.html"
NEW_DAYS = 14                      # first seen within this many days -> "new"; changed within -> "updated"
TIERS = ("likely", "possible")     # what v_municipal_page holds, in display order
TIER_LABEL = {"likely": "Likely", "possible": "Possible"}
CONNECTOR_LABEL = {
    "grants_gov": "Grants.gov (federal notices)",
    "sam_assistance_listings": "SAM.gov Assistance Listings (federal program catalog)",
    "md_dhcd": "Maryland DHCD",
    "md_commerce": "Maryland Commerce",
    "md_mht": "Maryland Historical Trust",
}
READER_QUESTIONS = (
    "What is open right now that is not on this page?",
    "Which rows should not be here, and why?",
    "Which columns do you actually use when deciding whether to apply? Which are noise?",
    "Where do you look for this today, and what does that source get right that this one does not?",
)


# ---------- data ----------

def load(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM v_municipal_page")]


def freshness(conn: sqlite3.Connection) -> list[tuple[str, str | None]]:
    """(connector, finished_at of its last successful run), every connector that has ever run."""
    return [
        (r["connector"], r["last_ok"])
        for r in conn.execute(
            "SELECT connector, MAX(CASE WHEN status = 'ok' THEN finished_at END) AS last_ok"
            " FROM run GROUP BY connector ORDER BY connector"
        )
    ]


def excluded_unlikely(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM v_open_for_municipalities WHERE municipal_tier = 'unlikely'"
    ).fetchone()[0]


# ---------- rendering ----------

def e(value: Any) -> str:
    """Escape for HTML text and attribute values. None renders empty."""
    return "" if value is None else html.escape(str(value), quote=True)


def money(value: int | None) -> str:
    return "" if value is None else f"${value:,}"


def closes(row: dict[str, Any]) -> str:
    parts = []
    if row["closes_at"]:
        parts.append(f"<b>{e(row['closes_at'])}</b>")
    elif row["closes_at_text"]:
        parts.append(e(row["closes_at_text"]))
    if row["rolling"]:
        parts.append('<span class="tag">rolling</span>')
    if row["closes_at"] and row["closes_at_text"]:
        parts.append(f'<div class="muted small">{e(row["closes_at_text"])}</div>')
    return " ".join(parts)


def badge(row: dict[str, Any]) -> str:
    if row["days_since_first_seen"] is not None and row["days_since_first_seen"] <= NEW_DAYS:
        return '<span class="badge new">new</span>'
    if row["days_since_changed"] is not None and row["days_since_changed"] <= NEW_DAYS:
        return '<span class="badge upd">updated</span>'
    return ""


def detail(row: dict[str, Any]) -> str:
    def field(label: str, value: str | None, pre: bool = False) -> str:
        if not value:
            return ""
        body = f'<pre class="verbatim">{e(value)}</pre>' if pre else f"<p>{e(value)}</p>"
        return f'<div class="field"><div class="label">{label}</div>{body}</div>'

    seen = f"first seen {e(row['first_seen'][:10])}"
    if row["last_changed"] and row["last_changed"][:10] != row["first_seen"][:10]:
        seen += f" · last changed {e(row['last_changed'][:10])}"
    return (
        '<details><summary>details</summary><div class="detail">'
        + field("Summary", row["summary"])
        + field("Eligibility, as written by the source", row["eligibility_text"], pre=True)
        + field("Who can apply (tags)", row["applicant_types"])
        + field("Categories", row["categories"])
        + field("Assistance Listings this notice cites", row["listings"], pre=True)
        + (field("Opens", row["opens_at"]) if row["opens_at"] else "")
        + f'<div class="field muted small">{seen} · <a href="{e(row["source_url"])}">source</a></div>'
        + "</div></details>"
    )


def table_row(row: dict[str, Any]) -> str:
    match = {None: "", 0: "no", 1: "yes"}.get(row["match_required"], "")
    search = " ".join(filter(None, (row["name"], row["administering_agency"], row["agency_code"], row["summary"])))
    return (
        f'<tr data-tier="{e(row["municipal_tier"])}" data-level="{e(row["level"])}" data-status="{e(row["status"])}"'
        f' data-agency="{e(row["administering_agency"] or row["agency_code"] or "")}"'
        f' data-search="{e(search.lower())}">'
        f'<td class="tier"><span class="tier-{e(row["municipal_tier"])}">{e(TIER_LABEL.get(row["municipal_tier"], row["municipal_tier"]))}</span></td>'
        f'<td class="name"><a href="{e(row["source_url"])}">{e(row["name"])}</a> {badge(row)}{detail(row)}</td>'
        f'<td>{e(row["administering_agency"] or row["agency_code"])}<div class="muted small">{e(row["level"])}</div></td>'
        f'<td>{e((row["funding_type"] or "").replace("_", " "))}</td>'
        f'<td>{e(row["status"])}</td>'
        f'<td class="closes">{closes(row)}</td>'
        f'<td class="num">{money(row["amount_max"])}</td>'
        f'<td>{match}</td>'
        "</tr>"
    )


def render(
    rows: list[dict[str, Any]],
    *,
    generated_at: str,
    freshness: list[tuple[str, str | None]],
    excluded_unlikely: int,
) -> str:
    agencies = sorted({r["administering_agency"] or r["agency_code"] or "" for r in rows} - {""})
    by_tier = {t: sum(1 for r in rows if r["municipal_tier"] == t) for t in TIERS}
    fresh_lines = "".join(
        f"<li>{e(CONNECTOR_LABEL.get(c, c))}: "
        + (f"last successful run {e(when[:10])}" if when else "no successful run yet")
        + "</li>"
        for c, when in freshness
    ) or "<li>No runs recorded.</li>"
    questions = "".join(f"<li>{e(q)}</li>" for q in READER_QUESTIONS)
    body_rows = "".join(table_row(r) for r in rows)
    agency_opts = "".join(f'<option value="{e(a)}">{e(a)}</option>' for a in agencies)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Open funding for Maryland municipalities</title>
<style>
:root {{ --ink:#1b1b1b; --muted:#5c5c5c; --line:#d9d9d9; --bg:#fff; --soft:#f3f4f6; --likely:#1a6b3a; --possible:#8a5a00; --new:#0b5fa5; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:16px; font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; color:var(--ink); background:var(--bg); }}
h1 {{ font-size:1.5rem; margin:0 0 4px; }}
h2 {{ font-size:1.1rem; margin:24px 0 8px; }}
.muted {{ color:var(--muted); }}
.small {{ font-size:.85em; }}
header ul {{ margin:6px 0 0; padding-left:18px; }}
.filters {{ display:flex; flex-wrap:wrap; gap:10px 18px; align-items:center; padding:12px; margin:16px 0 8px; background:var(--soft); border-radius:6px; }}
.filters label {{ white-space:nowrap; }}
.filters input[type=search] {{ padding:6px 8px; border:1px solid var(--line); border-radius:4px; min-width:220px; }}
.filters select {{ padding:6px 8px; border:1px solid var(--line); border-radius:4px; max-width:280px; }}
.count {{ margin-left:auto; font-weight:600; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ text-align:left; vertical-align:top; padding:8px 6px; border-bottom:1px solid var(--line); }}
th {{ position:sticky; top:0; background:var(--bg); font-size:.85em; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); }}
td.num {{ text-align:right; white-space:nowrap; }}
td.name {{ min-width:260px; }}
td.closes {{ min-width:140px; }}
tr[hidden] {{ display:none; }}
.tier-likely {{ color:var(--likely); font-weight:600; }}
.tier-possible {{ color:var(--possible); font-weight:600; }}
.badge {{ display:inline-block; font-size:.7em; font-weight:700; text-transform:uppercase; padding:1px 6px; border-radius:3px; color:#fff; vertical-align:middle; }}
.badge.new {{ background:var(--new); }}
.badge.upd {{ background:var(--muted); }}
.tag {{ display:inline-block; font-size:.8em; padding:0 6px; border:1px solid var(--line); border-radius:10px; color:var(--muted); }}
details {{ margin-top:4px; }}
summary {{ cursor:pointer; color:var(--muted); font-size:.85em; }}
.detail {{ margin:8px 0 4px; padding:10px; background:var(--soft); border-radius:6px; max-width:70ch; }}
.field {{ margin-bottom:10px; }}
.field p {{ margin:2px 0 0; }}
.label {{ font-size:.8em; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); }}
pre.verbatim {{ white-space:pre-wrap; font:inherit; margin:2px 0 0; }}
footer {{ margin-top:32px; padding-top:16px; border-top:1px solid var(--line); max-width:80ch; }}
footer ol, footer ul {{ padding-left:20px; }}
@media (max-width: 720px) {{
  body {{ padding:12px; }}
  table, thead, tbody, tr, td {{ display:block; }}
  thead {{ display:none; }}
  tr {{ padding:8px 0; border-bottom:2px solid var(--line); }}
  td {{ border:0; padding:2px 0; }}
  td.num {{ text-align:left; }}
  td[data-h]::before {{ content:attr(data-h) ": "; color:var(--muted); font-size:.85em; }}
  .count {{ margin-left:0; }}
}}
</style>
</head>
<body>
<header>
  <h1>Open funding for Maryland municipalities</h1>
  <div class="muted">Federal and Maryland state programs that are open or forecasted and name local governments as eligible. Generated {e(generated_at[:10])}.</div>
  <ul class="small muted">{fresh_lines}</ul>
</header>

<div class="filters" id="filters">
  <span><b>Tier</b>
    <label><input type="checkbox" name="tier" value="likely" checked> Likely ({by_tier['likely']})</label>
    <label><input type="checkbox" name="tier" value="possible"> Possible ({by_tier['possible']})</label>
  </span>
  <span><b>Level</b>
    <label><input type="checkbox" name="level" value="federal" checked> Federal</label>
    <label><input type="checkbox" name="level" value="state" checked> State</label>
  </span>
  <span><b>Status</b>
    <label><input type="checkbox" name="status" value="open" checked> Open</label>
    <label><input type="checkbox" name="status" value="forecasted" checked> Forecasted</label>
  </span>
  <select name="agency"><option value="">Any agency</option>{agency_opts}</select>
  <input type="search" name="q" placeholder="Search name, agency, summary">
  <span class="count" id="count"></span>
</div>

<table id="programs">
<thead><tr><th>Tier</th><th>Program</th><th>Agency</th><th>Type</th><th>Status</th><th>Closes</th><th>Max award</th><th>Match</th></tr></thead>
<tbody>{body_rows}</tbody>
</table>

<footer>
  <h2>About this page</h2>
  <p>This is a registry export, not advice. Each row is one program page or federal notice read by a connector; the status and
  dates are what that source said on the run date above. Programs that only list a month ("Application opens: February") keep that
  wording in the Closes column rather than a guessed date. Blank cells mean the source did not state the value.</p>
  <p><b>Tier</b> is a rule-based reading of the record, not program data: <i>likely</i> means the source text names local
  governments or the notice carries a municipal category and a targeted eligibility list; <i>possible</i> means local governments
  are eligible but the signal is weaker. {excluded_unlikely} further open records that list local governments as eligible are left
  off this page as unlikely (research notices, requests for information, foreign-facing programs).</p>
  <p><b>new</b> marks a record first seen within the last {NEW_DAYS} days; <b>updated</b> marks one whose source changed in that window.</p>
  <h2>What I would like to know from you</h2>
  <ol>{questions}</ol>
</footer>

<script>
(function () {{
  var form = document.getElementById('filters');
  var rows = Array.prototype.slice.call(document.querySelectorAll('#programs tbody tr'));
  var count = document.getElementById('count');
  var heads = Array.prototype.map.call(document.querySelectorAll('#programs thead th'), function (th) {{ return th.textContent; }});
  rows.forEach(function (tr) {{
    Array.prototype.forEach.call(tr.children, function (td, i) {{ td.setAttribute('data-h', heads[i]); }});
  }});
  function checked(name) {{
    return Array.prototype.map.call(form.querySelectorAll('input[name=' + name + ']:checked'), function (i) {{ return i.value; }});
  }}
  function apply() {{
    var tiers = checked('tier'), levels = checked('level'), statuses = checked('status');
    var agency = form.querySelector('select[name=agency]').value;
    var q = form.querySelector('input[name=q]').value.trim().toLowerCase();
    var shown = 0;
    rows.forEach(function (tr) {{
      var ok = tiers.indexOf(tr.dataset.tier) >= 0
            && levels.indexOf(tr.dataset.level) >= 0
            && statuses.indexOf(tr.dataset.status) >= 0
            && (!agency || tr.dataset.agency === agency)
            && (!q || tr.dataset.search.indexOf(q) >= 0);
      tr.hidden = !ok;
      if (ok) shown++;
    }});
    count.textContent = 'showing ' + shown + ' of ' + rows.length;
  }}
  form.addEventListener('change', apply);
  form.addEventListener('input', apply);
  apply();
}})();
</script>
</body>
</html>
"""


def write(conn: sqlite3.Connection, out: Path = DEFAULT_OUT) -> tuple[Path, int]:
    """Render the page from the connection and write it. Returns (path, row count)."""
    rows = load(conn)
    page = render(
        rows,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        freshness=freshness(conn),
        excluded_unlikely=excluded_unlikely(conn),
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out, len(rows)


app = typer.Typer(add_completion=False)


@app.command()
def main(
    db_path: Annotated[str, typer.Option("--db", help="SQLite file")] = db.DEFAULT_DB,
    out: Annotated[Path, typer.Option(help="where to write the page")] = DEFAULT_OUT,
) -> None:
    conn = db.connect(db_path)
    db.apply_schema(conn)
    path, n = write(conn, out)
    typer.echo(f"{path}: {n} programs")


if __name__ == "__main__":
    app()
