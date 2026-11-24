# Louisiana's Office of Community Development: surveyed, then built on its new host (12.9, 2026-11-24)

Louisiana has no public state index of funding programs (`docs/surveys/state_portals.md`). The target was the Division of
Administration's Office of Community Development: the Louisiana CDBG program pages (public facilities, economic
development), the Local Government Assistance Program (LGAP) and the Community Water Enrichment Fund (CWEF). The
disaster-recovery programs (OCD-DRU, `restore.la.gov`) were out of scope from the start.

**First pass: nothing on `www.doa.la.gov`** (below). The office now publishes on `locd.la.gov`; once that host was
allowed it was read and built the same day: see "Built: `la_ocd`" at the end.

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

## Built: `la_ocd` (2026-11-24)

`https://locd.la.gov` (served by Netlify, server-rendered; `robots.txt`: `User-agent: * / Allow: /`). Requests: robots,
the home page, three program pages for the survey, three for the fixtures, six for two live runs, 3 s apart.

Reader (`connectors/la_ocd.py`): the title is the `h1` in `<main>`; blocks are the `h2`/`h3`/`h4`, `p` and `li` after
it; the read stops at "Resources". One GET per page, `DELAY_S` 3 s.

| Record | Name | Status on 2026-11-24 | What the page says |
|---|---|---|---|
| `lgap` | Local Government Assistance Program | **open**, 2026-11-02 to 2027-02-26 | "The LGAP application period is open from November 2, 2026, through February 26, 2027." |
| `cwef` | Community Water Enrichment Fund | **open**, 2026-11-02 to 2027-02-26 | "Applications for FY2026-2027 are open November 2, 2026, through February 26, 2027" |
| `cdbg` | CDBG: Public Facilities Program | unknown | one paragraph, no round |
| `cdbg#clearance` | CDBG: Clearance Program | unknown | one paragraph, no round |
| `cdbg#economic-development` | CDBG: Economic Development Program | unknown | one paragraph, no round |
| `cdbg#make-a-difference` | CDBG: Make a Difference Program | unknown | one paragraph, no round |

Live: first run 6 added, second run no changes.

Scope calls and local rules:
- The CDBG page is four records through `SPLITS` (each program is one paragraph that starts with its name). Its CDBG-CV
  half (a one-time CARES Act allocation; "no additional applications are being accepted") is a tail with no record.
  The names carry "Community Development Block Grant (CDBG):" in front; that prefix is ours.
- **The date window**: this office writes "November 2, 2026, through February 26, 2027", with a comma the shared
  `RANGE_RE` does not allow. The module reads it itself (`WINDOW_RE`, in a sentence about applications): open inside
  the window, forecasted before, unknown with the date kept after. A wish for the shared rule, not made here.
- **CDBG applicants**: taken only from the page's own "LOCD partners with local governments" sentence and Make a
  Difference's "grants for non-entitlement local governments", so the Economic Development paragraph's "for-profit
  businesses" (who a project serves) are not tagged.
- Funding source set per record: LGAP and CWEF `direct` (their pages mention HUD only to define a non-entitlement
  community), the four CDBG records `pass_through` (the page names no federal agency).
- Amounts are not stored: the pages give ceilings by population band (villages up to $25,000 ... parishes up to
  $100,000), which is not one program maximum.

Not read (follow-ups): the Recovery Housing Program, the Water Sector Program and the EPA programs pages under Local
Government Assistance; every disaster recovery program (out of scope); other Louisiana agencies (DOTD, DEQ, GOHSEP).
