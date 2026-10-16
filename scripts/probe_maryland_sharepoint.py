"""One-off probe for a Maryland SharePoint (mdgov theme) connector: fetch the index page(s) and a handful of
program pages, save them as test fixtures, and print what the connector sees on each.
  uv run python scripts/probe_maryland_sharepoint.py md_mea                       # default pages
  uv run python scripts/probe_maryland_sharepoint.py md_mea govt/pages/solarapp.aspx
Writes tests/fixtures/<connector>/index__<name>.json per index page (url + main_html, so the index parser is
testable offline) and <name>.json per program page, each the exact RawRecord payload. Every program page is
fetched twice, half a second apart, to show that the text hash is stable while the markup is not."""

from __future__ import annotations

import importlib
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.maryland_sharepoint import fixture_name, main_section, page_h1, page_payload  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

DEFAULT_PAGES = {
    "md_mea": (
        "govt/pages/solarapp.aspx",                                        # status line open, deadline, counties/cities/towns, DOE pass-through
        "pages/commercial%26communitybuildingsgrantprogram.aspx",          # "Now Open!" prose, launch date, %26 in the path
        "pages/communityevse.aspx",                                        # status line open, "local governments" audience
        "govt/pages/smartenergycommunities.aspx",                          # L-GEM: "is CLOSED" prose, "may apply" sentence, past deadline
        "business/pages/resilientmaryland.aspx",                           # "FY26 Program Status: ... CLOSED" line
        "pages/energy-storage-grant-program.aspx",                         # "now open" prose, labels with the value in the next cell
        "residential/pages/incentives/maryland-solar-access-program.aspx", # two fiscal years on one page; first status line wins
        "govt/pages/solartechnicalassistanceprogram.aspx",                 # "remains open until funding is expended": rolling
        "govt/pages/janeelawton.aspx",                                     # no labels, no status sentence: unknown
        "pages/megawattsformaryland.aspx",                                 # closed line + future FOA date: forecasted
        "business/pages/commercial-solar.aspx",                            # closed because funding ran out: exhausted
    ),
    "md_dnr": (
        "land/pages/programopenspace/cpp.aspx",                            # "is now closed", unit H1 -> program H2, "municipal corporations"
        "land/pages/lwcf-grants.aspx",                                     # closed + "Check back in April 2027": forecasted; government-entity list
        "boating/pages/grants.aspx",                                       # hand-added WIF: "by September 18, 2026", public jurisdictions
        "land/pages/programopenspace/home.aspx",                           # POS Local: no status sentence, counties formula
        "met/pages/grant_programs.aspx",                                   # Keep Maryland Beautiful: dated window, municipalities
        "ccs/pages/funding/grantsgateway.aspx",                            # the WIF "no longer accepting" notice must not close it
        "forests/pages/programapps/forestlegacy.aspx",                     # rolling, private landowners
        "met/pages/tax_benefits.aspx",                                     # empty H1 -> H2 name
        "land/pages/greenspace-equity-program.aspx",                       # "is now closed", unit H1
    ),
}


def main(connector: str, paths: list[str]) -> None:
    mod = importlib.import_module(f"connectors.{connector}")
    site = mod.SITE
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / connector
    fixtures.mkdir(parents=True, exist_ok=True)
    today = date.today()
    with site.client() as client:
        print("== indexes ==")
        entries = site.index_entries(client)
        print(len(entries), "program links;", sum(1 for e in entries.values() if not e.get("listed", True)), "hand-added")
        for path in getattr(mod, "INDEX_PATHS", None) or (mod.INDEX_PATH,):
            url = f"{site.BASE}/{path}"
            resp = client.get(url)
            section = main_section(resp.text)
            (fixtures / f"index__{fixture_name(path)}.json").write_text(
                json.dumps({"url": url, "main_html": str(section)}, indent=1, ensure_ascii=False))
            time.sleep(0.3)

        for path in paths:
            entry = entries.get(path) or {"url": f"{site.BASE}/{path}"}
            print(f"\n== {path} ==")
            resp = client.get(entry["url"])
            print("http", resp.status_code)
            if resp.status_code != 200:
                continue
            payload = page_payload(entry["url"], resp.text)
            if payload is None:
                print("no mdgov body")
                continue
            time.sleep(0.5)
            again = page_payload(entry["url"], client.get(entry["url"]).text)
            print("text hash stable:", again is not None and again["content_hash"] == payload["content_hash"],
                  "| markup identical:", again is not None and again["main_html"] == payload["main_html"])
            payload = site.annotate(payload, entry) if hasattr(site, "annotate") else {**payload, **{k: v for k, v in entry.items() if k != "url"}}
            (fixtures / f"{fixture_name(path)}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
            print("title:", payload.get("title"), "| h1:", page_h1(payload["main_html"]), "| body:", len(payload["main_html"]), "bytes")
            print("index:", {k: v for k, v in payload.items() if k in ("index", "unit", "section", "listed")})
            if hasattr(mod, "labeled_lines"):
                for kind, label, value in mod.labeled_lines(payload["main_html"]):
                    print(f"  {kind:12s} {label}: {value[:100]}")
            program = site.normalize(RawRecord(source_connector=site.CONNECTOR, source_id=path, payload=payload), today=today)
            print("name:", program.name)
            print("status:", program.status, "| opens:", program.opens_at, "| closes:", program.closes_at, "| rolling:", program.rolling)
            print("text:", (program.closes_at_text or "")[:200])
            print("funding_type:", program.funding_type, "| source:", program.funding_source, program.alns)
            print("applicants:", program.applicant_pairs())
            print("categories:", program.category_pairs())
    print("\nfixtures written to", fixtures)


if __name__ == "__main__":
    name = sys.argv[1]
    main(name, sys.argv[2:] or list(DEFAULT_PAGES[name]))
