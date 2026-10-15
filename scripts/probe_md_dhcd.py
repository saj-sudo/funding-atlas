"""One-off probe: fetch the DHCD sitemap and a handful of program pages, save them as test fixtures, and
print what the box parser sees on each.
  uv run python scripts/probe_md_dhcd.py                 # default pages
  uv run python scripts/probe_md_dhcd.py business-development/nourishmd-grant-program
Writes tests/fixtures/md_dhcd/sitemap_excerpt.xml (candidate entries plus a few excluded ones) and
<last-path-segment>.json per page, each the exact RawRecord payload."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.md_dhcd import (  # noqa: E402
    BASE,
    SITEMAP_URL,
    _client,
    body_sections,
    page_payload,
    parse_box,
    status_for,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "md_dhcd"
DEFAULT_PAGES = (
    "neighborhood-revitalization/community-development-funding/technical-assistance-grant",
    "business-development/nourishmd-grant-program",
    "neighborhood-revitalization/community-development-funding/community-development-block-grant-program",
    "energy-home-repair/energy-grants-and-loans-residents/net-zero-loan-program",
    "neighborhood-revitalization/main-street-maryland/main-street-improvement-grant-mip",
    "energy-home-repair/energy-grants-and-loans-residents/maryland-energy-assistance-program",
    "neighborhood-revitalization/community-development-funding/state-revitalization-programs/community-legacy-program",  # no box
)


def sitemap_excerpt(xml_text: str, keep_paths: tuple[str, ...]) -> str:
    """Keep the entries for the pages we fixture plus the first media, news, and contacts entries so the
    filter has something to exclude."""
    entries = re.findall(r"<url>.*?</url>", xml_text, re.S)
    wanted = [e for e in entries if any(f"{BASE}/{p}</loc>" in e for p in keep_paths)]
    for marker in ("/media/", "/news-stories/", "/contacts", "/about-us"):
        wanted += [e for e in entries if marker in e][:2]
    wanted += [e for e in entries if f"{BASE}/</loc>" in e][:1]
    head = xml_text[: xml_text.index("<url>")]
    return head + "\n".join(wanted) + "\n</urlset>\n"


def main(paths: list[str]) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with _client() as client:
        print("== sitemap ==")
        xml_text = client.get(SITEMAP_URL).raise_for_status().text
        (FIXTURES / "sitemap_excerpt.xml").write_text(sitemap_excerpt(xml_text, tuple(paths)))
        lastmods = dict(re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>", xml_text))
        print(len(lastmods), "entries with lastmod")

        for path in paths:
            url = f"{BASE}/{path}"
            print(f"\n== {path} ==")
            resp = client.get(url)
            print("http", resp.status_code)
            if resp.status_code != 200:
                continue
            payload = page_payload(url, lastmods.get(url), resp.text)
            if payload is None:
                print("no <main>")
                continue
            name = path.rsplit("/", 1)[-1]
            (FIXTURES / f"{name}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
            lines = parse_box(payload["main_html"])
            print("lastmod:", payload["lastmod"], "| updated:", payload["updated_time"], "| main:", len(payload["main_html"]), "bytes")
            print("box:", lines if lines else "none")
            print("status:", status_for(lines) if lines else "(not a record)")
            print("sections:", [h for h, _ in body_sections(payload["main_html"])])
    print("\nfixtures written to", FIXTURES)


if __name__ == "__main__":
    main(sys.argv[1:] or list(DEFAULT_PAGES))
