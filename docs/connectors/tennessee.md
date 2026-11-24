# Tennessee's agency pages: walled on 2026-11-17 (12.6j), built on 2026-11-24 (12.9)

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

## The re-probe (2026-11-24) and the build (12.9)

`probe-hosts`, `states: TN`, on the Actions runner (run 10, 00:24 UTC): **20 of 20 pages 200** (`server: Apache`, the AEM
dispatcher), no 403. The first request of the run, `robots.txt`, was a connection reset, as the first two requests of
run 2 were on 2026-11-17; it is not the load balancer's refusal, and the robots file read on 2026-11-17 was
`User-agent: * / Allow: /`. The reopen rule ("every request 200: build; any 403: blocked for good") is read as met.
**For Saj**: if the reset on the first request should count as a failure, the two connectors come out of
`pipeline/run.py` and `site.yml` in one line each.

The development network is still refused: one request from this session answered `403` (`awselb/2.0`), and nothing
more was sent. The fixtures were cut from the bodies the runner saved (the `probe-out` artifact), with
`scripts/probe_tennessee.py --from DIR`. **Not verified**: a live `cli.py run` of either connector; their first live
read is the daily workflow's.

### Implemented (breadth first: ECD, and TDOT's one page that describes a program)

One reader for both (`connectors/tn_ecd.py`, `parse_page`): title `.tn-pagetitle h1`; every `.tn-rte` and
`.textimage-text` block under `#main` in page order (each tab of a tabbed page); a paragraph that lists dates one to a
line (`<br>`) is one block per line; contact lines dropped; the read stops at "Application Process", "Contact
Information" and "Materials & Resources". `DELAY_S` is 6 s. A refused request keeps the stored record.

| Connector | Record | Status on 2026-11-24 | What the page says |
|---|---|---|---|
| `tn_ecd` | `cdbg`, CDBG Community Development Regular Round | unknown | "Applications may be submitted only once a year, in the spring." No date. Funding source pass-through (the CDBG hub names HUD; this page does not). |
| `tn_ecd` | `infrastructure-planning`, Infrastructure Planning Grant | unknown, closes 2026-10-30 kept | "Application Deadline: October 30, 2026"; match required ("the required 5% match funding") |
| `tn_ecd` | `downtown-improvement`, Downtown Improvement Grant Program | unknown, opens 2026-07-07, closes 2026-08-28 kept | "July 7, 2026* - Application opens", "August 28, 2026 - Application Due" |
| `tn_ecd` | `threestar`, ThreeStar | unknown | "biennial grants will be available to counties"; no round |
| `tn_tdot` | `tap`, Transportation Alternatives Program | unknown | one paragraph, no round; "providing funds to local governments" |

Scope calls: **Site Development** is left out (its page is three image tiles, no text). **Historic Development Grant**
is left out while its page says "This funding has been allocated ... The grant program will not have any additional
rounds of grants" (the Missouri funds-exhausted rule). TDOT's **Funding Options** (formula STBG allocations, no
application) and **Active Transportation Office** (no program) pages are not records.

### Gaps

- Applicant tags are empty on CDBG, the Infrastructure Planning Grant and the Downtown Improvement Grant: their pages say
  who applies in sentences the shared rules do not read ("Eligible cities, with the exception of metropolitan
  governments, or counties can submit only one application"; "open to utility systems that serve distressed counties";
  "Tennessee Main Street Programs and Tennessee Downtowns alumni ... are eligible for a grant"). No shared rule was
  added for one state.
- Follow-ups, each a module on the same reader: TDEC's grants hub (LPRF, RTP, TRIP on the recreation page; water,
  materials management, remediation), TEMA's local-government assistance, TDOT's State Infrastructure Fund and
  Multimodal Access Grant, the CDBG hub's other rounds. THDA (`thda.org`) is its own host, not surveyed.
- Keep the request count low when adding pages: the wall of 2026-11-17 came after about sixty requests in fifteen minutes.
