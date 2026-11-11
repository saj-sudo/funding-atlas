# Missouri's agency pages (`mo_ded` so far): source, raw data and field mapping

Milestone 12.6e, the fifth agency state in the 12.6 cost ranking (after Vermont, Connecticut, North Dakota and Kentucky).
Written 2026-11-11 from a read-only survey of the candidate agencies' hosts and pages, before the parser. The agencies
are built one at a time, each its own commit; this doc grows with them.

## Survey (2026-11-11, the connectors' own User-Agent, one GET per page, 1.5 s apart)

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Economic Development (DED) | `ded.mo.gov` | Drupal 10, Layout Builder (`.node__content`) | allows all | **built** (this doc) |
| Transportation (MoDOT) | `www.modot.org` (the apex redirects) | Drupal 10 | blocks only `/media/oembed` | next |
| Natural Resources (DNR, with Energy) | `dnr.mo.gov` (`energy.mo.gov` redirects to `/energy`) | Drupal 10 | blocks `/taxonomy/` | next |
| Emergency Management (SEMA) | `sema.dps.mo.gov` | not Drupal, an older CMS with `.php` pages and no `.node__content` | blocks only legacy directories | next, its own reader |
| Housing (MHDC) | `mhdc.com` | no generator tag | no `robots.txt` (404) | deferred: its own CMS, mostly developer tax credits |
| Conservation (MDC) | `mdc.mo.gov` | Drupal 10 | **`Disallow: /`** in at least one agent block | **stopped** on robots, as ADECA was; recorded, not read |

## Implemented, DED (2026-11-11)

`connectors/missouri_drupal.py` (the base) and `connectors/mo_ded.py` follow this doc. First live run on an empty
database: **7 added, 0 errors**; second run **0 changed**. Open: Downtown Revitalization and Industrial Infrastructure
(year-round, "until funding is exhausted"), the Emergency cycle and the Water/Wastewater program ("currently open");
closed: the Competitive Cycle's three programs ("FY26 ... Application is now closed", the FY27 date not set).
Applicants tagged: Downtown Revitalization and Emergency (`municipality`, `county`). The other five pages name no
applicant in the text the connector reads, so they carry none (see Gaps).

Shared changes (two phrasings in `connectors/hand_list.py`), measured on the database restored from `gh-pages` (7,630
stored records, 39 connectors) with `scripts/measure_tagger.py`: **0 tag moves, 0 hash moves**.

- `AGENCY_OPEN_RE` reads "is currently open" ("The Emergency Cycle is currently open."); without it both DED pages
  that say so were `unknown` while the source said open.
- `ELIGIBILITY_LABEL_RE` reads the heading "Do I Qualify?" as the eligibility section, which DED's pages use for it.

## The platform

DED, MoDOT and DNR run the state's Drupal 10 theme. The page's text sits in `.node__content`: an `.alert` block with the
status, then tabbed `h2` sections ("Description", "Do I Qualify?", "How Do I Apply?", "Need Help?"), all in the static
HTML. The `h1` is printed twice on DED's pages, the department's name and then the program's, so the title is the last
`h1`. `/cdbg/opportunities-to-apply` lists the CDBG pages; `/program-lookup` is a paginated Views list (10 a page) of every
DED program, most of them business tax credits and incentives, which are not read.

## The pages (DED)

| slug | path | what it is | records |
|---|---|---|---|
| `competitive-cycle` | `/programs/community/community-development-block-grants-competitive-cycle` | Community Facilities, General Infrastructure, Demolition | 3 |
| `economic-development` | `.../community-development-block-grants-economic-development` | Downtown Revitalization, Industrial Infrastructure | 2 |
| `emergency` | `.../community-development-block-grants-emergency-long-term-recovery` | the emergency cycle | 1 |
| `water-wastewater` | `.../community-development-block-grants-waterwastewater` | the Water/Wastewater program | 1 |

Left out (Saj to overrule, see Decisions): `.../community-development-block-grants-disaster-recovery`, `...-mitigation`
and `...-covid-19`, and `/programs/community/community-development-block-grants` (it redirects to `/cdbg`, which carries
public notices and no program).

## Raw samples (verbatim, 2026-11-11)

The status is the page's alert block:

```
Competitive Cycle:     <p>FY26 CDBG Competitive Cycle Application is now closed.</p>
Economic Development:  <p><strong>Currently Accepting Applications!</strong></p><p>This is an open, year-round cycle.
                       Applications will be accepted until funding is exhausted.</p>
Emergency:             The Emergency Cycle is currently open.
Water/Wastewater:      The Water/Wastewater Program is currently open. To apply, a community must go through the Missouri
                       Water Wastewater Review Committee to receive an invitation to apply for CDBG funds.
```

The applicants, where a page says who:

```
Economic Development, "Do I Qualify?", Downtown Revitalization:
  Eligible applicants include non-entitlement cities and counties. Counties may apply on behalf of no more than one
  target area within their boundaries, if applying under one application.
Emergency, "Do I Qualify?":
  The recipient is a non-Entitlement Unit of General Local Government within the State of Missouri
```

## Field mapping

The agency-page table in `connectors/hand_list.py` (`AgencyPageConnector`), with the Missouri base's page reader.

| Field | From |
|---|---|
| `source_url` | the page's URL (a page with several programs shares it) |
| `name` | the program heading for a split page ("CDBG Community Facilities"), else the page's program `h1` |
| `status`, `closes_at` | the shared round table over the page's own sentences: a deadline ahead is `open`, closed wording is `closed`, open wording with no date is `open`, nothing is `unknown` |
| `applicant_types` | the shared tagger over the "Do I Qualify?" and eligibility lists and the sentences that name an applicant |
| `funding_type`, `funding_source` | `grant`; `pass_through` for every DED record (`FUNDING_SOURCES`, see Decisions) |
| `match_required` | a "match ... required" sentence (Downtown Revitalization's 20%); null when the page says nothing |
| `categories` | `community development` through the shared portal table |
| `summary` | the first paragraph that is not a status line |

A page that names its programs twice (Competitive Cycle, Economic Development) is cut by `join_tabs` in the base: each
tab is split at the program headings on its own and a program's description and qualifying text are joined, so a record
is one program, not the first tab run into the second. The first program keeps the page's own `source_id`, the others are
`slug#program`.

## Decisions

1. **Municipal programs only.** DED's `/program-lookup` lists business tax credits, incentives and broadband programs;
   none is read. The four CDBG pages that take applications from communities are.
2. **Disaster Recovery, Mitigation and COVID-19 are left out** (the Kentucky CDBG-DR precedent, 2026-11-11). Their pages
   say "Disaster funding is exhausted", "CDBG Mitigation funds have been exhausted" and "not currently accepting
   applications": closed for good, so they would be rows that never open. Saj can overrule; adding one is a line in
   `PAGES` and a fixture.
3. **Every DED record is `pass_through`.** The CDBG State program is HUD money the state passes to non-entitlement
   communities. Only the pages that print "HUD" in the section a record owns said so, which made one HUD program read as
   two funding sources; the funding source is set per record instead of guessed from the text.
4. **Industrial Infrastructure is read as a community program**, not a business one: the page's own sentence is "The local
   government applicant must provide ...", the businesses are beneficiaries. The tagger does not read "local government
   applicant" (see Gaps), so the record names no applicant rather than naming the wrong one.
5. **`records_for` is overridden in the base, not in `hand_list.py`** (`join_tabs`): one state, one page template, and the
   repo's rule is no abstraction before a third case. If DNR or MoDOT pages turn out to use two tabs too, it moves.

## Gaps (recorded, not hidden)

- Five of seven DED records tag no applicant: Community Facilities, General Infrastructure, Demolition and Water/Wastewater
  never name one in the text read (CDBG's eligible applicants are non-entitlement cities and counties, which the
  guidelines PDFs say and these pages do not), and Industrial Infrastructure says "The local government applicant".
  A hand quote from the guidelines is possible if one is open and would put a row on a page (Saj's rule, 10.6): none was
  open on 2026-11-11 except Water/Wastewater, which is invitation-only through the Review Committee.
- The water page's "Applicants must be sure that the project beneficiaries are at least 51% low-to-moderate income
  persons." is kept as an eligibility line by the shared `applicants must be` phrasing; it states a condition, not an
  applicant, and tags nothing.
- The Competitive Cycle's FY27 date is "TBD" on the page, so no opening date is stored.
