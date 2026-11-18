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

Surveyed: eight program pages. Built: five. **Left out while they state "Available Funds: $0 (Arizona State Parks and Trails
did not receive any additional FY27 ... funds ...)"**: SLIF and both Heritage Fund pages (the Missouri funds-exhausted rule;
commented lines in `PAGES`, restored when the FY28 pages name an amount). The eight: LWCF (`/lwcf-grants`), Competitive LWCF, ORLP/RARI
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

## Implemented (2026-11-17)

`connectors/az_parks.py`, the reader of its own (title from the page's last `h1`, since two pages open with a question as
their first `h2`; the read also stops at Route 66's "Frequently Asked Questions"). `scripts/probe_arizona.py` saved the
fixtures. First live run on a copy of the restored database: **5 added, 0 errors**; second run **0 changed**.

| Record | Status on 2026-11-17 | Applicants tagged | Source |
|---|---|---|---|
| LWCF Grants | unknown (no round stated) | municipality, county, tribe | pass_through (the hub's sentence) |
| Competitive LWCF Grants (ORLP/RARI) | unknown: "typically in June and closing in October" (kept, no year) | municipality, county, tribe, state, special district | pass_through (NPS) |
| Off Highway Vehicle Fund Grants | unknown | municipality, county, state, nonprofit | direct (the state OHV fund) |
| Recreational Trails Program (RTP) Grants | unknown | municipality, county, state, tribe, nonprofit | pass_through (FHWA) |
| Route 66 Historic Revitalization Grant | unknown: "Pre-Application due Friday, November 6, 2026" (past; final applications due 2026-11-23, but only after a pre-application) | municipality, county, tribe, nonprofit, business | pass_through (NPS's Paul Bruhn grant) |

The Arizona page: 0 open, 4 under "Status not confirmed", Route 66 under "Closed recently". No script errors, no sideways
scroll at 390px, light and dark.

**Shared rule** (`connectors/text.py`): "Local" inside a list that ends in "Governments" tags municipality and county (RTP's
"Federal, State, Local, County, and Tribal Governments"). Measured: 17 tag moves of 7,796 stored records, all closed
California CDFA rounds that say "local, state, and federal government entities" (correct readings), 0 other hash moves; 1 of
212 fixture records (RTP). Kept at Saj's word.

### Gaps and follow-ups

- SLIF and both Heritage Fund pages: restore their `PAGES` lines when the FY28 pages name an amount.
- Round dates live in the WebGrants storefront (walled): a page that never dates its round stays `unknown`.
- Housing (CDBG), ADOT (TA, safety), DEMA (mitigation) and Commerce are Arizona's municipal core and are all walled; WIFA
  disallows `ClaudeBot`. Reopen only if a runner probe gets through or the state gives permission.
