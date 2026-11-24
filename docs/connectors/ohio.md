# Ohio: Department of Development, stopped (12.9, 2026-11-24)

Ohio has no public state index with structured rows (`docs/surveys/state_portals.md`). The agency a town would start with
is the Department of Development (CDBG: Community Development Allocation, Neighborhood Revitalization, Critical
Infrastructure, Residential Public Infrastructure, Economic Development; Brownfield Remediation; Building Demolition and
Site Revitalization). Surveyed read-only with the connectors' User-Agent.

| Agency | Host | What answered | Verdict |
|---|---|---|---|
| Department of Development | `development.ohio.gov` | **404 from `AmazonS3`** on `/robots.txt`, on `/community` and on `/` (the home page): the same static "404 Error Page" each time | **stopped** |

## What the host answers

Three GETs in all, 2026-11-24, from the development proxy: `/robots.txt`, `/community` (the central survey)
and `/` (this session's recheck). Each returned HTTP 404 with `Server: AmazonS3` and the same 111 characters of text,
titled "404 Error Page", whose stylesheets are under `/errorpages/assets/`. A home page that is "not found" is not a
missing page: the state's front end did not hand this client the site at all and served its error bucket instead. Whether
it decides by User-Agent, by network or by something else was **not** established: the rule is no browser User-Agent and
no retry around a refusal, so nothing else was tried.

So there is no robots file to read, no program page, and nothing to say about how the program pages are built (server
HTML or a script shell): no page of the site was ever served.

## Sample of the raw data

```
HTTP 404   Server: AmazonS3
<title>404 Error Page</title>
<link rel="stylesheet" type="text/css" href="/errorpages/assets/css/ds-core.css">
```

## Implemented

Nothing: no connector, no fixtures, no tests. No internal API was called.

## Gaps and follow-ups

- One probe of `https://development.ohio.gov/` and `/robots.txt` from the Actions runner (`probe-hosts`) would say whether
  the daily run is refused too. If the runner gets the site, the survey starts over there (robots first).
- If it is refused there as well: ask the Department, as with GOCPP.
- Ohio's other municipal agencies (ODOT local programs, Ohio EPA's water financing, the Ohio Public Works Commission,
  ODNR's recreation grants) were not surveyed: their hosts are not on this session's allowlist.
