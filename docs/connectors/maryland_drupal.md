# Maryland Drupal platform: the shared base under the state connectors

Milestone 4 pre-work, written 2026-10-15 before any code. The DHCD doc (`md_dhcd.md`) ended with a lead: Commerce,
the Maryland Historical Trust and the Department of Aging are Drupal 11 sites on the same `maryland-` theme as DHCD,
and if the DHCD parser generalizes, "the shared base class CLAUDE.md predicts for the third connector is a
Drupal-theme parser, not a SharePoint one". This doc records the check and what the base class is.

## Survey (live, 2026-10-15)

| Site | Sitemap | Non-media pages | `og:updated_time` | DHCD summary box | Labeled status field | Verdict |
|---|---|---|---|---|---|---|
| commerce.maryland.gov | yes, 1,532 URLs, every one with `lastmod` | 209 (76 after skipping press room, boards, contacts) | yes | none | **`<h2>Program Status</h2>`** as the first body section on 34 program pages under `/financial-incentives/` | **Build.** Connector 2. |
| mht.maryland.gov | yes, 673 URLs with `lastmod` | 302 (84 after skipping education-outreach, about, events, locations) | yes | 1 (a "now open" banner on the one open program) | **`<h2>Timeline</h2>`** bullets on 12 funding pages, plus a site-level **"Open funding opportunities"** list on `/funding/how-apply-grant` | **Build.** Connector 3. |
| aging.maryland.gov | yes, 101 URLs | 62 (35 after skipping news, about, test pages) | yes | none | none; one `/grants` page with a single FY27 notice in prose | Not a source yet. Revisit when it has two programs. |
| energy.maryland.gov (MEA) | **404** (SharePoint) | n/a | no | n/a | prose, hand-listed program URLs; some pages carry a `FY26 Program Status: The application portal is currently CLOSED to new applications.` sentence | Still deferred. No enumeration and no change-detection signal. Next lead after the Drupal sites; the "Program Status:" sentence is parseable. |
| dnr, mdot, mde, health.maryland.gov | 404 (SharePoint) | n/a | no | n/a | prose | Deferred, as in the DHCD doc. |

The CLAUDE.md candidate list (GGO, DHCD, MDOT, DNR, MEA) is exhausted after DHCD: GGO has no listing, the other three are
SharePoint prose. Commerce and MHT are picked instead because they are the two remaining Maryland agencies with a
labeled status or timeline field in stable markup, a sitemap with per-page `lastmod`, and the same page skeleton as
DHCD. MHT is also the more municipal of the two: local governments are eligible applicants on seven of its twelve
programs. Commerce is business-facing with two exceptions (Advantage Maryland names "counties, municipalities";
Enterprise Zones are designated for local jurisdictions).

## What the three sites share (verified on every crawled page)

- `sitemap.xml` with `<loc>` and `<lastmod>` per page. Enumerate from it; skip paths that are never programs.
- `<main>` wrapping the page; `<h1>` is the program name; `<meta name="description">` is the summary;
  `<meta property="og:updated_time">` moves when the page is edited.
- Body in `<div class="usa-prose maryland-toc-target">` organized by `<h2>` sections. Eligibility sections are headed
  `Eligible applicants`, `Who is eligible to apply?` (DHCD), `Who Can Apply`, `Who This Is For` (Commerce),
  `Eligible applicants`, `Eligibility` (MHT).
- Optional `div.maryland-summary-box` component (DHCD uses it for Application status; MHT for a "now open" banner).
- robots.txt permits crawling; 0.3 s between requests keeps a full crawl under a minute per agency.

## What differs (one hook each)

| Concern | DHCD | Commerce | MHT |
|---|---|---|---|
| Is this page a record? | box has a status-type label | body has a `Program Status` section | body has `Timeline` and an eligibility section |
| Status | box status value | first closed/open phrase in the Program Status text | site-level open list, "now open" banner, or year-round wording; otherwise closed |
| Dates | box date lines | dated sentences in the Program Status text | "Applications close on <date>" in the banner; timeline months stay text |
| Amounts | null | null | `Available funding`: "up to $X" or one "$A to $B" range |
| Applicant scan headings | eligibility headings minus thing-headings | `Who ...` headings | `Eligible applicants`, `Eligibility` |
| Extra fetch | none | none | `/funding/how-apply-grant` for the open list, stamped onto every payload as `listed_open` |

## Base class

`connectors/maryland_drupal.py: MarylandDrupalConnector`. Class attributes carry the per-agency constants
(`CONNECTOR`, `BASE`, `AGENCY`, `AGENCY_CODE`, `SKIP_PATH`, `SECTION_CATEGORIES`, `PASS_THROUGH`,
`APPLICANT_HEADING_RE`, `THING_HEADING_RE`). Shared, not overridden: sitemap enumeration, the `lastmod` refetch gate,
`page_payload`, the `fetch` loop, `resolve_missing`, `body_sections`, eligibility text, applicant tagging, match
wording, funding type from the name, categories from the first URL segment, and `normalize`. Overridden per agency:
`is_record(payload)`, `status_fields(payload, today)` (status, opens_at, closes_at, closes_at_text, rolling),
`amounts(sections)`, and for MHT `before_fetch(client)` / `annotate(payload, context)`.

Each connector module keeps the pipeline contract as module-level `fetch`, `normalize`, `resolve_missing` bound to
one instance, so `pipeline/run.py` and the CLI do not change. The pure helpers DHCD's tests import
(`iter_sitemap`, `parse_box`, `parse_box_date`, `status_for`, ...) stay importable from `connectors.md_dhcd`.

Rule for the refactor: DHCD record hashes on the seven fixtures must be identical before and after, except where the
shared applicant keyword table gains entries (tribe, state agency, higher education, not-for-profit) that DHCD text
happens to contain; the test run says which.

## Applicant lines (added during implementation)

The first live run of Commerce put six business tax credits in the municipal `likely` tier: their "Who This Is For"
sections mention places ("4+ cities outside Maryland", "within a Tier 1 County", "incorporated municipalities") and
conditions ("local government approval (municipality or county resolution)"), and the keyword scan read those as
applicants. The sections on all three sites have the same shape: the applicant statement first, then a list of
conditions, then definitions. So the scan now reads lines, not whole sections (`applicant_lines` in the base):

- the first line of a who-section is the applicant statement whatever it says; list items at the top are introduced
  by the heading ("Eligible applicants" → "Local governments");
- a later paragraph counts only if it talks about applying or qualifying (`APPLICANT_MARKER_RE`), and a paragraph
  ending in a colon introduces applicant list items ("an applicant must be either:") unless it ends with a
  condition word ("businesses that:", "your company:"), where the scan stops for that section;
- a negated line never counts ("For-profit businesses are not eligible to apply."), and neither does a negated
  heading ("Who is not eligible to apply?");
- a place word right after a spatial preposition is a place ("located in a designated rural county");
- the section heading is itself the first line ("Household eligibility requirements" names the applicant).

Effect on DHCD, re-normalized from the stored live payloads: 7 local-government programs tagged as before; CDBG
loses the `county` tags it took from the entitlement-county list under "Who is not eligible"; NourishMD gains
`for-profit` and loses a `county` from "located in a designated rural county"; MEAP and Housing Rehabilitation
lose their one `household` tag (both are "you must:" condition lists, which name no applicant type), so 9 DHCD
records are untagged instead of 7. All on the side of reading less into the page. Commerce: 2 records carry
local-government tags, both correct. MHT: 8 of 11.

## Applicant keyword table (shared; additions for milestone 4 marked, milestone 7 in italics)

`units? of (general )?local government`, `local governments?` → municipality, county; `municipalit\w*`, *`municipal`*, `cities`,
`towns?` → municipality; `count(y|ies)` → county; `non-?profits?`, `501(c)(3)`, **`not-for-profit`** → nonprofit;
`for-profits?`, `business(es)?`, `retailers?`, `developers?` → business; `homeowners?`, `households?`, `residents?`,
`renters?` → household; `individuals?` → individual; `housing authorit\w*` → housing_authority; `schools?`,
`local education agenc\w*` → school; **`tribal|tribes?`** → tribe; **`state (government )?agenc\w*`** → state;
**`colleges?|universit\w*|institutions? of higher education`** → higher_ed. Scanned over the who-may-apply sections
only; the matched phrase is stored as `source_code`.

Milestone 7 added `\bmunicipal\b` (2026-10-16): MEA writes "county and municipal governments" and DNR "the governing bodies
of municipal corporations", neither of which `municipalit\w*` matches. Ripple on the three Drupal connectors, measured
by re-running them on a database loaded that morning: one change, the Town Manager Circuit Rider Program ("Municipal
governments, county governments or private organizations may sponsor") gains a municipality tag, which is correct;
Commerce and MHT unchanged.
