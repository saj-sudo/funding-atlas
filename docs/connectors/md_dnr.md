# Maryland DNR connector: site verification and field mapping

Milestone 7, connector 2. Live probe 2026-10-16. Second SharePoint (mdgov theme) agency; platform notes and the shared
base are in `maryland_sharepoint.md`, which was extracted while writing this connector.

## Implemented (2026-10-16, same day)

`connectors/md_dnr.py` follows this doc on the `MarylandSharePointConnector` base. Live run on the session database:
20 records (4 open, 1 forecasted, 2 closed, 13 unknown), as expected below; the second run reports no changes. Two
records carry a municipality tag and reach `v_municipal_page`: Keep Maryland Beautiful (open, closes 2026-12-01) and
the Land and Water Conservation Fund (forecasted, "Check back in April 2027"). Maryland's open municipal count went
from 11 to 13. Thirteen `unknown` records is the honest reading of a site whose program pages mostly describe the
program and point at a manual; the diff will show each one the day its page gains a dated window.

Known gaps, all because the page does not say it the way the rules read:

- Living Shorelines answers "Who is eligible?" in the next block ("Local Governments and non-profits"), so the
  sentence scan tags homeowners and individuals from other sentences and misses the local governments. The page is
  `unknown` (no application wording), so nothing surfaces wrongly; joining question headings to their answers is a
  rule for when a second page needs it.
- The Grants Gateway is one solicitation for six programs. One record, named "Grants Gateway", with the latest of its
  application deadlines (December 11, 2026) and no applicant tags: the page describes eligible projects, not
  applicants.
- (Fixed the same day, milestone 7.1.) `individual` used to tag the adjective in "individual private ... lands" on the
  Keep Maryland Beautiful page; the shared table now matches the noun only.
- The Waterway Improvement Fund's H1 is "Grants managed by Waterway Improvement and Infrastructure Program"; the
  `<title>` ("State Waterway Improvement Fund Grants") reads better, but the H1 is the rule on every other page.

## Source

`https://dnr.maryland.gov`, SharePoint on the state's `mdgov` theme, behind Cloudflare. No sitemap (404);
`robots.txt` disallows only the SharePoint system paths.

`/Pages/grantsandloans.aspx` is a hand-curated index: three jump links, then three `<h3>` sections separated by
`<hr>`, each with unit headings (`<h3>` or `<h4>`) above a `<ul>` of program links:

```
h3  Cost-share Programs
h3  Forest Service - Cost-share Programs        -> /forests/Pages/programapps/costshareprograms.aspx
h4  Wildlife and Heritage Service               -> /wildlife/Pages/habitat/milo.aspx
h3  Financial and Technical Resources
h3  Forest Service                              -> mucfcgrant (404), otheragencies-rcfp, fcmp, forestlegacy, tax (404), costshareprograms (+#eqip, #wip, #gpc), /land/Pages/crep.aspx
h3  Land Acquisition and Planning               -> cpp, LWCF-Grants, Greenspace-Equity-Program, ProgramOpenSpace/home, RuralLegacy/home
h3  Maryland Environmental Trust                -> grant_programs, Grant-EE-CI-CU (#bill, #clean, #jones), GrantLandTrust (#aileen, #janice)
h3  Watershed & Climate Services                -> grantsgateway, intechfund, livingshorelines, cbtrust.org (external), boating/Pages/pumpout/grants
h3  Tax Credit Programs
h3  Forest Service                              -> fcmp (http://), forestlegacy, tax (404)
h3  Maryland Environmental Trust                -> tax_benefits, a PDF
```

32 on-site links → 21 distinct `.aspx` pages after https / case / fragment normalization, 19 of them live; `tax.aspx`
and `mucfcgrant.aspx` are 404. Two `mailto:` links, one PDF and one external page (Chesapeake Bay Trust's Watershed
Assistance Grant Program, a real municipal program run by a nonprofit) are not records. The Waterway Improvement Fund
page `/boating/Pages/grants.aspx` is not linked from the index and is hand-added as `listed: false`.

Page skeleton as in `maryland_sharepoint.md`. Names: the `<h1>` on four Land Acquisition and Planning pages is the
unit ("Land Acquisition and Planning") and on the MET tax-benefits page it is empty; the program name is then the
first `<h2>` of the body. Every page has `<meta name="description">`.

### Status sentences seen (20 pages)

| Page | Sentence | Reading |
|---|---|---|
| Community Parks and Playgrounds | `The application period for the Fiscal Year 2028 Community Parks and Playgrounds Program grant is now closed.` | closed |
| Greenspace Equity | `The application period for the Fiscal Year 2028 Greenspace Equity Program grant is now closed.` | closed |
| LWCF | `UPDATE: The application period for LWCF grant funding is now closed.` / `Applications are not currently being accepted.` / `Check back in April 2027 for information about the next round of funding.` | forecasted (month kept as text) |
| Keep Maryland Beautiful | `Application period opens on September 3, 2026.` / `The Application deadline is December 1, 2026.` | open, 2026-09-03 to 2026-12-01 |
| Grants Gateway | `FY2028 Request for Solicitation OPENS on July 15, 2026` / `Beneficial Use Applications due: September 18, 2026 ...` / `All Other Applications due: December 11, 2026 ...` / `Shoreline Erosion Loan Applications due: through December 11, 2026* ...` / `*will be accepted on a rolling basis` / `The Waterway Improvement Fund (WIF) is no longer accepting applications through the Grants Gateway solicitation.` | open, closes 2026-12-11; not rolling; not closed |
| Waterway Improvement Fund | `Submit applications for State Waterway Improvement Funds via the link below by September 18, 2026, at 11:59 PM.` | deadline passed, no status wording: unknown, closes_at kept |
| Volunteer Fire Assistance | `The 2025 Volunteer Fire Assistance (VFA) Grant application period is now open and closes on September 15, 2025 at 4:00 p.m.` | open as the page says; the views drop it on the past date |
| Forest Legacy | `Applications are accepted on a rolling basis and evaluated annually.` | open, rolling |
| POS Local, Rural Legacy, CREP (both pages), cost-share, FCMP, pumpout, InTech, Living Shorelines, MET EE/CI/CU, land trusts, tax benefits | nothing about an application window | unknown |

## Enumeration and change detection

- `fetch()` GETs the index (non-200 aborts the run), walks its body: a heading that is one of the three section
  titles sets the section, any other heading is the unit for the links after it; every on-site `.aspx` link becomes an
  entry `{url, section, unit, listed: true}`; `HAND_ADDED` entries join with `listed: false`. Fragment-only variants
  of one page (`#eqip`, `#bill`) collapse onto it; a page linked from two sections keeps the first.
- Every page every run, 23 requests (index, 21 links, WIF). A 404 is skipped; other errors raise.
- The payload is the shared one plus `section`, `unit`, `listed`, stamped from the index, so a program moving between
  units or dropping off the index changes the record.
- `resolve_missing`: as the base. A de-listed page that still reads the same produces no change row.

## Field mapping

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `md_dnr` |
| name | `<h1>`, else first `<h2>` | the H1 unless it is a unit name (`UNIT_H1`) or empty, then the body's first H2 ("Community Parks and Playgrounds Program", "Program Open Space Local", "Tax Benefits of Conservation Easement Donations"); else the `<title>` |
| level / jurisdiction | constant | `state` / `MD` |
| administering_agency / agency_code | constant | `Maryland Department of Natural Resources` / `MD-DNR` |
| funding_type | name keywords, hand overrides | shared name keywords; POS Local → `formula` ("allocated annually to the 23 Maryland Counties and Baltimore City based on a formula"); else null |
| funding_source / alns | hand map, each quoted in the code | LWCF 15.916 ("administered nationally by the ... National Park Service"), Forest Legacy 10.676 ("a federal conservation easement program"), pumpout grants 15.616 ("funded by the Federal Clean Vessel Act"), Volunteer Fire Assistance 10.664 ("Federal funds will reimburse up to 50 percent"); all four listings verified on SAM.gov 2026-10-16. The rest `direct`. |
| amount_min / amount_max | none | null |
| match_required | shared wording over the body | null today |
| status | see decisions | first closed sentence → closed, then a future "check back in <Month YYYY>" / "next round" → forecasted; else first open sentence (not negated) → open, rolling on rolling wording; an application sentence with a deadline word and a full date gives `closes_at`; with no status wording the page is open while the latest such date is ahead and unknown after; else unknown |
| opens_at | "opens on <date>" sentence | full dates only; "April 2027" stays text |
| closes_at | application deadline sentences | the latest full date among sentences about applications or proposals carrying `due`, `deadline`, `closes on`, `submit ... by` or `must be submitted/received`, excluding report, notification and award sentences |
| closes_at_text | the sentences above | opens sentence, status sentence(s), deadline sentence(s), joined with a space |
| rolling | the open sentence | `rolling basis` / `year-round` → True, unless the page also states a dated deadline |
| summary | `<meta name="description">` | null: every DNR page carries the theme's site-wide boilerplate (`maryland_sharepoint.md`, decision 0) |
| eligibility_text | applicant sentences | sentences matching `eligible`, `may apply`, `available to`, `open to`, `applicant(s)`, `applications from`, minus negated ones; page order |
| applicant_types | keyword tags over the same sentences | shared table; `municipal` (added for milestone 7) catches CPP's "governing bodies of municipal corporations" |
| categories | unit | Land Acquisition and Planning → `parks`; Watershed & Climate Services and Boating Services → `water`; else `other`; `source_code` = the unit |

## Decisions

1. **"No longer accepting" is not a closed phrase here**, and an open phrase inside a negated sentence does not open
   a page. The Grants Gateway says "The Waterway Improvement Fund (WIF) is no longer accepting applications through
   the Grants Gateway solicitation" about a program that moved elsewhere; Commerce's `CLOSED_RE` would have closed the
   whole solicitation.
2. **A solicitation page's deadline is the latest application deadline on it.** The Gateway lists one per program
   (September 18 for beneficial use, December 11 for everything else). A rolling footnote on one of six programs does
   not make the solicitation rolling.
3. **Deadline sentences are about applications or proposals** and carry a deadline word; "You will be notified by
   October 15, 2025" and "Final grant reports are due ... by March 2, 2028" are not deadlines.
4. **Forecasted from a month.** LWCF: closed, "Check back in April 2027". The month-year is compared with today to
   choose forecasted over closed (DHCD's rule); no date is invented, `opens_at` stays null and the sentence is kept.
5. **Deadline-only pages** follow MEA's decision 4: open while the latest stated deadline is ahead, unknown after.
   WIF today: deadline September 18, 2026, no status wording, so `unknown` with `closes_at` kept.
6. **One record per page.** The MET Environmental Education page carries three named grants and the Gateway six
   programs; the registry's unit is the source record. Named sub-grants live in the summary and eligibility text.
7. **WIF is hand-added.** The roadmap names it; the index does not link it. `listed: false` keeps the fact visible.
8. **The base was extracted here** (`maryland_sharepoint.md`), with MEA's fixture hashes as the gate.

## Expected result (October 2026)

20 records. Open (4): Keep Maryland Beautiful (2026-12-01; municipalities), Grants Gateway (2026-12-11; no applicant
tags), Forest Legacy (rolling; private landowners), Volunteer Fire Assistance (the page still says "is now open" about
its 2025 round, closes 2025-09-15, so the views drop it). Forecasted (1): LWCF (April 2027; county, municipality,
state, tribe). Closed (2): Community Parks and Playgrounds (municipal corporations), Greenspace Equity. Unknown (13):
WIF (deadline 2026-09-18 passed, no status wording; local governments), POS Local (county formula), Rural Legacy,
both CREP pages, the Forest Service cost-share and FCMP pages, pumpout grants, InTech, Living Shorelines, the MET
environmental-education page (municipalities), the land-trust grants and the tax-benefits page.

Municipal open rows: Keep Maryland Beautiful and LWCF. CPP (closed, FY2028 round) and WIF (next round's date not yet
posted) are the ones to watch; both will show in the diff when their pages change.

## Fixtures

`tests/fixtures/md_dnr/`: `index__pages__grantsandloans.json` (url + the mdgov section);
`land__pages__programopenspace__cpp` (closed; unit H1 → program H2; "municipal corporations"),
`land__pages__lwcf-grants` (closed + "Check back in April 2027" → forecasted; government-entity list; pass-through),
`boating__pages__grants` (hand-added WIF; dated deadline past, no status wording → unknown; "local governments"),
`land__pages__programopenspace__home` (POS Local: no application wording; counties; formula),
`met__pages__grant_programs` (Keep Maryland Beautiful: dated window → open; municipalities),
`ccs__pages__funding__grantsgateway` (six deadlines, a rolling footnote and the WIF notice: open, 2026-12-11, not
rolling), `forests__pages__programapps__forestlegacy` (rolling; private land; pass-through),
`met__pages__tax_benefits` (empty H1 → H2 name; unknown), `land__pages__greenspace-equity-program` (closed; unit H1).
Written by `scripts/probe_maryland_sharepoint.py md_dnr`.
