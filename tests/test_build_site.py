"""Navigator site: the views of migrations 0005 and 0006, the JSON shaping, and the rendered pages, on an
in-memory database. No network, no browser."""

from __future__ import annotations

import html
import json
import re
from datetime import UTC, date, datetime, timedelta

import pytest

import db
from pipeline.models import ALL_APPLICANT_TYPES, ApplicantTag, CategoryTag, Program
from pipeline.upsert import upsert
from scripts import build_site

LOCAL = [ApplicantTag(value="municipality", source_code="02"), ApplicantTag(value="county", source_code="01")]
EVERYONE = [ApplicantTag(value=t, source_code=f"{i:02d}") for i, t in enumerate(ALL_APPLICANT_TYPES)]
NOW = datetime.now(UTC)
TODAY = NOW.strftime("%Y-%m-%d")
T1 = (NOW - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")   # first full read, three weeks ago
T2 = (NOW - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")    # a later run, two days ago
GEN = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


def prog(source_id, name, **over) -> Program:
    base = dict(
        source_connector="grants_gov", source_id=source_id, source_url=f"https://x/{source_id}", name=name,
        level="federal", jurisdiction="US", administering_agency="Agency X", agency_code="X", funding_type="grant",
        funding_source="direct", status="open", applicant_types=LOCAL,
        categories=[CategoryTag(value="water", source_code="ENV")],
    )
    base.update(over)
    return Program(**base)


SOON = (NOW + timedelta(days=12)).date()
FIRST_RUN = [
    prog("1", "Wildlife Crossings Pilot", closes_at=SOON, amount_max=2_000_000, match_required=True,
         summary="Crossings for critters", eligibility_text="Units of local government <may> apply",
         alns=["20.205", "99.999"], external_number="DOT-001"),
    prog("2", "Rolling State Thing", source_connector="md_mht", level="state", jurisdiction="MD",
         administering_agency="Maryland Historical Trust", agency_code="MD-MHT", funding_type="loan",
         rolling=True, closes_at=None, closes_at_text="Loan applications are accepted year-round.",
         applicant_types=[ApplicantTag(value="municipality", source_code="99")], categories=[]),
    prog("3", "Early-Onset Cancers (R01 Clinical Trial Optional)", agency_code="HHS-NIH11", applicant_types=EVERYONE,
         categories=[CategoryTag(value="health", source_code="HL")]),
    prog("4", "Will Close Later", source_connector="md_dhcd", level="state", jurisdiction="MD",
         administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments"),
    prog("5", "<script>alert(1)</script> Resilience", closes_at=date(2099, 1, 1), eligibility_text="local governments"),
    prog("6", "Virginia Towns Fund", source_connector="va_test", level="state", jurisdiction="VA:Richmond",
         administering_agency="Virginia DHCD", agency_code="VA-DHCD", eligibility_text="towns and cities"),
    prog("20.205", "Highway Planning and Construction", source_connector="sam_assistance_listings", status="unknown",
         applicant_types=[], categories=[], alns=["20.205"]),
    # between rounds: a state round that closed three months ago (listed), one that closed two years ago (too old),
    # and a closed federal notice (never listed: federal rows stay off the appendix)
    prog("8", "Spring Round", source_connector="md_dhcd", level="state", jurisdiction="MD",
         administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
         status="closed", closes_at=(NOW - timedelta(days=90)).date(), closes_at_text="application closed: three months ago"),
    prog("9", "Long Dead Credit", source_connector="md_dhcd", level="state", jurisdiction="MD",
         administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
         status="closed", closes_at=(NOW - timedelta(days=700)).date()),
    prog("10", "Old Notice", status="closed", closes_at=(NOW - timedelta(days=30)).date(), eligibility_text="local governments"),
    # status not confirmed: a state page that states no status and no date (listed, migration 0008), and a federal
    # Assistance Listing in the same state of knowledge (never listed: federal rows stay off the group)
    prog("11", "Main Street Facades", source_connector="md_dhcd", level="state", jurisdiction="MD",
         administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
         status="unknown", closes_at=None, closes_at_text="Applications are accepted each spring."),
]
SECOND_RUN = [
    prog("4", "Will Close Later", source_connector="md_dhcd", level="state", jurisdiction="MD",
         administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
         status="closed"),
    prog("7", "Brand New Notice", closes_at=date(2099, 6, 1), eligibility_text="local governments"),
]


@pytest.fixture(scope="module")
def conn():
    c = db.connect(":memory:")
    db.apply_schema(c)
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('grants_gov', ?, ?, 'ok')", (T1, T1))
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_mht', ?, ?, 'ok')", (T1, T1))
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_dhcd', ?, ?, 'ok')", (T1, T1))
    c.execute("INSERT INTO run (connector, started_at, status) VALUES ('va_test', ?, 'failed')", (T1,))
    upsert(c, 1, FIRST_RUN, T1)
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('grants_gov', ?, ?, 'ok')", (T2, T2))
    c.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_dhcd', ?, ?, 'ok')", (T2, T2))
    upsert(c, 5, SECOND_RUN, T2)
    yield c
    c.close()


# ---------- views ----------

def test_navigator_program_covers_every_state_and_matches_the_maryland_page(conn):
    rows = [dict(r) for r in conn.execute("SELECT * FROM v_navigator_program")]
    assert {r["state"] for r in rows} == {None, "MD", "VA"}
    assert "Early-Onset Cancers (R01 Clinical Trial Optional)" not in {r["name"] for r in rows}   # unlikely
    assert "Will Close Later" not in {r["name"] for r in rows}                                   # closed now
    md = [r["id"] for r in conn.execute("SELECT id FROM v_navigator_program WHERE state IS NULL OR state = 'MD'")]
    page = [r["id"] for r in conn.execute("SELECT id FROM v_municipal_page")]
    assert md == page and len(md) == 4
    wc = next(r for r in rows if r["name"] == "Wildlife Crossings Pilot")
    assert wc["alns"] == "20.205, 99.999" and wc["listings"] == "20.205 · Highway Planning and Construction"
    assert wc["slug"].startswith("wildlife-crossings-pilot-grants-gov-")


def test_navigator_change_keeps_the_closed_flip(conn):
    rows = [dict(r) for r in conn.execute("SELECT * FROM v_navigator_change")]
    assert rows[0]["changed_at"] >= rows[-1]["changed_at"]
    flip = next(r for r in rows if r["name"] == "Will Close Later" and r["change_type"] == "changed")
    assert json.loads(flip["changed_fields"])["status"] == {"old": "open", "new": "closed"}
    assert all(r["name"] != "Early-Onset Cancers (R01 Clinical Trial Optional)" for r in rows)


def test_navigator_coverage(conn):
    cov = {r["state"]: dict(r) for r in conn.execute("SELECT * FROM v_navigator_coverage")}
    assert cov["MD"]["n_agencies"] == 2 and cov["MD"]["n_programs"] == 5 and cov["MD"]["n_open_municipal"] == 1
    assert cov["MD"]["n_between_rounds"] == 2 and cov["MD"]["last_ok"] == T2
    assert cov["VA"]["n_programs"] == 1 and cov["VA"]["n_between_rounds"] == 0 and cov["VA"]["last_ok"] is None
    assert "US" not in cov


def test_navigator_between_lists_recent_closed_state_rounds_only(conn):
    rows = [dict(r) for r in conn.execute("SELECT * FROM v_navigator_between")]
    assert [r["name"] for r in rows] == ["Spring Round", "Will Close Later"]       # dated first, then undated
    assert all(r["state"] == "MD" for r in rows)                                   # never a federal row
    assert "Long Dead Credit" not in {r["name"] for r in rows}                      # older than 15 months
    assert "Old Notice" not in {r["name"] for r in rows}                            # federal, closed, recent: still out
    spring = rows[0]
    assert spring["days_since_deadline"] == 90 and spring["last_reopened"] is None and spring["municipal_tier"] == "likely"
    assert rows[1]["closes_at"] is None and rows[1]["days_since_deadline"] is None
    on_page = {r["id"] for r in conn.execute("SELECT id FROM v_navigator_program")}
    assert not on_page & {r["id"] for r in rows}


def test_navigator_unstated_lists_state_rows_with_no_status_and_no_date(conn):
    rows = [dict(r) for r in conn.execute("SELECT * FROM v_navigator_unstated")]
    assert [r["name"] for r in rows] == ["Main Street Facades"]
    assert rows[0]["closes_at_text"] == "Applications are accepted each spring." and rows[0]["state"] == "MD"
    # the three state views partition what they list: no row in two of them
    groups = [{r["id"] for r in conn.execute(f"SELECT id FROM {v} WHERE state IS NOT NULL")}
              for v in ("v_navigator_program", "v_navigator_between", "v_navigator_unstated")]
    assert sum(len(g) for g in groups) == len(set().union(*groups))
    cov = {r["state"]: dict(r) for r in conn.execute("SELECT * FROM v_navigator_coverage")}
    assert cov["MD"]["n_unstated"] == 1 and cov["VA"]["n_unstated"] == 0


# ---------- shaping ----------

def test_build_shapes_programs_and_rules(conn):
    site = build_site.build(conn, generated_at=GEN)
    md = site["states"]["MD"]
    names = {p["name"]: p for p in md["programs"]}
    assert set(names) == {"Wildlife Crossings Pilot", "Rolling State Thing", "<script>alert(1)</script> Resilience", "Brand New Notice"}
    wc = names["Wildlife Crossings Pilot"]
    assert wc["is_new"] is False                      # first seen on the connector's first run: not "new"
    assert names["Brand New Notice"]["is_new"] is True   # seen on a later run, within the window
    assert wc["days_to_close"] == 12 and wc["match_required"] is True and wc["rolling"] is None
    assert wc["applicant_types"] == ["county", "municipality"] and wc["categories"] == ["water"]
    assert wc["alns"] == ["20.205", "99.999"] and wc["listings"] == [{"aln": "20.205", "name": "Highway Planning and Construction"}]
    assert wc["number"] == "DOT-001" and wc["summary"] == "Crossings for critters"
    rs = names["Rolling State Thing"]
    assert rs["rolling"] is True and rs["closes_at"] is None and rs["closes_text"].startswith("Loan applications")
    assert rs["state"] == "MD" and rs["listings"] == [] and rs["amount_max"] is None
    assert md["coverage"]["state"]["agencies"] == 2 and md["coverage"]["state"]["open"] == 1
    assert md["coverage"]["state"]["between"] == 2 and md["rules"]["between_months"] == build_site.BETWEEN_MONTHS
    assert [p["name"] for p in md["between"]] == ["Spring Round", "Will Close Later"]
    assert [p["name"] for p in md["unstated"]] == ["Main Street Facades"] and md["coverage"]["state"]["unstated"] == 1
    assert md["unstated"][0]["status"] == "unknown" and md["unstated"][0]["closes_text"].startswith("Applications are")
    spring = md["between"][0]
    assert spring["days_since_deadline"] == 90 and spring["days_to_close"] == -90 and spring["last_reopened"] is None
    assert spring["closes_text"] == "application closed: three months ago" and spring["status"] == "closed"
    assert md["coverage"]["federal"]["open"] == 3
    assert md["excluded_unlikely"] == 1
    assert [s["connector"] for s in md["coverage"]["state"]["sources"]] == ["md_dhcd", "md_mht"]

    va = site["states"]["VA"]
    assert {p["name"] for p in va["programs"]} == {"Wildlife Crossings Pilot", "<script>alert(1)</script> Resilience", "Brand New Notice", "Virginia Towns Fund"}
    assert va["coverage"]["state"]["last_ok"] is None and va["coverage"]["state"]["programs"] == 1
    assert va["between"] == [] and va["coverage"]["state"]["between"] == 0 and va["unstated"] == []
    assert site["states"]["WY"]["coverage"]["state"] is None
    assert len(site["states"]["WY"]["programs"]) == 3 and site["states"]["WY"]["between"] == []


def test_history_is_the_programs_own_log(conn):
    site = build_site.build(conn, generated_at=GEN)
    md = site["states"]["MD"]
    closed = next(p for p in md["between"] if p["name"] == "Will Close Later")
    # no code_release rows in the test database, so every cause is 'unknown' (migration 0010)
    assert closed["history"] == [[T1[:10], "added", None, None, "unknown"], [T2[:10], "status", "open", "closed", "unknown"]]
    brand_new = next(p for p in md["programs"] if p["name"] == "Brand New Notice")
    assert brand_new["history"] == [[T2[:10], "added", None, None, "unknown"]]
    assert all("history" in p for p in md["programs"] + md["between"] + md["unstated"])


def test_change_cause_follows_code_releases(conn):
    rows = {r["change_id"]: r["cause"] for r in conn.execute("SELECT * FROM v_change_cause")}
    assert set(rows.values()) == {"unknown"}                       # no git history recorded yet
    flip = conn.execute("SELECT c.id FROM program_change c JOIN program p ON p.id = c.program_id"
                        " WHERE p.name = 'Will Close Later' AND c.change_type = 'changed'").fetchone()[0]
    first = conn.execute("SELECT c.id FROM program_change c JOIN program p ON p.id = c.program_id"
                         " WHERE p.name = 'Will Close Later' AND c.change_type = 'added'").fetchone()[0]
    mid = (datetime.strptime(T1, "%Y-%m-%dT%H:%M:%SZ") + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        # the fixture logs every change under the grants_gov runs (run ids 1 and 5), so the release names that connector
        conn.execute("INSERT INTO code_release VALUES ('grants_gov', 'abc', ?)", (mid,))
        rows = {r["change_id"]: r["cause"] for r in conn.execute("SELECT * FROM v_change_cause")}
        assert rows[first] == "first_read" and rows[flip] == "code"
        conn.execute("UPDATE code_release SET released_at = ?", ((NOW + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),))
        rows = {r["change_id"]: r["cause"] for r in conn.execute("SELECT * FROM v_change_cause")}
        assert rows[flip] == "source"                                 # a release after the run does not count
    finally:
        conn.execute("DELETE FROM code_release")


def test_reading_files_follow_the_imports():
    from pipeline.code_release import reading_files
    from pipeline.run import CONNECTORS
    files = reading_files(CONNECTORS["vt_accd"])
    assert "connectors/vt_accd.py" in files and "connectors/vermont_drupal.py" in files
    assert "pipeline/upsert.py" in files and "pipeline/run.py" not in files
    assert "connectors/ca_grants.py" not in files


def test_build_shapes_changes(conn):
    site = build_site.build(conn, generated_at=GEN)
    md = site["states"]["MD"]
    flip = next(c for c in md["changes"] if c["name"] == "Will Close Later" and c["type"] == "changed")
    assert flip["status_flip"] is True and flip["listed"] is True        # closed, but on the page under "between rounds"
    assert flip["fields"] == [{"field": "status", "old": "open", "new": "closed"}]
    added = next(c for c in md["changes"] if c["name"] == "Brand New Notice")
    assert added["type"] == "added" and added["listed"] is True and added["fields"] == []
    assert all(c["state"] in (None, "MD") for c in md["changes"])
    assert sum(1 for c in md["changes"] if c["state"] == "MD") == 6    # five added + the flip, never starved by federal rows
    assert md["changes"][0]["at"] >= md["changes"][-1]["at"]
    assert len(site["index"]["changes"]) <= build_site.INDEX_FEED_N
    assert site["index"]["federal"]["new"] == 1 and site["index"]["federal"]["closing_soon"] == 1
    week = sum(1 for c in build_site.load_changes(conn) if c["changed_at"][:10] > (NOW - timedelta(days=build_site.NEW_DAYS)).strftime("%Y-%m-%d"))
    assert site["index"]["changes_week"] == week > 0                     # the T2 run is two days ago, T1 three weeks


def test_changes_within_counts_every_change_not_the_index_slice():
    rows = [{"changed_at": "2026-11-19T06:00:00Z"}] * (build_site.INDEX_FEED_N + 5) + [
        {"changed_at": "2026-11-14T00:00:01Z"},    # the first day of the 7 days to 2026-11-20 (14th to 20th)
        {"changed_at": "2026-11-13T23:59:59Z"},    # the day before: outside
        {"changed_at": None},
    ]
    assert build_site.changes_within(rows, "2026-11-20T02:00:00Z", 7) == build_site.INDEX_FEED_N + 6


def test_state_page_reaches_the_first_program_sooner(conn, tmp_path):
    """Redesign session 3 (13.20): the 26-week chart left the state page; sort has a copy in the phone filter tray."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    page = (out / "md" / "index.html").read_text(encoding="utf-8")
    assert 'id="ahead"' not in page and 'id="sort-tray"' in page
    assert page.count('<option value="closing">') == 2          # the toolbar's sort and the tray's offer the same orders


def test_topics_are_words_with_their_own_colours(conn, tmp_path):
    """Redesign session 4 (13.21): no lettered badge or key row; topic colours are tokens of their own in both themes."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    page = (out / "md" / "index.html").read_text(encoding="utf-8")
    css, js = (out / "app.css").read_text(encoding="utf-8"), (out / "app.js").read_text(encoding="utf-8")
    assert "topic-key" not in page + css + js and 'class="topic ' not in page + js
    root, dark = css.split("@media (prefers-color-scheme: dark)", 1)
    for token in ("--topic-env", "--topic-inf", "--topic-com"):
        assert token + ":" in root and token + ":" in dark.split("}", 2)[0] + dark.split("}", 2)[1]


def test_about_page_is_an_essay_argument_first(conn, tmp_path):
    """2026-11-27 (Saj's pick): About reads as an essay, argument first: what sources state, amounts, what is due, then
    under "For researchers" when deadlines fall and what changes, then the limits and Data and code. Each section's
    sentences are built from the payload, so no number is typed into the page. Captions stay plain words: view names
    are in one Data and code note (13.22)."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    page = (out / "about" / "index.html").read_text(encoding="utf-8")
    at = [page.index(s) for s in ('id="lede"', 'id="c3"', 'id="c5"', 'id="c1"', "For researchers", 'id="c2"', 'id="c4"',
                                  "What this cannot tell you", "Data and code")]
    assert at == sorted(at)
    for sid in ("lede", "c3-sub", "c5-sub", "c1-sub", "c2-sub", "c4-sub"):
        assert f'id="{sid}"></p>' in page, sid                      # filled by the script from the counts
    data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1))
    assert isinstance(data["unread"], int) and "log_since" in data
    assert not [s for s in re.findall(r'<p class="src">(.*?)</p>', page, re.S) if "<code>v_" in s]
    assert "<code>v_navigator_program</code>" in page


def test_every_page_has_a_link_preview(conn, tmp_path):
    """Redesign session 1 (13.23): a link pasted into a chat shows a title, a description and the share image."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    png = (out / "share.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and int.from_bytes(png[16:20], "big") == 1200 and int.from_bytes(png[20:24], "big") == 630
    for rel, url in (("index.html", build_site.SITE_URL), ("md/index.html", build_site.SITE_URL + "md/"),
                     ("about/index.html", build_site.SITE_URL + "about/")):
        page = (out / rel).read_text(encoding="utf-8")
        meta = dict(re.findall(r'<meta (?:property|name)="((?:og|twitter):[a-z:_]+)" content="([^"]*)">', page))
        assert meta["og:url"] == url and meta["og:image"] == build_site.SHARE_IMAGE, rel
        assert meta["og:title"] and meta["og:description"] and meta["twitter:card"] == "summary_large_image", rel
        assert f'<link rel="canonical" href="{url}">' in page and page.count('<meta name="theme-color"') == 2, rel
        assert not any(c in page for c in ("1d5bb8", "7fd09b", "f2c069")), rel    # the old off-palette favicon
    assert 'href="../feed.xml"' in (out / "about" / "index.html").read_text(encoding="utf-8")


def test_theme_switch_matches_the_dark_preference(conn, tmp_path):
    """Redesign session 6 (13.24): a dark choice gets exactly the dark preference's tokens; every page has the switch
    and applies a stored choice before it paints."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    for rel in ("index.html", "md/index.html", "about/index.html"):
        page = (out / rel).read_text(encoding="utf-8")
        assert 'id="theme-btn"' in page and "localStorage.getItem('fa-theme')" in page, rel
        assert page.index("localStorage.getItem('fa-theme')") < page.index('<link rel="stylesheet"'), rel
    page = (out / "app.css").read_text(encoding="utf-8")
    pref = re.search(r':root:not\(\[data-theme="light"\]\) \{(.*?)\}', page, re.S).group(1)
    chosen = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', page, re.S).group(1)
    tokens = lambda block: dict(re.findall(r"(--[a-z0-9-]+|color-scheme):\s*([^;]+);", block))  # noqa: E731
    assert tokens(pref) and tokens(pref) == tokens(chosen)
    assert ":root, :root[data-theme] { --bg: #fff;" in page                 # print stays light whatever the choice


def test_index_leads_with_the_map(conn, tmp_path):
    """Redesign session 2 (13.19): the map comes before the numbers, the numbers are sentences, the log is folded."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    index = (out / "index.html").read_text(encoding="utf-8")
    assert 'id="stats"' not in index
    assert index.index('id="map"') < index.index('class="today"') < index.index('id="numbers"') < index.index('<details class="changes-fold" id="changes">') < index.index('id="feed"')
    assert "Pick your state. Your state's own programs come first." in index


def test_map_grammar_and_display_names(conn, tmp_path):
    """2026-11-26: solid stated, hatched read and not stated, dashed cannot be read; a hatched tile's number counts
    programs with no status; a name that opens with its own number is shown without it (display only)."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "listed, no status stated" in index and "cannot be read: blocked or login only" in index
    assert "On a hatched state it counts programs the source lists without saying whether they are open." in index
    css, js = (out / "app.css").read_text(encoding="utf-8"), (out / "app.js").read_text(encoding="utf-8")
    assert ".map a.t.k-blocked { color: var(--muted); background: transparent; border: 2px dashed var(--edge); }" in css
    assert "var num = dir ? s.programs : un ? s.unstated : s.open;" in js
    assert "function programName(p)" in js and "h(programName(p))" in js


def test_scales_and_card_slots(conn, tmp_path):
    """2026-11-26: font sizes, weights and corners come from the token scales; controls take --edge; every card has
    an Amount and a Match slot, hatched with words when the source does not say; dashed is kept for "cannot be read"."""
    css = (build_site.WEB / "app.css").read_text(encoding="utf-8")
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    page = (out / "md" / "index.html").read_text(encoding="utf-8")
    rules = css[css.index("* { box-sizing: border-box; }"):]
    assert not re.findall(r"font-size: [\d.]+rem", rules) and not re.findall(r"font: (?:\d{3} )?[\d.]+rem", rules)
    assert set(re.findall(r"font-weight: (\d+)", rules)) <= {"400", "600", "700"}
    assert set(re.findall(r"border-radius: (\d+px)", rules)) <= {"999px", "0px"}
    assert ".btn { display: inline-flex; align-items: center; gap: 6px; padding: 9px 14px; border: 1px solid var(--edge);" in rules
    # dashed only ever means "cannot be read": the index map's blocked states, and About's atlas (2026-11-27)
    assert [m for m in re.findall(r"([^{}\n]+)\{[^}]*dashed", rules)] == [
        ".legend .sw.wall ", ".tile.t-wall ", ".map a.t.k-blocked ", ".legend i.k-blocked "]
    js = (out / "app.js").read_text(encoding="utf-8")
    assert "slot('Amount', amount) + slot('Match', match)" in js and "'Source does not say'" in js
    assert "Amount not published" not in page + js


def test_program_pages(conn, tmp_path):
    """2026-11-26: every listed program has a page of its own at p/<slug>/, and no other program does; the head is the
    shared one with the program's own title, description, address and feed; the body says something without script."""
    site = build_site.build(conn, generated_at=GEN)
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    listed = {p["slug"] for code in site["states"] for k in ("programs", "between", "unstated") for p in site["states"][code][k]}
    pages = {d.name for d in (out / "p").iterdir() if d.is_dir()}
    assert listed and pages == {build_site.program_page_path(s).split("/")[1] for s in listed}
    assert len(site["program_pages"]) == len(listed)
    key = build_site.asset_version((out / "app.css").read_text(encoding="utf-8"), (out / "app.js").read_text(encoding="utf-8"))
    data = next(d for d in site["program_pages"] if d["program"]["state"] == "MD")
    p = data["program"]
    page = (out / build_site.program_page_path(p["slug"])).read_text(encoding="utf-8")
    url = build_site.program_url(p["slug"])
    assert 'data-page="program"' in page and "{{" not in page
    assert f"<title>{html.escape(p['name'])} · Maryland · Funding Atlas</title>" in page
    assert f'<link rel="canonical" href="{url}">' in page and f'<meta property="og:url" content="{url}">' in page
    assert 'href="../' + build_site.program_feed_path(p["slug"])[2:] + '"' in page       # its own feed, beside the folder
    assert re.findall(r'<script src="([^"]+)"', page) == ["../../app.js?v=" + key]
    assert re.findall(r'<link rel="stylesheet" href="([^"]+)"', page) == ["../../app.css?v=" + key]
    assert page.index("localStorage.getItem('fa-theme')") < page.index('<link rel="stylesheet"')
    body = page[page.index("<body"):page.index('<script type="application/json"')]
    assert html.escape(p["name"]) in body and html.escape(p["source_url"], quote=True) in body
    assert html.escape(build_site.status_sentence(p)) in body and 'href="../../md/"' in body
    embedded = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1))
    assert embedded["program"] == p and embedded["state"] == {"code": "MD", "name": "Maryland"}
    # a federal notice has a page too, and says where it is listed in place of a state
    fed = next(d for d in site["program_pages"] if d["program"]["state"] is None)
    fpage = (out / build_site.program_page_path(fed["program"]["slug"])).read_text(encoding="utf-8")
    assert "· Federal · Funding Atlas</title>" in fpage and "Federal notice, listed on every state page" in fpage
    # feeds and the sitemap point at the page
    feed = (out / build_site.program_feed_path(p["slug"])).read_text(encoding="utf-8")
    assert f'rel="alternate" href="{url}"' in feed or f'href="{url}" rel="alternate"' in feed or url in feed
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert sitemap.count("<url>") == 1 + 51 + 1 + len(listed) and f"<loc>{url}</loc>" in sitemap
    # the status words are the page script's
    js = (out / "app.js").read_text(encoding="utf-8")
    for k, v in build_site.STATUS_LABEL.items():
        assert f"{k}: '{v}'" in js, k


def test_status_sentence_states_only_what_is_stored():
    base = {"status": "open", "closes_at": None, "deadline_placeholder": False, "days_to_close": None, "rolling": False, "closes_text": None}
    assert build_site.status_sentence(base) == "Open. No deadline stated."
    assert build_site.status_sentence(dict(base, rolling=True)) == "Open. Rolling deadline."
    assert build_site.status_sentence(dict(base, status="unknown", closes_text="Spring")) == "Status not confirmed. Deadline in the source's words."
    assert build_site.status_sentence(dict(base, closes_at="2026-12-01", days_to_close=5)) == "Open. Closes Dec 1, 2026."
    assert build_site.status_sentence(dict(base, status="closed", closes_at="2026-02-23", days_to_close=-9)) == "Closed. Last deadline Feb 23, 2026."
    assert build_site.status_sentence(dict(base, closes_at="2035-12-31", deadline_placeholder=True, days_to_close=3000)) == "Open. No deadline stated."


def test_phone_paging_and_federal_fold():
    """2026-11-26 (Saj, from the mockup): on a phone a section shows 10 cards at a time and the federal notices wait
    behind one line while the page is as it opens; wide screens keep 30 and "Show all"."""
    js = (build_site.WEB / "app.js").read_text(encoding="utf-8")
    assert "window.matchMedia('(max-width: 599px)')" in js and "var PAGE_N = PHONE ? 10 : 30" in js
    assert "'Show ' + Math.min(PAGE_N, left) + ' more of ' + rows.length : 'Show all ' + rows.length" in js
    assert "if (!PHONE || st.fed || !FEDERAL_LOADED || !rf.length || !rs.length || !defaultFilters()) return '';" in js
    assert "Show federal notices" in js and "if (st.fed) parts.push('fed=1');" in js


def test_index_daily_blocks(conn):
    """2026-11-26 (Saj's pick A): the index carries what closes this week, the week's changes by kind and what the
    sources state by how each state is read: counts from the data, nothing inferred."""
    site = build_site.build(conn, generated_at=GEN)
    idx = site["index"]
    cw = idx["closing_week"]
    assert cw["total"] == cw["state"] + cw["federal"] and len(cw["rows"]) <= 5
    assert [r["closes_at"] for r in cw["rows"]] == sorted(r["closes_at"] for r in cw["rows"])
    wk = idx["week"]
    assert wk["days"] == build_site.NEW_DAYS and sum(wk["kinds"].values()) == idx["changes_week"]
    assert all({"at", "state", "name", "slug", "old", "new", "listed"} <= set(c) for c in wk["status_changes"])
    assert idx["stated"] and idx["stated"][0]["kind"] == "federal"
    assert all(r["status"] <= r["n"] and r["date"] <= r["n"] and r["amount"] <= r["n"] for r in idx["stated"])


def test_closing_week_and_week_changes_count_only_what_is_stated():
    row = lambda **k: {"slug": "s", "name": "N", "number": None, "state": "MD", "agency": "A", "agency_code": None,  # noqa: E731
                       "closes_at": "2026-12-01", "deadline_placeholder": False, "days_to_close": 3, **k}
    cw = build_site.closing_week([row(), row(state=None, name="F"), row(days_to_close=8), row(days_to_close=-1),
                                  row(deadline_placeholder=True), row(closes_at=None, days_to_close=None)])
    assert (cw["total"], cw["state"], cw["states"], cw["federal"]) == (2, 1, 1, 1) and [r["name"] for r in cw["rows"]] == ["F", "N"]
    ch = lambda day, kind, fields=None, pid=1: {"changed_at": f"2026-11-{day}T00:00:00Z", "change_type": kind, "program_id": pid,  # noqa: E731
                                                "changed_fields": json.dumps(fields) if fields else None, "state": "MD", "name": "N", "slug": "s"}
    wk = build_site.week_changes([
        ch(25, "changed", {"status": {"old": "open", "new": "closed"}, "closes_at": {"old": None, "new": "2026-12-01"}}),
        ch(24, "changed", {"closes_at": {"old": None, "new": "2026-12-01"}}), ch(24, "changed", {"summary": {"old": "a", "new": "b"}}),
        ch(23, "added"), ch(22, "missing", pid=9), ch(10, "changed", {"status": {"old": "open", "new": "closed"}}),
    ], "2026-11-26T00:00:00Z", 7, {1})
    assert wk["kinds"] == {"added": 1, "status": 1, "dates": 1, "wording": 1, "missing": 1}
    assert wk["status_changes"] == [{"at": "2026-11-25T00:00:00Z", "state": "MD", "name": "N", "slug": "s", "old": "open", "new": "closed", "listed": True}]


def test_charts_draw_at_shown_width_with_tables(conn, tmp_path):
    """2026-11-26: a chart is drawn at the width it is shown at (12px labels stay 12px on a phone), a tap shows a
    mark's note, and every About chart has its numbers as a table."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    js, about = (out / "app.js").read_text(encoding="utf-8"), (out / "about" / "index.html").read_text(encoding="utf-8")
    assert "function chartW(svgEl, max)" in js and "var w = 900" not in js and "onWidthChange(draw);" in js
    assert js.count("narrow = w < 560") == 4                     # "what sources state" is HTML squares since 2026-11-27
    assert "svgEl.addEventListener('click', function (e) { var t = e.target.closest('[data-tip]');" in js
    for cid in ("c1", "c2", "c3", "c4", "c5"):
        assert f'<div id="{cid}-table"></div>' in about and (f"el('{cid}-table')" in js), cid
    assert '<th scope="col">' in js and '<th scope="row">' in js


def test_history_strip_is_not_scaled(conn, tmp_path):
    """2026-11-27: the program's history strip has no viewBox and places its marks in percentages, so its 11px labels
    stay 11px on a phone (they were 7.6px at 390 and 17.3px at 1440 when the strip was a 520-unit drawing)."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    js = (out / "app.js").read_text(encoding="utf-8")
    assert "'<svg class=\"hist\" height=\"58\" aria-hidden=\"true\">'" in js and "W = 520" not in js
    assert "svg.hist { width: 100%; height: 58px;" in (out / "app.css").read_text(encoding="utf-8")


def test_index_states_and_tile_grid(conn):
    site = build_site.build(conn, generated_at=GEN)
    states = site["index"]["states"]
    assert len(states) == 51 and len({s["code"] for s in states}) == 51
    assert len({(s["row"], s["col"]) for s in states}) == 51          # no two tiles on one cell
    md = next(s for s in states if s["code"] == "MD")
    assert md["programs"] == 5 and md["open"] == 1 and md["agencies"] == 2 and md["between"] == 2
    assert md["unstated"] == 1
    wy = next(s for s in states if s["code"] == "WY")
    assert wy["programs"] == 0 and wy["between"] == 0


# ---------- rendering ----------

def test_coverage_kind_follows_the_connectors():
    con = {"MD": ["md_dhcd"], "CA": ["ca_grants"], "ND": ["webgrants", "nd_dot"], "NC": ["nc_grants"]}
    assert build_site.coverage_kind("MD", con) == ("agencies", None)
    assert build_site.coverage_kind("CA", con) == ("portal", None)
    assert build_site.coverage_kind("ND", con) == ("portal_agencies", None)
    assert build_site.coverage_kind("NC", con) == ("directory", None)
    assert build_site.coverage_kind("AK", con)[0] == "blocked" and build_site.coverage_kind("AK", con)[1]
    assert build_site.coverage_kind("AR", con) == ("federal", None)
    # a blocked state that gains a connector stops being called blocked
    assert build_site.coverage_kind("AK", {"AK": ["ak_test"]}) == ("agencies", None)


def test_stats_views_count_what_the_pages_list(conn):
    stated = {r["state"]: dict(r) for r in conn.execute("SELECT * FROM v_stats_stated")}
    md = stated["MD"]
    assert md["n"] == 5 and md["status_stated"] == 4          # Main Street Facades states no status
    assert stated["US"]["n"] == conn.execute("SELECT COUNT(*) FROM v_navigator_program WHERE state IS NULL").fetchone()[0]
    flips = [dict(r) for r in conn.execute("SELECT * FROM v_stats_status_flips")]
    assert {(f["old_status"], f["new_status"], f["cause"]): f["n"] for f in flips} == {("open", "closed", "unknown"): 1}
    months = list(conn.execute("SELECT state, month, n FROM v_stats_deadline_month"))
    assert all(1 <= m <= 12 for _, m, _ in months) and {st for st, _, _ in months} <= {"MD", "VA"}


def test_about_page_is_written_and_same_origin(conn, tmp_path):
    out, _ = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    page = (out / "about" / "index.html").read_text(encoding="utf-8")
    assert 'data-page="about"' in page and 'href="../fonts/public-sans-latin.woff2"' in page
    data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1))
    assert {"deadlines", "awards", "months", "stated", "flips", "open"} <= set(data)
    assert set(re.findall(r'<script src="([^"?]+)', page)) == {"../app.js"} and "cdn" not in page


def test_what_sources_state_is_a_hundred_squares_by_kind(conn, tmp_path):
    """2026-11-27 (Saj's pick A2): "what sources state" sums the stated fields by how each state is read, as the index
    does; every row carries its kind, no count is null, and the chart is squares, solid for stated, in HTML."""
    out, _ = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    page = (out / "about" / "index.html").read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1))
    rows, kinds = data["stated"], data["stated_kinds"]
    assert rows and all(r["kind"] and all(r[k] is not None for k in ("n", "status_stated", "date_stated", "amount_stated")) for r in rows)
    assert kinds[0]["kind"] == "federal"
    for k in kinds:
        mine = [r for r in rows if r["kind"] == k["kind"]]
        assert k["n"] == sum(r["n"] for r in mine) and k["date"] == sum(r["date_stated"] for r in mine) and k["states"] == len(mine)
    assert '<div id="c3" class="waffle"></div>' in page and '<svg id="c3"' not in page
    js = (out / "app.js").read_text(encoding="utf-8")
    assert "function chartStated(el, tableEl, kinds, rows)" in js and "for (var i = 0; i < 100; i++)" in js
    assert "m-s1" not in js and "--s3" not in (out / "app.css").read_text(encoding="utf-8")


def test_one_colour_one_meaning_in_the_charts(conn, tmp_path):
    """2026-11-27: hue says who (blue federal, orange and its ramp state), fill says whether the source stated it, ink
    for the rest. Blue had also meant "states a status" and "the source changed", and the heat map of state-only
    deadlines was a blue ramp."""
    out = build_site.write(conn, tmp_path / "site", generated_at=GEN)[0]
    js, css = (out / "app.js").read_text(encoding="utf-8"), (out / "app.css").read_text(encoding="utf-8")
    assert "var(--q" not in js and "--q1" not in css and css.count("--o1:") == 3
    assert "var RAMP = ['var(--o1)'" in js
    assert "[['src', 'm-ink'], ['other', 'm-ink'], ['code', 'm-maybe']]" in js
    # blue marks only on the two charts that split federal from state: weekly deadlines and maximum awards
    assert js.count("'m-fed'") == 1 and js.count("class=\"m-fed\"") == 1


def test_about_opens_with_the_atlas(conn, tmp_path):
    """2026-11-27 (Saj's pick H1 for the entry piece): About opens with every state on the tile map, filled to the share
    of its programs whose source states a deadline; each tile carries how the state is read and, if it is not, why."""
    out, _ = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    page = (out / "about" / "index.html").read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1))
    atlas = {s["code"]: s for s in data["atlas"]}
    assert len(atlas) == len(build_site.STATES) and all({"row", "col", "kind", "n", "date", "listed"} <= set(s) for s in atlas.values())
    md = next(r for r in data["stated"] if r["state"] == "MD")
    assert atlas["MD"]["n"] == md["n"] and atlas["MD"]["date"] == md["date_stated"]
    assert atlas["AK"]["kind"] == "blocked" and atlas["AK"]["note"] and atlas["AK"]["n"] == 0
    assert page.index('id="lede"') < page.index('id="atlas"') < page.index('id="c3"')
    assert 'id="atlas-note" aria-live="polite"' in page
    js = (out / "app.js").read_text(encoding="utf-8")
    assert "function drawAtlas(el, noteEl, atlas, fed, kinds)" in js and "aria-pressed" in js


def test_about_shows_how_each_state_is_read(conn, tmp_path):
    """2026-11-27: the same map by how each state is read, with the state pages' own reason for every unread state;
    the paragraph and the "five ways" heading are counted from the atlas, not typed."""
    out, _ = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    page = (out / "about" / "index.html").read_text(encoding="utf-8")
    assert page.index('id="atlas"') < page.index('id="kindmap"') < page.index('id="c3"')
    assert 'id="read-sub"></p>' in page and 'id="reasons"' in page and 'id="kindmap-note" aria-live="polite"' in page
    js = (out / "app.js").read_text(encoding="utf-8")
    assert "drawAtlas(el('kindmap'), el('kindmap-note'), A.atlas, null, true);" in js
    assert "claim('h-read', ways === 5 && A.atlas.length === 51, 'Fifty states, read five ways');" in js


def test_embed_json_is_script_safe():
    text = build_site.embed_json({"a": "</script><b> "})
    assert "</" not in text and "\\u2028" in text
    assert json.loads(text) == {"a": "</script><b> "}


def test_write_site(conn, tmp_path):
    out, counts = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    assert (out / ".nojekyll").exists() and (out / "index.html").exists()
    assert len(counts) == 51 and counts["MD"] == 4 and counts["VA"] == 4 and counts["WY"] == 3
    page = (out / "md" / "index.html").read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>")
    assert "<script>alert(1)</script>" not in page
    data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1))
    federal = json.loads((out / "federal.js").read_text(encoding="utf-8").removeprefix("window.FA_FEDERAL = ").rstrip().rstrip(";"))
    # the page carries Maryland's own rows; the federal ones come once from federal.js (13.16)
    assert all(p["state"] == "MD" for p in data["programs"]) and all(p["state"] is None for p in federal["programs"])
    assert data["state"] == {"code": "MD", "name": "Maryland"} and len(data["programs"]) + len(federal["programs"]) == 4
    assert len(data["between"]) == 2
    assert 'id="list-between"' in page and 'id="between-toggle"' in page and len(data["unstated"]) == 1
    # the state's own groups come before the federal notices (13.1, decision 2026-11-14)
    order = [page.index(f'id="g-{g}"') for g in ("state", "unstated", "between", "federal")]
    assert order == sorted(order)
    assert "<may>" in json.dumps(federal)                                # verbatim text survives the round trip
    assert "</script" not in (out / "federal.js").read_text(encoding="utf-8")
    # same origin only (2026-11-26): the stylesheet and script are files beside the pages, shared and cached; a page
    # loads those, federal.js and the two fonts, and nothing from anywhere else
    css, js = (out / "app.css").read_text(encoding="utf-8"), (out / "app.js").read_text(encoding="utf-8")
    assert css == (build_site.WEB / "app.css").read_text(encoding="utf-8") and js == (build_site.WEB / "app.js").read_text(encoding="utf-8")
    key = build_site.asset_version(css, js)
    assert key != build_site.asset_version(css + " ", js) and key != build_site.asset_version(css, js + " ")
    assert re.findall(r'<script src="([^"]+)"', page) == ["../federal.js?v=" + GEN[:10], "../app.js?v=" + key]
    assert re.findall(r'<link rel="stylesheet" href="([^"]+)"', page) == ["../app.css?v=" + key]
    for rel, root in (("index.html", ""), ("about/index.html", "../")):
        other = (out / rel).read_text(encoding="utf-8")
        assert re.findall(r'<script src="([^"]+)"', other) == [root + "app.js?v=" + key], rel
        assert re.findall(r'<link rel="stylesheet" href="([^"]+)"', other) == [root + "app.css?v=" + key], rel
        assert "<style" not in other and "function programName" not in other, rel
    assert "<style" not in page and "function programName" not in page and ":root {" not in page
    body = page.replace("https://x/", "")
    assert "@import" not in body + css and "url(http" not in body + css and "cdn" not in body + css + js
    assert not re.search(r'(?:src|href)="https?://(?!x/)', re.sub(r'<(?:meta|link rel="(?:canonical|alternate)")[^>]*>', "", body))
    index = (out / "index.html").read_text(encoding="utf-8")
    assert 'data-page="index"' in index and "Funding Atlas" in index
    # web fonts are served from the site itself, with their licences, and referenced relative to each page
    assert (out / "fonts" / "public-sans-latin.woff2").exists() and (out / "fonts" / "OFL-SourceSerif4.txt").exists()
    assert 'href="../fonts/source-serif-4-latin.woff2"' in page and 'href="fonts/public-sans-latin.woff2"' in index
    assert 'url("fonts/source-serif-4-latin.woff2")' in css and 'url("fonts/public-sans-latin.woff2")' in css
    # rebuilding wipes stale files
    (out / "stale.txt").write_text("x")
    build_site.write(conn, out, generated_at=GEN)
    assert not (out / "stale.txt").exists()


def test_a_reopening_is_observed_from_the_change_log(conn):
    """Last in the file on purpose: it adds a third run to the shared fixture."""
    t3 = (NOW - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    run3 = conn.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_dhcd', ?, ?, 'ok')", (t3, t3)).lastrowid
    reopened = prog("8", "Spring Round", source_connector="md_dhcd", level="state", jurisdiction="MD",
                    administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
                    status="open", closes_at=(NOW + timedelta(days=60)).date(), closes_at_text="application closes in two months")
    upsert(conn, run3, [reopened], t3)
    assert "Spring Round" not in {r["name"] for r in conn.execute("SELECT name FROM v_navigator_between")}
    assert "Spring Round" in {r["name"] for r in conn.execute("SELECT name FROM v_navigator_program")}
    # close it again: the appendix now carries the observed reopening date, from the log, not from a calendar
    t4 = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    run4 = conn.execute("INSERT INTO run (connector, started_at, finished_at, status) VALUES ('md_dhcd', ?, ?, 'ok')", (t4, t4)).lastrowid
    closed = prog("8", "Spring Round", source_connector="md_dhcd", level="state", jurisdiction="MD",
                  administering_agency="Maryland DHCD", agency_code="MD-DHCD", eligibility_text="local governments",
                  status="closed", closes_at=(NOW - timedelta(days=1)).date())
    upsert(conn, run4, [closed], t4)
    row = dict(conn.execute("SELECT * FROM v_navigator_between WHERE name = 'Spring Round'").fetchone())
    assert row["last_reopened"] == t3 and row["days_since_deadline"] == 1
    site = build_site.build(conn, generated_at=GEN)
    spring = next(p for p in site["states"]["MD"]["between"] if p["name"] == "Spring Round")
    assert spring["last_reopened"] == t3


def test_placeholder_dates_are_flagged_not_dropped():
    from datetime import date as _date

    from scripts.build_site import is_placeholder

    today = _date(2026, 10, 18)
    assert is_placeholder("2035-12-31", today) is True and is_placeholder("2999-07-01", today) is True
    assert is_placeholder("2031-10-18", today) is False and is_placeholder("2031-10-19", today) is True
    assert is_placeholder("2027-06-30", today) is False and is_placeholder(None, today) is False
    assert is_placeholder("not a date", today) is False



# ---------- the change feed (Atom + JSON) ----------

def test_feed_files_exist_for_root_and_every_state(conn, tmp_path):
    out, counts = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    assert (out / "feed.xml").exists() and (out / "changes.json").exists()
    for code in counts:
        assert (out / code.lower() / "feed.xml").exists() and (out / code.lower() / "changes.json").exists()
    page = (out / "md" / "index.html").read_text(encoding="utf-8")
    assert '<link rel="alternate" type="application/atom+xml" title="Funding Atlas: changes" href="feed.xml">' in page
    assert '<link rel="alternate" type="application/atom+xml"' in (out / "index.html").read_text(encoding="utf-8")


def test_every_listed_program_has_its_own_feed(conn, tmp_path):
    import xml.etree.ElementTree as ET
    out, _ = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    site = build_site.build(conn, generated_at=GEN)
    listed = {p["slug"] for d in site["states"].values() for p in d["programs"] + d["between"] + d["unstated"]}
    files = {f.name for f in (out / "p").iterdir() if f.is_file()}             # the folders beside them are program pages
    logged = {r["slug"] for r in conn.execute("SELECT DISTINCT slug FROM v_navigator_change")}
    assert files == {build_site.program_feed_path(sl)[2:] for sl in listed | logged}
    # a program that left every page keeps its feed: Long Dead Credit closed two years ago and is listed nowhere
    gone = conn.execute("SELECT slug FROM program WHERE name = 'Long Dead Credit'").fetchone()[0]
    assert gone not in listed and build_site.program_feed_path(gone)[2:] in files
    closed = next(p for p in site["states"]["MD"]["between"] if p["name"] == "Will Close Later")
    root = ET.parse(out / build_site.program_feed_path(closed["slug"])).getroot()
    ns = {"a": build_site.ATOM_NS}
    assert root.find("a:title", ns).text.endswith(": Will Close Later")
    assert sorted(e.find("a:title", ns).text for e in root.findall("a:entry", ns)) == ["added: Will Close Later", "changed: Will Close Later"]


def test_atom_parses_ids_unique_and_scoped_to_the_state(conn, tmp_path):
    import xml.etree.ElementTree as ET
    out, _ = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    md = ET.parse(out / "md" / "feed.xml").getroot()
    assert md.find("a:title", ns).text == "Funding Atlas: changes (Maryland and federal)"
    assert md.find("a:updated", ns).text == GEN and md.find("a:id", ns).text == build_site.SITE_URL + "md/feed.xml"
    entries = md.findall("a:entry", ns)
    assert entries, "the Maryland feed has entries"
    ids = [e.find("a:id", ns).text for e in entries]
    assert len(ids) == len(set(ids)) and all(i.startswith(build_site.FEED_ID_PREFIX) for i in ids)
    assert {e.find("a:category", ns).get("term") for e in entries} <= {"federal", "MD"}
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", e.find("a:updated", ns).text) for e in entries)
    flip = next(e for e in entries if e.find("a:title", ns).text == "changed: Will Close Later")
    assert flip.find("a:summary", ns).text == "status open → closed · Maryland DHCD · Maryland"
    assert flip.find("a:link", ns).get("href") == build_site.SITE_URL + "p/" + quote_slug(conn, "Will Close Later") + "/"
    va = ET.parse(out / "va" / "feed.xml").getroot()
    assert {e.find("a:category", ns).get("term") for e in va.findall("a:entry", ns)} <= {"federal", "VA"}
    root = ET.parse(out / "feed.xml").getroot()
    assert root.find("a:title", ns).text == "Funding Atlas: changes (every source)"
    assert len(root.findall("a:entry", ns)) <= build_site.FEED_N
    assert {e.find("a:category", ns).get("term") for e in root.findall("a:entry", ns)} >= {"federal", "MD", "VA"}


def quote_slug(conn, name):
    from urllib.parse import quote
    return quote(conn.execute("SELECT slug FROM program WHERE name = ?", (name,)).fetchone()[0])


def test_changes_json_equals_the_pages_change_log(conn, tmp_path):
    out, _ = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    page = (out / "md" / "index.html").read_text(encoding="utf-8")
    # the state's own log is in changes.js since 2026-11-26 (it loads when the Changes tab opens); the page keeps
    # the count for the tab and the week's status changes for the briefing line
    on_page = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1))
    text = (out / "md" / "changes.js").read_text(encoding="utf-8")
    assert "</script" not in text and "changes.js?v=" in (out / "app.js").read_text(encoding="utf-8")
    embedded = json.loads(text.removeprefix("window.FA_CHANGES = ").rstrip().rstrip(";"))
    assert "changes" not in on_page and on_page["changes_n"] == len(embedded) > 0
    cutoff = (NOW.date() - timedelta(days=build_site.NEW_DAYS)).isoformat()
    assert on_page["week_flips"] == [c for c in embedded if c["status_flip"] and c["at"][:10] >= cutoff]
    assert all(c["state"] == "MD" for c in embedded)
    federal = json.loads((out / "federal.js").read_text(encoding="utf-8").removeprefix("window.FA_FEDERAL = ").rstrip().rstrip(";"))
    embedded = sorted(embedded + federal["changes"], key=lambda c: (c["at"], c["id"]), reverse=True)
    data = json.loads((out / "md" / "changes.json").read_text(encoding="utf-8"))
    assert data["state"] == "MD" and data["generated_at"] == GEN and data["feed"]["atom"].endswith("/md/feed.xml")
    assert [c["id"] for c in data["changes"]] == [c["id"] for c in embedded]
    assert all("summary" in c and "link" in c for c in data["changes"])
    root = json.loads((out / "changes.json").read_text(encoding="utf-8"))
    assert root["state"] is None and len(root["changes"]) <= build_site.FEED_N


def test_describe_change_wording():
    d = build_site.describe_change
    assert d({"type": "added", "fields": []}) == "added to the registry"
    assert d({"type": "missing", "fields": [{"field": "status", "old": "open", "new": "unknown"}]}) == "no longer listed by the source · status open → unknown"
    assert d({"type": "changed", "fields": [{"field": "status", "old": "open", "new": "closed"},
                                            {"field": "eligibility_text", "old": "a", "new": "b"}]}) == "status open → closed · also eligibility text"
    assert d({"type": "changed", "fields": [{"field": "summary", "old": "a", "new": "b"}]}) == "summary"
    assert d({"type": "changed", "fields": [{"field": "closes_at", "old": None, "new": "2026-12-01"},
                                            {"field": "amount_max", "old": 1000, "new": 2500000}]}) == "closes (blank) → 2026-12-01 · max award $1,000 → $2,500,000"
    assert d({"type": "changed", "fields": []}) == "changed"


def test_field_label_mirrors_app_js():
    js = (build_site.WEB / "app.js").read_text(encoding="utf-8")
    block = re.search(r"var FIELD_LABEL = \{(.*?)\};", js, re.S).group(1)
    pairs = dict(re.findall(r"(\w+): '([^']*)'", block))
    assert pairs == build_site.FIELD_LABEL


def test_feed_link_uses_the_program_page_when_listed():
    c = {"slug": "a-b", "state": "MD", "listed": True, "source_url": "https://x/1"}
    assert build_site.feed_link(c, "MD") == build_site.SITE_URL + "p/a-b/"
    assert build_site.feed_link({**c, "state": None}, "VA") == build_site.SITE_URL + "p/a-b/"         # a federal notice has one page, whichever feed names it
    assert build_site.feed_link({**c, "state": None}, None) == build_site.SITE_URL + "p/a-b/"
    assert build_site.feed_link({**c, "listed": False}, "MD") == "https://x/1"


def test_control_characters_do_not_break_atom():
    import xml.etree.ElementTree as ET
    entry = {"id": 1, "at": GEN, "type": "added", "name": "Bad\x00name\x07", "slug": "x", "state": "MD", "level": "state",
             "agency": "A\x1f", "connector": "md_dhcd", "listed": True, "source_url": "https://x/1", "fields": []}
    text = build_site.render_atom([entry], state="MD", self_url="https://s/md/feed.xml", alternate_url="https://s/md/", updated=GEN)
    root = ET.fromstring(text)
    assert root.find("{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}title").text == "added: Badname"


def test_summary_json_counts_the_pages_own_rows(conn, tmp_path):
    """summary.json is the page in numbers: it must agree with the JSON the page embeds, row for row."""
    out, _ = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    for code in ("md", "va", "wy"):
        page = (out / code / "index.html").read_text(encoding="utf-8")
        data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S).group(1))
        summary = json.loads((out / code / "summary.json").read_text(encoding="utf-8"))
        own = [p for p in data["programs"] if p["state"] is not None]
        assert summary["state"] == data["state"]
        assert summary["page"] == f"{build_site.SITE_URL}{code}/"
        # The page embeds the state's own rows; federal rows ship once in federal.js (13.16), so the federal
        # number is checked against the count the page states for them.
        assert len(own) == len(data["programs"])
        assert summary["open"] == {"state": len(own), "federal": data["coverage"]["federal"]["open"]}
        assert sum(c["open"] for c in summary["by_category"]) == sum(len(p["categories"]) for p in own)
        assert summary["license"]["records"] == "ODbL-1.0" and summary["audience"] == "local governments"


def test_summary_json_lists_only_real_upcoming_deadlines():
    """No placeholder dates, nothing already past, nearest first, and never more than SUMMARY_SOON_N."""
    def row(name, days, *, state="MD", placeholder=False):
        return {"name": name, "state": state, "agency": "Agency", "slug": name.lower().replace(" ", "-"),
                "categories": ["housing"], "closes_at": "2026-12-01", "days_to_close": days,
                "deadline_placeholder": placeholder}
    data = {
        "generated_at": GEN,
        "state": {"code": "MD", "name": "Maryland"},
        "programs": [
            row("Past", -3), row("Placeholder", 4000, placeholder=True), row("No date", None),
            row("Federal", 2, state=None),
            *[row(f"Round {i}", 10 + i) for i in range(build_site.SUMMARY_SOON_N + 2)],
            row("Soonest", 1),
        ],
    }
    summary = json.loads(build_site.summary_json(data))
    names = [c["name"] for c in summary["closing_soon"]]
    assert names[0] == "Soonest" and len(names) == build_site.SUMMARY_SOON_N
    assert not {"Past", "Placeholder", "No date", "Federal"} & set(names)
    assert summary["closing_soon"][0]["link"] == f"{build_site.SITE_URL}md/#p=soonest"
    assert summary["open"]["federal"] == 1


def test_summary_json_exists_for_every_state(conn, tmp_path):
    out, _ = build_site.write(conn, tmp_path / "site", generated_at=GEN)
    for code, _, _, _ in build_site.STATES:
        summary = json.loads((out / code.lower() / "summary.json").read_text(encoding="utf-8"))
        assert summary["state"]["code"] == code
