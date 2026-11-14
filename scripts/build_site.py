"""Build the navigator site: one page per state plus an index, from the navigator views (migrations 0005 and 0006).

  uv run python cli.py export                     # writes site/ from atlas.db
  uv run python scripts/build_site.py --out site

Each state page is one self-contained HTML file: the state's data as JSON in a <script type="application/json">
block, the stylesheet and script from web/ inlined, no external requests, so it works at a URL, as an email
attachment, and offline. Python here only queries SQL and shapes JSON; the page logic lives in web/app.js.

Nothing here reads a source or invents a value: a NULL in the database is null in the JSON and blank on the page.
The only derived fields are display rules about the registry's own metadata (is_new, is_updated, days_to_close),
and the rules are stated in the page footer.

Beside every page sits its change log as a feed: `feed.xml` (Atom) and `changes.json`, the same rows the page's
Changes tab shows (the newest FEED_N federal plus the newest FEED_N of that state), and at the site root the newest
FEED_N across every source. An entry's id is a tag URI over the change-log row id, so it never changes; its summary
is the same wording web/app.js renders (FIELD_LABEL is kept in both places and a test holds them equal).
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

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
BETWEEN_MONTHS = 15    # mirrors v_navigator_between (migration 0006): last deadline within this many months
ATOM_NS = "http://www.w3.org/2005/Atom"
FEED_ID_PREFIX = "tag:saj-sudo.github.io,2026:funding-atlas/change/"   # a permanent id per change-log row
FEED_TITLE = "Funding Atlas: changes"
PLACEHOLDER_YEARS = 5  # a close date this far out is a portal's way of saying "no deadline" (pa.gov uses 2035-12-31 and 2999-07-01)

CONNECTOR_LABEL = {
    "grants_gov": "Grants.gov",
    "sam_assistance_listings": "SAM.gov Assistance Listings",
    "md_dhcd": "Maryland DHCD",
    "md_commerce": "Maryland Commerce",
    "md_mht": "Maryland Historical Trust",
    "md_mea": "Maryland Energy Administration",
    "md_dnr": "Maryland DNR",
    "md_mdem": "Maryland Department of Emergency Management",
    "md_mdot": "Maryland Department of Transportation",
    "md_mde": "Maryland Department of the Environment (MWIFA)",
    "pa_grants": "Pennsylvania grants portal (pa.gov)",
    "wv_grants": "West Virginia grants portal (grants.wv.gov)",
    "ca_grants": "California Grants Portal (grants.ca.gov)",
    "il_csfa": "Illinois Catalog of State Financial Assistance (GATA)",
    "webgrants": "WebGrants storefronts (Iowa, Montana)",
    "tx_egrants": "Texas Office of the Governor eGrants",
    "nj_dca_sage": "New Jersey DCA SAGE (public RFP list)",
    "ny_sfs": "New York SFS Grant Opportunity Portal",
    "va_dcjs": "Virginia Department of Criminal Justice Services",
    "va_dhcd": "Virginia Department of Housing and Community Development",
    "va_dcr": "Virginia Department of Conservation and Recreation",
    "va_vdot": "Virginia Department of Transportation (Local Assistance)",
    "de_dnrec": "Delaware DNREC Environmental Finance",
    "de_dema": "Delaware Emergency Management Agency",
    "de_deldot": "Delaware DelDOT (TAP and Safe Routes to School)",
    "de_dsha": "Delaware State Housing Authority (Housing Delaware)",
    "ma_onestop": "Community One Stop for Growth (EOED, EOHLC, MassDevelopment)",
    "or_biz": "Business Oregon",
    "nc_grants": "nc.gov Grant Opportunities (directory)",
    "wa_fund_directory": "Washington Fund Directory (State Treasurer, directory)",
    "ky_dlg": "Kentucky DLG Portal (Office of State Grants)",
    "vt_accd": "Vermont ACCD (Housing and Community Development)",
    "vt_vtrans": "Vermont Agency of Transportation (Municipal Assistance)",
    "vt_fpr": "Vermont Forests, Parks and Recreation",
    "vt_vem": "Vermont Emergency Management",
    "ct_doh": "Connecticut Department of Housing",
    "ct_dot": "Connecticut Department of Transportation",
    "ct_deep": "Connecticut DEEP (Open Space)",
    "ct_demhs": "Connecticut DEMHS (Emergency Management)",
    "nd_commerce": "North Dakota Commerce (Community Development and Rural Prosperity)",
    "nd_dot": "North Dakota Department of Transportation",
    "nd_des": "North Dakota Department of Emergency Services",
    "nd_parks": "North Dakota Parks and Recreation",
    "ky_dlgfed": "Kentucky Department for Local Government (federal grants)",
    "ky_tc": "Kentucky Transportation Cabinet (Office of Local Programs)",
    "ky_eec": "Kentucky Energy and Environment Cabinet",
    "ky_kia": "Kentucky Infrastructure Authority",
    "mo_ded": "Missouri DED (Community Development Block Grants)",
    "mo_dnr": "Missouri Department of Natural Resources",
    "mo_modot": "Missouri Department of Transportation (Local Public Agency programs)",
    "mo_sema": "Missouri State Emergency Management Agency",
    "mo_parks": "Missouri State Parks (grants)",
    "ne_ded": "Nebraska Department of Economic Development",
    "ne_dwee": "Nebraska Department of Water, Energy, and Environment",
    "ne_dot": "Nebraska Department of Transportation",
}
# What each connector reads, for the index map (13.13): a state portal with structured rows, a directory with no
# status, or agency pages. A connector missing here counts as agency pages.
CONNECTOR_KIND = {
    "pa_grants": "portal", "wv_grants": "portal", "ca_grants": "portal", "il_csfa": "portal", "webgrants": "portal",
    "tx_egrants": "portal", "nj_dca_sage": "portal", "ny_sfs": "portal", "ky_dlg": "portal",
    "nc_grants": "directory", "wa_fund_directory": "directory",
}
# States with no state source read, and why, in one plain sentence each. From docs/surveys/state_portals.md and
# the roadmap's decisions (12.0, 12.5); a state that gains a connector drops out of this table by itself.
STATE_NOTE: dict[str, tuple[str, str]] = {
    "AK": ("blocked", "Alaska's community grants pages refuse automated readers (a bot wall answers every request)."),
    "CO": ("blocked", "Colorado's local funding guide refuses automated readers."),
    "ID": ("blocked", "Idaho Commerce's grants pages sit behind a bot challenge."),
    "KS": ("blocked", "The Kansas Infrastructure Hub refuses automated readers."),
    "ME": ("blocked", "Maine's community funding finder refuses automated readers."),
    "MI": ("blocked", "Michigan's grants pages refuse automated readers."),
    "RI": ("blocked", "Rhode Island's funding opportunities page sits behind a bot challenge."),
    "OK": ("login", "Oklahoma's Grant Exchange is login only and asks crawlers not to read it."),
    "AZ": ("login", "Arizona's funding opportunities are in a login-only grants system."),
    "AL": ("blocked", "Alabama's grants office asks this registry's crawler not to read its pages; the registry respects that."),
    "UT": ("stopped", "Utah's grants list loads only in a browser script; reading it would need a headless browser, which this registry does not use."),
    "WY": ("stopped", "Wyoming's grants list loads only in a browser script; reading it would need a headless browser, which this registry does not use."),
    "GA": ("none", "No public state list of grants for local governments was found."),
    "HI": ("none", "No public state list of grants for local governments was found."),
    "LA": ("none", "No public state list of grants for local governments was found."),
    "MS": ("none", "No public state list of grants for local governments was found."),
    "OH": ("none", "Ohio's grants site answered nothing when surveyed."),
    "SC": ("none", "No public state list of grants for local governments was found."),
    "WI": ("none", "No public state list of grants for local governments was found."),
    "DC": ("none", "The District is out of scope for now: it has no towns or counties under it."),
}


def coverage_kind(code: str, connectors: dict[str, list[str]]) -> tuple[str, str | None]:
    """How a state is read, for the index map: portal, agencies, portal_agencies, directory, or a STATE_NOTE kind,
    else 'federal' (nothing built yet). Derived from the connectors that hold records for the state."""
    kinds = {CONNECTOR_KIND.get(c, "agencies") for c in connectors.get(code, [])}
    if "portal" in kinds and "agencies" in kinds:
        return "portal_agencies", None
    if "portal" in kinds:
        return "portal", None
    if "agencies" in kinds:
        return "agencies", None
    if "directory" in kinds:
        return "directory", None
    if code in STATE_NOTE:
        return STATE_NOTE[code]
    return "federal", None


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


def load_between(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """State programs a town could apply to that are closed or past their deadline: the page's appendix."""
    return [dict(r) for r in conn.execute("SELECT * FROM v_navigator_between")]


def load_unstated(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """State programs a town could apply to whose source states no status and no date (migration 0008)."""
    return [dict(r) for r in conn.execute("SELECT * FROM v_navigator_unstated")]


HISTORY_FIELDS = ("status", "closes_at", "opens_at")


def load_history(conn: sqlite3.Connection, ids: set[int]) -> dict[int, list[list[Any]]]:
    """Each listed program's own change log, compacted for the detail panel's history strip (13.7).

    One event per fact: [date, 'added'], [date, 'missing'], [date, field, old, new] for status, closes_at and
    opens_at, and [date, 'edit', n] for a change that touched only other fields (n of them). Oldest first.
    Nothing is inferred: these are the rows program_change holds, in their own order."""
    out: dict[int, list[list[Any]]] = {}
    if not ids:
        return out
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT program_id, changed_at, change_type, changed_fields FROM program_change "
        f"WHERE program_id IN ({marks}) ORDER BY changed_at, id",
        sorted(ids),
    )
    for pid, at, kind, fields in rows:
        day = at[:10]
        events = out.setdefault(pid, [])
        if kind in ("added", "missing"):
            events.append([day, kind])
            continue
        raw = json.loads(fields) if fields else {}
        hit = [f for f in HISTORY_FIELDS if f in raw]
        for f in hit:
            events.append([day, f, raw[f].get("old"), raw[f].get("new")])
        if not hit and raw:
            events.append([day, "edit", len(raw)])
    return out


def load_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """The three chart views of migration 0009, as plain rows."""
    months: dict[str, list[int]] = {}
    for r in conn.execute("SELECT state, month, n FROM v_stats_deadline_month"):
        months.setdefault(r["state"], [0] * 12)[r["month"] - 1] = r["n"]
    stated = [dict(r) for r in conn.execute("SELECT * FROM v_stats_stated ORDER BY n DESC, state")]
    flips = [dict(r) for r in conn.execute("SELECT * FROM v_stats_status_flips")]
    return {"months": months, "stated": stated, "flips": flips}


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


def is_placeholder(iso: str | None, today: date) -> bool:
    """True when a close date lies more than PLACEHOLDER_YEARS past today (see the constant)."""
    if not iso:
        return False
    try:
        return date.fromisoformat(iso[:10]) > today.replace(year=today.year + PLACEHOLDER_YEARS)
    except ValueError:
        return False

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
        # A stated date more than PLACEHOLDER_YEARS out is kept as the source states it but shown as "no deadline
        # stated": pa.gov writes 2035-12-31 and 2999-07-01 on recurring programs and loans.
        "deadline_placeholder": is_placeholder(row["closes_at"], today),
        # v_navigator_between and v_navigator_unstated only: days since the last stated deadline, and the last time the change log saw
        # the record flip to open or forecasted (null until observed; never computed from a calendar).
        "days_since_deadline": row.get("days_since_deadline"),
        "last_reopened": row.get("last_reopened"),
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


# ---------- the change feed (Atom + JSON), the same wording as web/app.js ----------

FIELD_LABEL = {
    "status": "status", "closes_at": "closes", "opens_at": "opens", "closes_at_text": "deadline wording",
    "amount_max": "max award", "amount_min": "min award", "match_required": "match required", "match_pct": "match %",
    "name": "name", "summary": "summary", "eligibility_text": "eligibility text", "funding_type": "funding type",
    "administering_agency": "agency", "applicant_types": "applicant tags", "categories": "categories",
    "alns": "listings cited", "rolling": "rolling", "source_url": "source URL", "external_number": "number",
}
LEAD_FIELDS = ("status", "closes_at", "amount_max", "opens_at")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def fmt_val(field: str, v: Any) -> str:
    if v is None or v == "":
        return "(blank)"
    if field in ("amount_max", "amount_min"):
        try:
            return f"${float(v):,.0f}"
        except (TypeError, ValueError):
            return str(v)
    if field in ("match_required", "rolling"):
        return "yes" if v else "no"
    if isinstance(v, list):
        return f"{len(v)} values"
    if isinstance(v, dict):
        return "changed"
    text = str(v)
    return text if len(text) <= 40 else text[:39] + "…"


def describe_change(c: dict[str, Any]) -> str:
    """One line of plain text per change: the port of describe() in web/app.js."""
    lead: list[str] = []
    rest: list[str] = []
    for f in c["fields"]:
        if f["field"] in LEAD_FIELDS:
            lead.append(f"{FIELD_LABEL[f['field']]} {fmt_val(f['field'], f['old'])} → {fmt_val(f['field'], f['new'])}")
        else:
            rest.append(FIELD_LABEL.get(f["field"], f["field"].replace("_", " ")))
    out = " · ".join(lead)
    if c["type"] == "added":
        out = "added to the registry" + (" · " + out if out else "")
    if c["type"] == "missing":
        out = "no longer listed by the source" + (" · " + out if out else "")
    if rest:
        out += (" · " if out else "") + ("also " if lead or c["type"] != "changed" else "") + ", ".join(rest)
    return out or "changed"


def feed_link(c: dict[str, Any], state: str | None) -> str:
    """The program on the state page it is listed on, else the source's own page."""
    page = state or c.get("state")
    if c.get("listed") and page:
        return f"{SITE_URL}{page.lower()}/#p={quote(c['slug'] or '')}"
    return c.get("source_url") or SITE_URL


def _who(c: dict[str, Any]) -> str:
    where = "federal" if c.get("level") == "federal" else (STATE_NAME.get(c.get("state") or "", c.get("state")) or c.get("level") or "")
    return f"{c.get('agency') or CONNECTOR_LABEL.get(c.get('connector'), c.get('connector'))} · {where}"


def _text(value: Any) -> str:
    return _CONTROL_RE.sub("", str(value if value is not None else ""))


def render_atom(entries: list[dict[str, Any]], *, state: str | None, self_url: str, alternate_url: str, updated: str,
                title: str | None = None) -> str:
    """An Atom feed of the change entries. Built with the standard library; the library escapes the text."""
    feed = ET.Element("feed", xmlns=ATOM_NS)
    where = f"{STATE_NAME[state]} and federal" if state else "every source"
    ET.SubElement(feed, "title").text = _text(title or f"{FEED_TITLE} ({where})")
    ET.SubElement(feed, "subtitle").text = "Programs a local government could apply to: added, changed or no longer listed, as read from each source."
    ET.SubElement(feed, "id").text = self_url
    ET.SubElement(feed, "updated").text = updated
    ET.SubElement(feed, "link", rel="self", href=self_url, type="application/atom+xml")
    ET.SubElement(feed, "link", rel="alternate", href=alternate_url, type="text/html")
    ET.SubElement(ET.SubElement(feed, "author"), "name").text = "Funding Atlas"
    for c in entries:
        e = ET.SubElement(feed, "entry")
        ET.SubElement(e, "id").text = f"{FEED_ID_PREFIX}{c['id']}"
        ET.SubElement(e, "title").text = _text(f"{c['type']}: {c['name']}")
        ET.SubElement(e, "updated").text = c["at"]
        ET.SubElement(e, "link", rel="alternate", href=feed_link(c, state), type="text/html")
        ET.SubElement(e, "category", term=c.get("state") or "federal")
        ET.SubElement(ET.SubElement(e, "author"), "name").text = _text(c.get("agency") or CONNECTOR_LABEL.get(c.get("connector"), c.get("connector")))
        ET.SubElement(e, "summary", type="text").text = _text(f"{describe_change(c)} · {_who(c)}")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(feed, encoding="unicode")


def changes_json(entries: list[dict[str, Any]], *, state: str | None, generated_at: str, base: str) -> str:
    """The same entries as JSON: {generated_at, site_url, state, feed, changes}."""
    return json.dumps({
        "generated_at": generated_at,
        "site_url": SITE_URL,
        "state": state,
        "feed": {"atom": base + "feed.xml", "json": base + "changes.json"},
        "changes": [{**c, "link": feed_link(c, state), "summary": describe_change(c)} for c in entries],
    }, ensure_ascii=False, separators=(",", ":"))


def sources_for(codes: list[str], run_info: dict[str, dict[str, str | None]]) -> list[dict[str, Any]]:
    return [
        {"connector": c, "label": CONNECTOR_LABEL.get(c, c), "last_ok": (run_info.get(c) or {}).get("last_ok")}
        for c in codes
    ]


def state_payload(
    code: str,
    *,
    programs: list[dict[str, Any]],
    between: list[dict[str, Any]],
    unstated: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    coverage: dict[str, dict[str, Any]],
    connectors: dict[str, list[str]],
    run_info: dict[str, dict[str, str | None]],
    excluded: int,
    generated_at: str,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [p for p in programs if p["state"] is None or p["state"] == code]
    between_rows = [p for p in between if p["state"] == code]          # state rows only, by construction
    unstated_rows = [p for p in unstated if p["state"] == code]        # state rows only, by construction
    listed = {p["id"] for p in rows} | {p["id"] for p in between_rows} | {p["id"] for p in unstated_rows}
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
        "rules": {"new_days": NEW_DAYS, "updated_days": UPDATED_DAYS, "closing_days": CLOSING_DAYS, "feed_n": FEED_N,
                  "between_months": BETWEEN_MONTHS},
        "coverage": {
            "federal": {
                "open": federal_open,
                "sources": sources_for(connectors.get("US", []), run_info),
            },
            "state": None if cov is None else {
                "agencies": cov["n_agencies"],
                "programs": cov["n_programs"],
                "open": cov["n_open_municipal"],
                "between": cov["n_between_rounds"],
                "unstated": cov["n_unstated"],
                "last_ok": cov["last_ok"],
                "sources": sources_for(connectors.get(code, []), run_info),
            },
        },
        "excluded_unlikely": excluded,
        "questions": list(READER_QUESTIONS),
        "programs": rows,
        "between": between_rows,
        "unstated": unstated_rows,
        "season": (stats or {}).get("months", {}).get(code),
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
            "between": cov["n_between_rounds"] if cov else 0,
            "unstated": cov["n_unstated"] if cov else 0,
            "last_ok": cov["last_ok"] if cov else None,
            "kind": coverage_kind(code, connectors)[0],
            "note": coverage_kind(code, connectors)[1],
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
    between = [shape_program(r, run_info, today) for r in load_between(conn)]
    unstated = [shape_program(r, run_info, today) for r in load_unstated(conn)]
    changes = load_changes(conn)
    coverage = load_coverage(conn)
    connectors = state_connectors(conn)
    history = load_history(conn, {p["id"] for p in programs + between + unstated})
    stats = load_stats(conn)
    for p in programs + between + unstated:
        p["history"] = history.get(p["id"], [])
    unknown = sorted({p["state"] for p in programs if p["state"] and p["state"] not in STATE_NAME})
    if unknown:
        typer.echo(f"warning: records with a jurisdiction that is not a state page: {', '.join(unknown)}", err=True)
    states = {
        code: state_payload(
            code, programs=programs, between=between, unstated=unstated, changes=changes, coverage=coverage, connectors=connectors,
            run_info=run_info, excluded=excluded_unlikely(conn, code), generated_at=generated_at, stats=stats,
        )
        for code, _, _, _ in STATES
    }
    index = index_payload(
        programs=programs, changes=changes, coverage=coverage, connectors=connectors,
        run_info=run_info, generated_at=generated_at,
    )
    # The site-wide feed: the newest FEED_N across every source (the index page itself embeds only INDEX_FEED_N).
    listed_all = {p["id"] for p in programs} | {p["id"] for p in between} | {p["id"] for p in unstated}
    feed = [shape_change(c, listed_all) for c in changes[:FEED_N]]
    # One feed per listed program (13.9): its whole change log, for the watchlist. A program's feed exists while
    # the program is listed on some page; the watchlist says so.
    own: dict[int, list[dict[str, Any]]] = {}
    for c in changes:
        if c["program_id"] in listed_all:
            own.setdefault(c["program_id"], []).append(shape_change(c, listed_all))
    program_feeds = [
        {"slug": p["slug"], "name": p["name"], "state": p["state"], "source_url": p["source_url"], "entries": own.get(p["id"], [])}
        for p in {p["id"]: p for p in programs + between + unstated}.values()
    ]
    about = about_payload(programs=programs, stats=stats, generated_at=generated_at)
    return {"index": index, "states": states, "feed": feed, "program_feeds": program_feeds, "about": about}


def about_payload(*, programs: list[dict[str, Any]], stats: dict[str, Any], generated_at: str) -> dict[str, Any]:
    """The About the data page (13.14): the chart views plus the open rows' deadlines and awards, nothing else."""
    return {
        "generated_at": generated_at,
        "site_url": SITE_URL,
        "repo_url": REPO_URL,
        "rules": {"new_days": NEW_DAYS, "closing_days": CLOSING_DAYS},
        "states": [{"code": c, "name": n} for c, n, _, _ in STATES],
        "deadlines": [[p["state"], p["closes_at"], p["deadline_placeholder"]] for p in programs if p["closes_at"]],
        "awards": [[p["state"], p["amount_max"], p["name"]] for p in programs if p["amount_max"]],
        "open": {"state": sum(1 for p in programs if p["state"]), "federal": sum(1 for p in programs if not p["state"])},
        "months": stats["months"],
        "stated": stats["stated"],
        "flips": stats["flips"],
        "questions": list(READER_QUESTIONS),
    }


def render_about(data: dict[str, Any], css: str, js: str, template: str) -> str:
    return fill(
        template,
        TITLE="About the data · Funding Atlas",
        DESCRIPTION="What the Funding Atlas registry reads, what its sources state, and what the change log has seen, in five charts.",
        ROOT="../",
        CSS=css,
        JS=js,
        DATA=embed_json(data),
        GENERATED=data["generated_at"][:10],
    )


def program_feed_path(slug: str) -> str:
    """Where a program's own feed lives, relative to the site root (p/<slug>.xml); app.js builds the same path."""
    return "p/" + re.sub(r"[^a-z0-9-]+", "-", (slug or "").lower()) + ".xml"


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
    # The two web fonts (SIL Open Font License, the licence files go with them): same origin, so the pages still
    # make no request to anyone else. The @font-face rules are in the templates, where {{ROOT}} is filled.
    shutil.copytree(WEB / "fonts", out / "fonts")
    (out / "index.html").write_text(render_index(site["index"], css, js, index_tpl), encoding="utf-8")
    generated_at = site["index"]["generated_at"]
    (out / "feed.xml").write_text(render_atom(site["feed"], state=None, self_url=SITE_URL + "feed.xml",
                                              alternate_url=SITE_URL, updated=generated_at), encoding="utf-8")
    (out / "changes.json").write_text(changes_json(site["feed"], state=None, generated_at=generated_at, base=SITE_URL), encoding="utf-8")
    counts: dict[str, int] = {}
    for code, data in site["states"].items():
        d = out / code.lower()
        d.mkdir()
        (d / "index.html").write_text(render_state(data, css, js, state_tpl), encoding="utf-8")
        base = f"{SITE_URL}{code.lower()}/"
        (d / "feed.xml").write_text(render_atom(data["changes"], state=code, self_url=base + "feed.xml",
                                                alternate_url=base, updated=generated_at), encoding="utf-8")
        (d / "changes.json").write_text(changes_json(data["changes"], state=code, generated_at=generated_at, base=base), encoding="utf-8")
        counts[code] = len(data["programs"])
    about_tpl = (WEB / "about.html").read_text(encoding="utf-8")
    (out / "about").mkdir()
    (out / "about" / "index.html").write_text(render_about(site["about"], css, js, about_tpl), encoding="utf-8")
    (out / "p").mkdir()
    for pf in site["program_feeds"]:
        path = program_feed_path(pf["slug"])
        alt = f"{SITE_URL}{pf['state'].lower()}/#p={quote(pf['slug'])}" if pf["state"] else (pf["source_url"] or SITE_URL)
        (out / path).write_text(render_atom(pf["entries"], state=pf["state"], self_url=SITE_URL + path, alternate_url=alt,
                                            updated=generated_at, title=f"{FEED_TITLE}: {pf['name']}"), encoding="utf-8")
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
    md_between = conn.execute("SELECT COUNT(*) FROM v_navigator_between WHERE state = 'MD'").fetchone()[0]
    typer.echo(f"{path}: index + {len(counts)} state pages")
    typer.echo(f"  federal rows on every page: {counts.get('VA', 0)}")
    typer.echo(f"  MD: {counts.get('MD', 0)} rows (v_municipal_page: {md_page}), {md_between} between rounds")
    for code, n in counts.items():
        if n != counts.get("VA", 0) and code != "MD":
            typer.echo(f"  {code}: {n} rows")


if __name__ == "__main__":
    app()
