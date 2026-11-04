# Vermont's municipal four (`vt_accd`, `vt_vtrans`, `vt_fpr`, `vt_vem`): source, raw data and field mapping

Milestone 12.6, the first agency state. Written 2026-11-04 from a read-only probe of the four agencies, before the
parser. The 12.6 ranking (same day) put Vermont cheapest: four agencies that matter to a town (community development,
transportation, parks and recreation, emergency management), all on the same vermont.gov Drupal 10 theme, about
seventeen program pages, and most of their rounds closing between November 2026 and February 2027. Vermont's eGrants
is an IntelliGrants login (12.0) and is not needed: every round below is announced on the agency's own page.

## Implemented (2026-11-04, same day)

`connectors/vermont_drupal.py` and the four agency modules follow this doc. First live run on a fresh database: 17
added in about ten seconds (6 ACCD, 5 VTrans, 3 FPR, 3 VEM), 0 errors; second run 0 changed. Open: VCDP (no date),
Municipal Planning Grant (to 2026-12-02), TAP and MHSMP (to 2026-12-04), Better Roads (to 2026-11-20), RTP and LWCF
(pre-applications to 2026-11-20), VOREC (to 2026-12-13); closed: Downtown Transportation Fund, Grants in Aid; the rest
`unknown`. The Vermont page: 4 agencies, 17 programs, 6 open municipal rows, 3 between rounds. Found while writing
the parser:

- the first `.field--name-body` on a page is often an empty sidebar block; the body is the main block's;
- VTrans writes its intro sentences bold, so "grant funding to municipalities" sat in label blocks the shared
  `label_lines` never reads for sentences; Vermont reads applicant sentences from every block;
- VCDP's eligibility sentence carries "(except Burlington)", and the shared negation guard dropped the whole
  sentence; the parenthetical is removed before tagging (the text is stored as written);
- VOREC's example projects mention a "FEMA buyout property"; FPR's own "Funding source:" line now decides;
- Hazard Mitigation's first sentence with "deadline" and a date was a 2024 notice about changed deadlines; a deadline's
  date must sit within 40 characters of its word;
- TAP and MHSMP name no applicant on the page (open rows the municipal page does not show).

## The platform

Every agency site is vermont.gov's Drupal 10 USWDS theme: the page title is the `h1`, and the page's own text is the
body field of the main content block, `.block-system-main-block .field--name-body`. (Other `.field--name-body`
elements sit in sidebar blocks, often empty; the first one on the page is not the body.) Inside the body the agencies
write `h2`-`h4`, `p` and `li`, with bold one-line paragraphs as labels. `robots.txt` on all four hosts is Drupal's
standard file (admin paths only). Two kinds of block are not the program: VTrans's accessibility notice ("The Agency of
Transportation is committed to ensuring accessibility ...") at the top of every page, and contact lines (a name with
"Telephone:" or an `@vermont.gov` address). Both are dropped before anything is read.

Because the four agencies share the theme, the page reader, the status table and the field mapping live in one base,
`connectors/vermont_drupal.py` (`VermontAgency`, on `connectors/hand_list.py`'s `HandListConnector`), and each agency is
a module of constants and a page dict: the Maryland Drupal pattern, forced by four sites at once.

## The pages (2026-11-04)

| Connector | Agency (code) | Category label | Pages |
|---|---|---|---|
| `vt_accd` | Agency of Commerce and Community Development, Department of Housing and Community Development (`VT-ACCD`) | community development | VCDP (CDBG), CDBG-DR, Downtown Transportation Fund, EVSE Grant Program, Municipal Planning Grant, Bylaw Modernization Grants |
| `vt_vtrans` | Agency of Transportation (`VT-VTRANS`) | transportation | Transportation Alternatives, Municipal Highway and Stormwater Mitigation, Grants in Aid, Better Roads, Bicycle and Pedestrian |
| `vt_fpr` | Department of Forests, Parks and Recreation (`VT-FPR`) | recreation and conservation | VOREC Community Grant Program, Recreational Trails Program, Land and Water Conservation Fund |
| `vt_vem` | Vermont Emergency Management (`VT-VEM`) | emergency management | EMPG, Hazard Mitigation Funding Programs, Public Assistance |

Left out, on purpose: ACCD's Community Investment Program (designations, not a grant), the tax credits, TIF and the
sales tax reallocation (not grants to a town), the Northern Border Regional Commission (a federal commission with its
own site); VTrans's HSIP page (answered 403 with a generic VTrans page); FPR's Forest Legacy (state acquisition) and
the links to other organizations (Communities Caring for Canopy, Working Lands). Hazard Mitigation is one page that
describes HMGP, BRIC, FMA and the Flood Resilient Communities Fund together; it is one record, as the page is.

## Round sentences, as the pages write them

- FPR, all three: a status list at the top, "Current status: 2027 grant round is now open. Pre-Application materials
  are due November 20, 2026", and a timeline: "Pre-applications open and application materials released by September
  29, 2026", "Pre-application submission deadline: November 20, 2026", "Full application submission deadline: January
  31, 2027". (VOREC: due December 13, 2026; full application February 17, 2027.)
- ACCD Municipal Planning Grant: a timeline of label lines, "October 1, 2026 - Application Opens", "December 2, 2026 at
  6 p.m. - Application Due", then grant term and closeout dates.
- ACCD VCDP: "CDBG FY26 Pre-Applications are now open." No date on the page (they are on the Applicant Guidance page).
- ACCD Downtown Transportation Fund: "The application period for the 2026 Downtown Transportation Fund grant is now
  closed".
- VTrans TAP and MHSMP: one link text on both pages, "TAP and MHSMP Fillable Grant Application 2027 Applications due
  December 4th, 2026".
- VTrans Better Roads: "FY2028 Better Roads Category B,C,D Solicitation is now open." and "DEADLINE EXTENDED!
  Applications due 11/20/2026." (the only numeric date).
- VTrans Grants in Aid: "FY27 Grants-in-Aid program application period is closed" and "Letters of Intent were due on
  May 1st, 2026".
- VEM EMPG: "The EMPG 25 RPC Subgrant Application period opened on August 7th, 2025". Hazard Mitigation: "State
  application deadline: May 15, 2026". Public Assistance: none.
- ACCD CDBG-DR, EVSE, Bylaw Modernization ("had funding to grant", past tense), VTrans Bicycle and Pedestrian: none.

## Field mapping

| Program field | From |
|---|---|
| `source_id` | the page slug (`vcdp`, `transport-alt`, `recreational-trails-program`, `mitigation`) |
| `source_url` | the agency host plus the path |
| `name` | the `h1` |
| `level`, `jurisdiction` | `state`, `VT` |
| `administering_agency`, `agency_code` | the agency's constants above |
| `funding_type` | `funding_type_for(name)`, else `grant` |
| `funding_source` | `pass_through` when the page names the federal source (Federal Highway Administration, FHWA, FEMA, HUD, National Park Service, "federally funded"), else `direct` |
| `status`, `opens_at`, `closes_at`, `closes_at_text`, `rolling` | the Vermont table below |
| `match_required` | true when the page says a match is required ("20% match required", "require a 25% local match"); else null |
| `summary` | the first paragraph that is not a status line |
| `eligibility_text`, `applicant_types` | the lines under an eligibility label ("Eligible applicants:", "Applicant Eligibility", "Who is eligible to apply") plus the sentences that say who may apply ("available to municipalities", "limited to municipalities", "grant funding to municipalities"), through the shared tagger |
| `categories` | the agency's label through the shared table (`community development` infrastructure, `transportation`, `recreation and conservation` parks, `emergency management` public safety) |

## The Vermont status table

Read over every sentence of the page's blocks, in page order:

1. **The deadline**: the first sentence that says due or deadline with a date (a closeout, report or grant-term date is
   not a deadline). FPR's first is the pre-application deadline: that is the date a town has to act by, so it is the
   one stored; the full-application deadline is for those invited. Dates are "Month D, YYYY" (an ordinal or a weekday
   allowed) or "M/D/YYYY".
2. **The opening**: the first sentence that says applications open, or open "by" a date, with a date.
3. A deadline still ahead: `forecasted` when the opening date is also ahead, else `open`.
4. Otherwise closed wording ("is now closed", "is closed", "closed for applications") is `closed`.
5. Otherwise a deadline that has passed is `unknown` (Hazard Mitigation): a past date says the last round ended, not
   that there is no round. It outranks undated open wording, which a page keeps until someone edits it (RTP's "2027
   grant round is now open" the day after its pre-application deadline).
6. Otherwise open wording ("now open", "accepting applications"), not negated, is `open` with no date (VCDP).
7. Otherwise `unknown`.

`closes_at_text` is the sentence that decided; `rolling` is null throughout (no page says year-round).

## Decisions

1. **One base for four agencies** (`vermont_drupal.py`), each agency its own connector: a town reads "VTrans" on the
   page, and a broken page at one agency must not touch the other three.
2. **The pre-application deadline is `closes_at`** where a page states both stages.
3. **A future deadline with no opening sentence is open** (TAP, MHSMP): the application form for that round is posted
   on the page.
4. **One record per page**, Hazard Mitigation included.
5. **Scope is the municipal four**; Vermont's Public Service Department (energy) was not probed and is a later addition.
