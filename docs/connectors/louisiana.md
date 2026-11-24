# Louisiana's Office of Community Development: survey and stop (12.9, 2026-11-24)

Louisiana has no public state index of funding programs (`docs/surveys/state_portals.md`). The target was the Division of
Administration's Office of Community Development: the Louisiana CDBG program pages (public facilities, economic
development), the Local Government Assistance Program (LGAP) and the Community Water Enrichment Fund (CWEF). The
disaster-recovery programs (OCD-DRU, `restore.la.gov`) were out of scope from the start.

**Stopped: no connector.** The programs are no longer on the host we may read.

| Agency | Host | CMS | robots | Result | Verdict |
|---|---|---|---|---|---|
| Division of Administration | `www.doa.la.gov` | the DOA's own CMS behind Cloudflare (no challenge) | `/robots.txt` answers 404: no restriction | `/doa/ocd/` is 200 and empty | **nothing to read** |
| Office of Community Development | `locd.la.gov` | not seen | not fetched | our proxy refuses the host (`CONNECT tunnel failed, response 403`) | **not reachable from here** |

## What was read (two page requests to `www.doa.la.gov` after its `robots.txt`, one refused attempt at `locd.la.gov`)

1. `https://www.doa.la.gov/doa/ocd/` (200). The page is titled "Office of Community Development - Disaster Recovery" and
   its body is the breadcrumb and the Division's address, nothing else: no program text and no link to LCDBG, LGAP or CWEF.
   The site menu's "Office of Community Development" entry points to **`https://locd.la.gov/`**.
2. `https://www.doa.la.gov/sitemap.xml` (404): no sitemap to find a surviving LGAP or CWEF page from. The earlier census
   had already found the old LGAP address 404, and no page under `www.doa.la.gov` was guessed at.
3. `https://locd.la.gov/robots.txt`: refused by our own network allowlist, not by the site. Nothing is known about that
   host's `robots.txt`, CMS or pages. It was not worked around.

So the office has moved to a site of its own, and that host is not on this session's allowlist.

## Sample of the raw data

```
https://www.doa.la.gov/doa/ocd/  (the whole body, after the site-wide phishing notice and menu)
    Office of Community Development
    Home / Division Offices / Office of Community Development - Disaster Recovery
    [the Division's address and telephone numbers]
```

## Field mapping

None: there is no program text to map. If `locd.la.gov` turns out readable, the mapping would be the agency-page table in
`connectors/hand_list.py` with a reader of its own, id `la_ocd`, agency "Louisiana Office of Community Development",
code `LA-OCD`.

## Implemented

Nothing. No connector, no fixtures, no tests.

## Gaps and follow-ups

- **`locd.la.gov`**: add the host to the allowlist (or run one `probe-hosts` key from the Actions runner), read its
  `robots.txt` first, then survey LCDBG, LGAP and CWEF. Until then Louisiana has no agency connector.
- The disaster-recovery programs stay out (CDBG-DR).
- Louisiana's other municipal agencies (DOTD's local programs, DEQ's revolving funds, GOHSEP's mitigation grants) were not
  surveyed: none of their hosts was on the allowlist for this session.
