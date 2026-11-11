# North Dakota's municipal four (`nd_commerce`, `nd_dot`, `nd_des`, `nd_parks`): source, raw data and field mapping

Milestone 12.6c part 2, the third agency state (the 12.6 cost ranking's third, after Vermont and Connecticut). Written
2026-11-11 from a read-only probe of the four agencies' pages, before the parser. Part 1 (2026-11-05) put the state's
WebGrants storefront, `grants.nd.gov`, on `webgrants`; a round an agency posts there is read there.

## Implemented (2026-11-11)

`connectors/north_dakota_drupal.py` and the four agency modules follow this doc. First live run, on the database
restored from `gh-pages`: 16 added (8 Commerce, 4 NDDOT, 2 DES, 2 Parks), 0 errors; second run 0 changed. Open: the
Urban Grant Program (to 2026-12-31); closed: seven of Commerce's eight (each page says "now closed"); `unknown`: Partners
in Planning, the Flex Fund and Transportation Alternatives (past deadlines), the Special Road Fund (solicits "when there
is adequate funding"), DES's two (disaster-driven), LWCF ("Next grant round opens: TBD") and RTP (no round on its page).
The North Dakota page: UGP as an open likely row beside FIND; 6 between rounds (the Flex Fund and five CDRP grants).
Vermont's and Connecticut's 31 fixtures produce identical `record_hash` before and after every shared change, on both
capture dates (scripted; 62 hashes).

Found while writing the parser:

- Commerce writes `<li><strong>Eligible Entities</strong> – City, County, ...</li>`; the hand-list reader takes a list
  item's own text, which lost the bold label. The ND reader unwraps inline tags inside a list item with no nested list.
- Parks heads its applicant lists with a plain paragraph ending in a colon ("The following entities are eligible to
  apply:"); the ND reader reads a short paragraph ending in a colon as a label.
- NDDOT's TA page says plans must be "completed and submitted by January 1, 2028" (a construction milestone), which the
  shared table read as the deadline. "submitted by" is now a deadline word only in a sentence that mentions an
  application (Connecticut DEEP's "Applications must be submitted by" still is).
- Six applicant phrasings and one federal wording added to the shared table (below), with Vermont and Connecticut held
  to identical hashes. A first, unanchored "eligible entities" moved Connecticut's SLCGP (its statute quote, "award
  grants to eligible entities", joined the eligibility text; tags unchanged), so the rule only reads a line that
  starts with "Eligible Entities".

## The platform

All four agencies run the state's `ndit_base` Drupal 11 theme on Layout Builder (generator tag "Drupal 11",
`body.page-node-type-page`, assets under `/themes/custom/ndit_base/`). There is no `field--name-body`: the page's own
text sits in `.node__content` as WYSIWYG (`block-inline-blockndit-wysiwyg`), accordion (`ndit-accordion`, Bootstrap
`.accordion-item`) and tab (`ndit-tabs`) blocks, all in the static HTML; collapsed tabs and accordions need no
JavaScript. `main` is not the container: DES puts its side menu inside `main`. Every host serves the standard Drupal
`robots.txt`; no target page needs a login.

The page reader (`connectors/north_dakota_drupal.py`): title from `h1`; blocks `h2, h3, h4, p, li` from
`.node__content`; dropped: contact lines ("Phone:", "TTY", "Email:", `@nd.gov`, DES's "T: 701.328.8100" address blocks)
and the theme's "Copy Link"; the read stops at the first heading that starts a past-awards or link list ("Prior Year
Projects", "... Awarded Projects", "... grant recipients ...", "Resources", "Related Links"), so the towns that won last
round never reach the tagger.

## The pages (2026-11-11)

| Connector | Agency (code) | Category label | Pages |
|---|---|---|---|
| `nd_commerce` | Commerce, Community Development and Rural Prosperity (`ND-COMMERCE`) | community development | Vibrancy, Rural Slum and Blight Removal, Rural Workforce Housing, Rural Facility Planning, Partners in Planning, Artists on Main Street, Rural Catalyst, Rural Grocery Store Sustainability |
| `nd_dot` | Department of Transportation (`ND-DOT`) | transportation | Flexible Transportation Fund, Transportation Alternatives, Urban Grant Program, Special Road Fund |
| `nd_des` | Department of Emergency Services (`ND-DES`) | emergency management | Public Assistance, Unified Hazard Mitigation (HMGP, BRIC, FMA: one page, three records) |
| `nd_parks` | Parks and Recreation Department (`ND-PARKS`) | parks and recreation | Land and Water Conservation Fund, Recreational Trails Program |

URLs: Commerce's eight are under
`https://www.commerce.nd.gov/community-services/community-development-rural-prosperity/cdrp-resources/`, as
`cdrp-grant-programs-0` to `-6` and `cdrp-grant-programs/rural` (Rural Grocery). The roadmap's bare
`/cdrp-grant-programs` is a 404, and the index page at `.../cdrp-resources/cdrp-grant-programs` links no program (the
eight are in the section menu). NDDOT: `/flexfund`, `/construction-and-planning/transportation-plans-programs/
transportation-alternatives-ta`, `/construction-and-planning/urban-grant-program-ugp`, `/construction-and-planning/
construction-planning/programs-and-planning/special-road-fund-program`. DES: `/recovery-mitigation/public-assistance`,
`/recovery-mitigation/unified-hazard-mitigation-grant-assistance`. Parks: `/business/grants/
land-and-water-conservation-fund`, `/business/grants/recreational-trails-program`.

## Raw samples (verbatim, 2026-11-11)

- Commerce, Rural Catalyst: "Application Window is now closed"; "Eligible Entities – Political subdivisions, Tribal
  entities, and Regional Councils"; "Applications will be accepted for submission on October 28th, 2025 The application
  window will close on January 7 th , 2026. If there are remaining funds, a second round will be opened on March 2 nd ,
  2026 and will close on April 15th, 2026."; "This marks the final round of funding under SB 2390".
- Commerce, Rural Grocery: "Application period is now closed!"; "Eligible Entities: Political subdivisions, regional
  councils, and tribal entities"; dates with no year ("beginning Wednesday, July 9 at 3 PM CDT").
- NDDOT, Flex Fund: "This program is open to non-oil townships for transportation related projects." ... "Applications
  Due September 19, 2025".
- NDDOT, TA: "Eligible Project Applicants" over a list; "Deadline for Transportation Alternatives Program Applications:
  December 31, 2025" beside 2026 MPO submittal dates and an FY 2029 guidance document.
- NDDOT, UGP: "provides an opportunity for cities with a population of over 5,000"; "Deadline for Urban Grant Program
  Applications: December 31, 2026"; "This program is funded with federal aid."
- DES, Public Assistance: "Under the Public Assistance (PA) Program, FEMA provides supplemental aid to state, local,
  tribal and qualified Private Non Profit (PNP) organizations."
- Parks, LWCF: "Next grant round opens: TBD"; "The following entities are eligible to apply:" over "Cities, counties,
  and townships / Park boards and park districts / School districts / State agencies / Water management districts /
  Federally-recognized Indian tribes".

## Field mapping

The agency-page table in `connectors/hand_list.py` (Vermont's, moved there for Connecticut), unchanged in shape:

| Field | From |
|---|---|
| `name` | the `h1` |
| `source_url` | `BASE + path` |
| `status`, `opens_at`, `closes_at`, `closes_at_text` | `round_for`: a deadline ahead (`forecasted` before an opening date), closed wording, a past deadline (`unknown`), undated open wording, else `unknown` |
| `applicant_types`, `eligibility_text` | short items under an applicant label, plus the applicant sentences anywhere; the shared tagger |
| `funding_source` | a "Funding source:" line, else federal wording on the page (FHWA, FEMA, NPS, HUD, "funded with federal aid") |
| `match_required` | "match ... required" / "requires ... match" |
| `categories` | the agency's category label through `PORTAL_CATEGORIES` |
| `summary` | the first paragraph that is not a status line |

Added to the shared table this session (each one quoted from a page above): applicant labels "Eligible Project
Applicants" and "... entities are eligible ..."; applicant sentences a line starting "Eligible Entities", "program is open
to", "projects identified by", "an opportunity for <up to two words> cities/counties/towns/townships/municipal...",
"provides <a word> aid to"; federal "funded with federal aid"; "submitted by" needs an application in the sentence.

## Per page (2026-11-11)

| Page | Status | Applicant tags |
|---|---|---|
| Vibrancy | closed | nonprofit, municipality, county (10.6) |
| Slum and Blight, Workforce Housing, Facility Planning, Rural Grocery | closed | municipality, county, tribe |
| Rural Catalyst | closed | municipality, county, tribe, special_district (10.6: job development authority) |
| Partners in Planning | unknown | none |
| Artists on Main Street | closed | none |
| Flex Fund | unknown (2025-09-19) | municipality, county |
| Transportation Alternatives | unknown | municipality, county, school, tribe, special_district (10.6) |
| Urban Grant Program | open (2026-12-31) | municipality |
| Special Road Fund | unknown | municipality, county, tribe, state |
| Public Assistance | unknown | tribe, state (10.6) |
| Hazard Mitigation | unknown | municipality, county, nonprofit (10.6) |
| LWCF | unknown | municipality, county, school, state, tribe, special_district (10.6) |
| RTP | unknown | municipality, county, nonprofit, tribe, special_district (10.6) |

## Decisions

1. One ND base for four hosts, the Vermont pattern (`BASE` in each agency module), because the theme is shared and the
   hosts are not.
2. The Flex Fund page holds three grants (non-oil townships $31.1M, non-oil counties and cities $44.85M, bridges
   $40.25M). Saj's first call (2026-11-11) was one record; **the same day Saj reversed it: a page that holds several
   programs is one record per program.** `nd_dot` and `nd_des` set `SPLITS` (`connectors/hand_list.py`): Flex Fund is
   `flex-fund` (townships, keeps the old id), `flex-fund#counties-cities` and `flex-fund#bridges`; Unified Hazard
   Mitigation is `hazard-mitigation` (HMGP), `#bric` and `#fma`. The Flex Fund's "Prairie Dog as Grants" note (where
   the money comes from, naming every applicant type) and DES's "For more information" link are in no record; the
   text above the first heading follows every section. Effects: the bridges grant tags `county` only and has no
   deadline (the 2025-09-19 date is the townships' and the counties-and-cities'); BRIC and FMA tag nothing, because
   their sections name no applicant (they used to borrow HMGP's). The page's 16 records become 20.
3. All eight CDRP pages go in, the dormant three included (Rural Catalyst's "final round under SB 2390", Partners in
   Planning "contingent upon State Legislative funding", Artists on Main Street a 2022-2023 pilot) (Saj's call,
   2026-11-11): each shows what its page says, and the change feed catches a reopening.
4. TA's headline deadline (2025-12-31) is stale beside 2026 MPO dates; the page's own date stands and the record is
   `unknown`. The date sits 55 characters from "Deadline" (past the table's 40-character window), so `closes_at` is
   null; widening the window for every state was not worth one stale date.
5. No double count with WebGrants: on 2026-11-11 the storefront's North Dakota rounds are Honor Guard Stipends and FIND;
   neither LWCF nor RTP is posted there. If Parks posts a round, the round is a `webgrants` record and the page a
   program, as with FIND.

## Known gaps (recorded, not fixed)

- HMGP's page names no federal agency, so the record is `direct` (the table's rule: a page must name its federal source);
  BRIC and FMA name no applicant. (Fixed 2026-11-11, roadmap 10.6: "All eligible jurisdictions and private not-for profit
  (PNP) entities may submit" is now an applicant sentence and tags municipality, county and nonprofit; "not-for profit"
  with a space is no longer read as a negation.) DES's detail links (`grants.des.nd.gov/site/PA.cfm`, `HM.cfm`) are 404, and that host serves
  `Disallow: /`.
- (Fixed 2026-11-11, roadmap 10.6.) "local political entities" (Vibrancy: municipality, county), "park districts",
  "water management districts" (LWCF, RTP), "Transit agencies" (TA) and "job development authority" (Rural Catalyst:
  `special_district`); Public Assistance gains `state`. Still not read, on purpose (Saj's call): "local" alone. Townships
  tag as municipality, the tagger's existing reading.
- Dates live in PDFs: Parks' FY27 timeline, Partners in Planning's guidance, Artists on Main Street's guidelines (which
  also hold its applicants). Rural Grocery's dates carry no year.
- Facility Planning's "Minimum of a 10% match" does not say "required", so `match_required` is null.
