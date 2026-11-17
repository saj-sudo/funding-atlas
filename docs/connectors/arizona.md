# Arizona's agency pages: survey (12.6j fallback, 2026-11-17)

Arizona has no public state index (`docs/surveys/state_portals.md`: the Grants Network is a login). Surveyed after
Tennessee was walled (`docs/connectors/tennessee.md`), read-only, the connectors' User-Agent, one `robots.txt` and at most
two pages a host, 3 s apart. The five walled hosts were then probed once each from the Actions runner (`probe-hosts` run
4, `AZ-*` keys in `scripts/probe_hosts.py`).

| Agency | Host | robots | Development proxy | Actions runner | Verdict |
|---|---|---|---|---|---|
| Department of Housing (CDBG) | `housing.az.gov` | not served (challenge) | Cloudflare challenge | Cloudflare challenge | **blocked** |
| Transportation (ADOT) | `azdot.gov` | not served (challenge) | Cloudflare challenge | Cloudflare challenge | **blocked** |
| Emergency and Military Affairs (DEMA) | `dema.az.gov` | not served (challenge) | Cloudflare challenge | Cloudflare challenge | **blocked** |
| Commerce Authority | `www.azcommerce.com` | not served (challenge) | Cloudflare challenge | Cloudflare challenge | **blocked** |
| Water Infrastructure Finance Authority (WIFA) | `www.azwifa.gov` | **`ClaudeBot: Disallow: /`** (Content-Signal `ai-train=no`) | 200 | not probed | **not read**, the ADECA rule |
| State Parks and Trails, WebGrants storefront | `www.azparkgrants.com` | not served (challenge) | Cloudflare challenge | Cloudflare challenge | **blocked** (would have been one line in `connectors/webgrants.py`) |
| State Parks and Trails, program pages | `azstateparks.com` | `User-agent: * / Disallow:` | 200 (nginx) | not probed | **readable** |

## What State Parks would give

The grants hub (`/grants`) links seven program pages: LWCF (`/lwcf-grants`), Competitive LWCF / ORLP
(`/competitive-LWCF-grants`), OHV (`/off-highway-vehicle-fund-grants`), the Route 66 Historic Revitalization Grant,
RTP (`/recreational-trails-program-grants`), SLIF (`/state-lake-improvement-fund-grants`) and the Heritage Fund. Each page
carries labelled lines: "Available Funds: $1,820,000", "Eligible Applicants: Federal, State, Local, County, and Tribal
Governments and Non-Profits are eligible to apply", "Eligible Projects: ...". **No page states a round**: the hub says
"Grant opportunities are available throughout the year. For timing, please register in Webgrants", and the WebGrants
storefront is walled. So every record would be `unknown` ("Status not confirmed"), as most of South Dakota's are.

## Scope (Saj, 2026-11-17: build State Parks), one record per program page

Each a line in `connectors/az_parks.py`'s `PAGES`: LWCF (`/lwcf-grants`), Competitive LWCF, ORLP/RARI
(`/competitive-LWCF-grants`; NPS's national competition, in as Missouri's ORLP is), OHV (`/off-highway-vehicle-fund-grants`),
RTP (`/recreational-trails-program-grants`), SLIF (`/state-lake-improvement-fund-grants`), the Heritage Fund
(`/heritage-fund-grants`), Historic Preservation Heritage Grants (`/heritage-fund-historic-preservation-grants`) and the
Route 66 Historic Revitalization Grant (`/route-66-historic-revitalization-grant`; nonprofits, local governments, tribes
and businesses: in, the tagger decides). Out: workshops, how to apply, awarded projects (no program).

## Field mapping

The agency-page table in `connectors/hand_list.py`, with a reader of this module's own (no other Arizona agency is read):

- **Text**: the `div.content.container .col-md-12` column; the grants submenu is a `nav` and is dropped. The read stops at
  the `h2` "Start Here Before You Apply" (an accordion of manuals, maps and tools, then the apply link). The FAQ and
  contact line ("Have questions about eligibility ...") is dropped.
- `name`: the column's first `h2` (the page has two `h1`s, the first the site logo).
- `status`: `unknown` on every page today; no page states a round ("For timing, please register in Webgrants").
- `eligibility_text` and applicants: the "Eligible Applicants:" item of the labelled list.
- `funding_source`: the shared `funding_source_for` (RTP names FHWA, LWCF the federal fund; SLIF, OHV and Heritage are
  state funds).
- "Available Funds: $1,820,000" is not parsed: the amount parser stays deferred until its third case (roadmap); the line
  stays in the stored text.

## Sample of the raw data (RTP, 2026-11-17)

```
h2  Recreational Trails Program (RTP) Grants
p   The Recreational Trails Program (RTP) is a federal-aid assistance program ... returned to the states through the
    Federal Highway Administration (FHWA) to provide grants for a wide variety of trail projects. ...
li  <b>Available Funds:</b> $1,820,000
li  <b>Eligible Applicants:</b> Federal, State, Local, County, and Tribal Governments and Non-Profits are eligible to apply
li  <b>Eligible Projects:</b> Trail construction/maintenance, trail facilities (trailheads, restrooms, parking), and trail education.
p   Have questions about eligibility or the application process? Consult this helpful FAQ document ...   (dropped)
h2  Start Here Before You Apply   (the read stops)
```
