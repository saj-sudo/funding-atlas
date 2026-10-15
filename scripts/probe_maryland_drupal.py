"""One-off probe for a maryland.gov Drupal connector: fetch the sitemap and a handful of pages, save them as
test fixtures, and print what the connector sees on each.
  uv run python scripts/probe_maryland_drupal.py md_commerce                 # default pages
  uv run python scripts/probe_maryland_drupal.py md_mht funding/museum-assistance-program-grants
Writes tests/fixtures/<connector>/sitemap_excerpt.xml (the fixtured entries plus a few that the filter must
drop) and <last-path-segment>.json per page, each the exact RawRecord payload."""

from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.maryland_drupal import body_sections, page_payload, parse_box, source_id_for  # noqa: E402

DEFAULT_PAGES = {
    "md_commerce": (
        "financial-incentives/grants/exportmd-program",
        "financial-incentives/grants/maryland-manufacturing-40-m40",
        "financial-incentives/tax-incentives/employer-security-clearance-costs-tax-credit-escc",
        "financial-incentives/tax-incentives/research-and-development-tax-credit-rd",
        "financial-incentives/loans-financing/child-care-capital-support-revolving-loan-fund",
        "financial-incentives/loans-financing/advantage-maryland-medaaf",
        "financial-incentives/loans-financing/cannabis-business-assistance-fund-cbaf",
        "financial-incentives/grants",                                   # section index, no status: excluded
    ),
    "md_mht": (
        "funding/how-apply-grant",                                       # the open list
        "funding/historic-preservation-capital-grant-program",
        "funding/african-american-heritage-preservation-program-grants/aahpp-non-capital-grants",
        "planning-protection/maryland-heritage-areas-program/maryland-heritage-areas-program-project-grants",
        "funding/loans-historic-preservation",
        "funding/maritime-heritage-grant-program",
        "funding/tax-credits/small-commercial-tax-credit",
        "planning-protection/preservation-easements/donate-or-convey-easement",   # Timeline, no eligibility: excluded
    ),
}
DROP_MARKERS = ("/media/", "/press-room/", "/education-outreach/", "/about", "/contacts")


def sitemap_excerpt(xml_text: str, base: str, keep_paths: tuple[str, ...]) -> str:
    entries = re.findall(r"<url>.*?</url>", xml_text, re.S)
    wanted = [e for e in entries if any(f"{base}/{p}</loc>" in e for p in keep_paths)]
    for marker in DROP_MARKERS:
        wanted += [e for e in entries if marker in e][:2]
    wanted += [e for e in entries if f"{base}/</loc>" in e][:1]
    head = xml_text[: xml_text.index("<url>")]
    return head + "\n".join(wanted) + "\n</urlset>\n"


def main(connector: str, paths: list[str]) -> None:
    mod = importlib.import_module(f"connectors.{connector}")
    site = mod.SITE
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / connector
    fixtures.mkdir(parents=True, exist_ok=True)
    with site.client() as client:
        print("== sitemap ==")
        xml_text = client.get(site.sitemap_url).raise_for_status().text
        (fixtures / "sitemap_excerpt.xml").write_text(sitemap_excerpt(xml_text, site.BASE, tuple(paths)))
        lastmods = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", xml_text))
        print(len(lastmods), "entries with lastmod;", len(site.iter_sitemap(xml_text)), "kept by the filter")
        context = site.before_fetch(client)
        print("context:", context)

        for path in paths:
            url = f"{site.BASE}/{path}"
            print(f"\n== {path} ==")
            resp = client.get(url)
            print("http", resp.status_code)
            if resp.status_code != 200:
                continue
            payload = page_payload(url, lastmods.get(url), resp.text)
            if payload is None:
                print("no <main>")
                continue
            payload = site.annotate(payload, context)
            (fixtures / f"{path.rsplit('/', 1)[-1]}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
            sections = body_sections(payload["main_html"])
            print("lastmod:", payload["lastmod"], "| updated:", payload["updated_time"], "| main:", len(payload["main_html"]), "bytes")
            print("sections:", [h for h, _ in sections])
            print("box:", parse_box(payload["main_html"]) or "none")
            if site.is_record(payload):
                print("fields:", site.status_fields(payload, sections, __import__("datetime").date.today()))
                print("applicants:", [(t.value, t.source_code) for t in site.normalize(
                    __import__("pipeline.models", fromlist=["RawRecord"]).RawRecord(
                        source_connector=site.CONNECTOR, source_id=source_id_for(url), payload=payload)).applicant_types])
            else:
                print("(not a record)")
    print("\nfixtures written to", fixtures)


if __name__ == "__main__":
    name = sys.argv[1]
    main(name, sys.argv[2:] or list(DEFAULT_PAGES[name]))
