"""Probe the index hosts the census recorded as blocked, from wherever this runs (milestone 12.0).

The 50-state census (docs/surveys/state_portals.md, 2026-10-18) was taken through this project's development proxy,
and ten hosts answered a 403, a bot challenge or a connection reset. The daily runner is GitHub Actions, whose address
range is the one that matters for a connector, so `.github/workflows/probe_hosts.yml` runs this script there on demand.
Each URL and its host's robots.txt is fetched once with the connectors' own User-Agent; the script prints the status,
the server header, the final URL after redirects and the first 300 bytes of the body, and never fails. It writes
nothing. Results are read by a person and recorded in the census: a 200 moves the state to 12.8, a wall is blocked for
good (the GOCPP rule).

  uv run python scripts/probe_hosts.py            # every host
  uv run python scripts/probe_hosts.py CO ME      # a few
"""

from __future__ import annotations

import re
import sys
import time
from urllib.parse import urlsplit

import httpx

USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"
TIMEOUT_S = 30.0
DELAY_S = 1.0
BODY_CHARS = 300

# state -> (what the census calls it, the index URL recorded there)
HOSTS: dict[str, tuple[str, str]] = {
    "AK": ("DCCED (DataDome 403)", "https://www.commerce.alaska.gov/web/dcra/"),
    "CO": ("DOLA Local Community Funding Guide (CloudFront 403)", "https://dlg.colorado.gov/local-community-funding-guide"),
    "ID": ("Commerce grants (Cloudflare challenge)", "https://commerce.idaho.gov/incentives-and-financing/grants/"),
    "KS": ("Kansas Infrastructure Hub (Akamai 403)", "https://www.kshub.gov/"),
    "ME": ("MOCA Community Funding Finder (CloudFront 403)", "https://www.maine.gov/moca/funding"),
    "MI": ("eGrams (Akamai 403)", "https://www.michigan.gov/egrams"),
    "MN": ("mn.gov/grants/find (Radware captcha)", "https://mn.gov/grants/find/"),
    "NM": ("DFA (502 / reset through the proxy)", "https://www.nmdfa.state.nm.us/"),
    "RI": ("GMS funding opportunities (Cloudflare challenge)",
           "https://controller.admin.ri.gov/grants-management/grant-management-system-gms/subrecipients/funding-opportunities"),
    "OK": ("OGX, Oklahoma Grant Exchange (reset through the proxy)", "https://ogx.ok.gov/"),
    "FL": ("FloridaCommerce (Azure WAF 403)", "https://floridajobs.org/"),
    "VT": ("eGrants (reset through the proxy)", "https://egrants.vermont.gov/"),
}


def robots_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def describe(client: httpx.Client, url: str) -> str:
    try:
        resp = client.get(url)
    except httpx.HTTPError as e:
        return f"{type(e).__name__}: {str(e)[:120]}"
    body = re.sub(r"\s+", " ", resp.text[:4000]).strip()[:BODY_CHARS]
    server = resp.headers.get("server", "-")
    final = str(resp.url) if str(resp.url) != url else "-"
    return f"{resp.status_code} | server={server} | final={final} | {body}"


def main(states: list[str]) -> None:
    chosen = {s: HOSTS[s] for s in (states or HOSTS) if s in HOSTS}
    unknown = [s for s in states if s not in HOSTS]
    if unknown:
        print(f"not in the list: {' '.join(unknown)} (known: {' '.join(HOSTS)})")
    with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for i, (state, (label, url)) in enumerate(chosen.items()):
            if i:
                time.sleep(DELAY_S)
            print(f"\n== {state}: {label}")
            print(f"   {url}")
            print(f"   page:   {describe(client, url)}")
            print(f"   robots: {describe(client, robots_url(url))}")


if __name__ == "__main__":
    main([s.upper() for s in sys.argv[1:]])
