"""Probe the index hosts the census recorded as blocked, from wherever this runs (milestone 12.0).

The 50-state census (docs/surveys/state_portals.md, 2026-10-18) was taken through this project's development proxy,
and ten hosts answered a 403, a bot challenge or a connection reset. The daily runner is GitHub Actions, whose address
range is the one that matters for a connector, so `.github/workflows/probe_hosts.yml` runs this script there on demand.
Each URL and its host's robots.txt is fetched once with the connectors' own User-Agent; the script prints the status,
the server header, the final URL after redirects and the first 300 bytes of the body, and never fails. It writes
nothing. Results are read by a person and recorded in the census: a 200 moves the state to 12.8, a wall is blocked for
good (the GOCPP rule).

A state can carry further URLs (`EXTRA`), and `--tries N` fetches each URL N times, for a host that walls some requests
and not others (Tennessee, 12.6j: an AWS load balancer answered 403 to about half the development proxy's requests).
Each try prints the HTTP version beside the status.

  uv run python scripts/probe_hosts.py            # every host
  uv run python scripts/probe_hosts.py CO ME      # a few
  uv run python scripts/probe_hosts.py --tries 5 TN
"""

from __future__ import annotations

import re
import sys
import time
from urllib.parse import urlsplit

import httpx

USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"
TIMEOUT_S = 30.0
DELAY_S = 3.0  # the connectors' own pace on a host that may rate-limit (12.6j)
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
    "TN": ("tn.gov agency pages (AWS ELB 403 on some requests, 12.6j)", "https://www.tn.gov/ecd/grants.html"),
}

# state -> further URLs on the same host, probed after the first
EXTRA: dict[str, list[str]] = {
    "TN": [
        "https://www.tn.gov/ecd/rural-development/cdbg.html",
        "https://www.tn.gov/ecd/rural-development/infrastructure-planning-grant.html",
        "https://www.tn.gov/tdot.html",
        "https://www.tn.gov/environment.html",
        "https://www.tn.gov/tema.html",
        # the program pages a connector would read (all 403 through the development proxy after ~30 requests)
        "https://www.tn.gov/ecd/community-development-block-grant/cdbg/cdbg-community-development-regular-round.html",
        "https://www.tn.gov/ecd/rural-development/site-development.html",
        "https://www.tn.gov/ecd/rural-development/threestar.html",
        "https://www.tn.gov/ecd/rural-development/tennessee-main-street/downtown-improvement-grant-program.html",
        "https://www.tn.gov/ecd/rural-development/historic-development-grant-program.html",
        "https://www.tn.gov/environment/about-tdec/grants/recreation.html",
        "https://www.tn.gov/environment/about-tdec/grants/water.html",
        "https://www.tn.gov/environment/about-tdec/grants/materials-management.html",
        "https://www.tn.gov/environment/about-tdec/grants/remediation.html",
        "https://www.tn.gov/tdot/local-programs-community-investments/local-programs/tap.html",
        "https://www.tn.gov/tdot/local-programs-community-investments/local-programs/funding-options.html",
        "https://www.tn.gov/tdot/local-programs-community-investments/community-investments-office/bicycle-and-pedestrian-program.html",
        "https://www.tn.gov/tema/assistance/assistance-for-local-governments.html",
        "https://www.tn.gov/tema/ready-communities/grants/governor-s-response-and-recovery-fund.html",
    ],
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
    return f"{resp.status_code} | {resp.http_version} | server={server} | final={final} | {body}"


def parse_args(argv: list[str]) -> tuple[int, list[str]]:
    tries, states, rest = 1, [], iter(argv)
    for arg in rest:
        if arg == "--tries":
            tries = max(1, int(next(rest, "1")))
        else:
            states.append(arg.upper())
    return tries, states


def main(states: list[str], tries: int = 1) -> None:
    chosen = {s: HOSTS[s] for s in (states or HOSTS) if s in HOSTS}
    unknown = [s for s in states if s not in HOSTS]
    if unknown:
        print(f"not in the list: {' '.join(unknown)} (known: {' '.join(HOSTS)})")
    with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for i, (state, (label, url)) in enumerate(chosen.items()):
            if i:
                time.sleep(DELAY_S)
            print(f"\n== {state}: {label}")
            print(f"   robots: {describe(client, robots_url(url))}")
            for page in [url, *EXTRA.get(state, [])]:
                print(f"   {page}")
                for n in range(tries):
                    if n:
                        time.sleep(DELAY_S)
                    print(f"   page {n + 1}: {describe(client, page)}")


if __name__ == "__main__":
    tries, states = parse_args(sys.argv[1:])
    main(states, tries)
