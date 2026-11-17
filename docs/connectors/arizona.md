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
