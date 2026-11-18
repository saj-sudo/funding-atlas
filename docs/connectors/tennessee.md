# Tennessee's agency pages: walled for the daily run (12.6j, 2026-11-17)

Milestone 12.6j, the next agency state in the 12.6 cost ranking. Tennessee has no state index
(`docs/surveys/state_portals.md`); its agencies (ECD, TDOT, TDEC, TEMA) all publish on `www.tn.gov`, one Adobe Experience
Manager site, which would have made one base and four modules (the Vermont shape). **Not built**: the site's AWS load
balancer answers 403 to the connectors' requests from the GitHub Actions runner, `robots.txt` included.

## What was seen (2026-11-17, the connectors' own User-Agent)

`robots.txt`: `User-agent: * / Allow: /`. Two answers come back from `www.tn.gov`: the AEM dispatcher (`server: Apache`,
HTTP/1.1, cached pages with an `Age` header) with the page, or an AWS load balancer (`server: awselb/2.0`) with a bare
`403 Forbidden`.

| When | Client | What came back |
|---|---|---|
| 17:43 to 17:47 | curl through the development proxy, 4 to 30 s apart | about half 403 (`awselb`, HTTP/2), half 200 (Apache, HTTP/1.1); the same page flipped between the two |
| 17:52 | httpx (the connectors' client), `scripts/probe_hosts.py --tries 2 TN`, 1 s apart | 13 of 13 200 (robots and six shallow pages) |
| 17:55 | Actions runner, `probe-hosts` run 2, `--tries 5 TN` | 29 of 31 200; the first two requests a connection reset |
| 17:56 | httpx through the development proxy, 14 program pages 3 s apart | 14 of 14 403 (`awselb`) |
| 17:58 | Actions runner (a fresh machine), `probe-hosts` run 3, 21 URLs | **21 of 21 403 (`awselb`), robots.txt included**, the six pages that passed three minutes earlier among them |

So the wall is not the page or the address: after roughly sixty requests in fifteen minutes the load balancer refused this
User-Agent from both networks. It may be a rule that lifts. The CLAUDE.md stop rule applies: no browser User-Agent, no
pinning a request to the dispatcher, no retry on a 403.

**Reopen**: one `probe-hosts` run (`states: TN`) no sooner than 2026-11-24. Every request 200: build as below, with
`DELAY_S` of at least 3 s. Any 403: Tennessee is blocked for good unless the state allows it (the GOCPP route: ask the
office, or ECD, for permission or a feed).

## What the build would read (from the pages that came through)

- **The page**: title in `.tn-pagetitle h1`; the program text in each `.tn-rte` block under `#main` (tabbed pages put one
  block per tab, `.tab-pane`; the link-button tabs hold reports and forms). One reader for every agency.
- **ECD**, Community and Rural Development (`/ecd/rural-development/...`): CDBG (regular round), Site Development,
  ThreeStar, Downtown Improvement Grant, Historic Development Grant, Infrastructure Planning Grant. The Infrastructure
  Planning Grant page states its round plainly: "FY26-27 IPG Timeline: Application Launch: September 1, 2026 / Application
  Deadline: October 30, 2026 / Award Announcements: January 2027"; it is "open to utility systems that serve distressed
  counties and rural communities on the financially distressed utility system referral list".
- **TDOT**, Local Programs (`/tdot/local-programs-community-investments/...`): TAP, the funding options page, the State
  Infrastructure Fund, the Bicycle and Pedestrian program.
- **TDEC**, the grants hub (`/environment/about-tdec/grants.html`): recreation (LPRF, LWCF, RTP), water (SRF), materials
  management, remediation.
- **TEMA**: assistance for local governments, the Governor's Response and Recovery Fund.
- **THDA** (`thda.org`) is its own host; not surveyed.
