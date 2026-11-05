# Connecticut's municipal four (`ct_doh`, `ct_dot`, `ct_deep`, `ct_demhs`): source, raw data and field mapping

Milestone 12.6b, the second agency state (the 12.6 cost ranking's second, after Vermont). Written 2026-11-04 from a
read-only probe of the five agencies a town deals with, before the parser.

## Implemented (2026-11-05)

`connectors/connecticut_portal.py` and the four agency modules follow this doc. First live run on a fresh database: 14
added (1 DOH, 4 DOT, 2 DEEP, 7 DEMHS), 0 errors; second run 0 changed. Open: OSWA (to 2026-11-06) and Urban Green (to
2026-12-04); closed: CCGP; `unknown`: Small Cities (past deadline) and the rest (no round stated). Applicants: Small
Cities, LOTCIP, the Municipal Grant Program and HMGP municipality; OSWA and Urban Green municipality and nonprofit; BRIC
municipality and nonprofit; the State and Local Cybersecurity program municipality, county and tribe; EMPG and HSGP
nothing (the State is the applicant). The Connecticut page: 4 agencies, 14 programs, 2 open municipal rows, 1 between
rounds. Found while writing the parser:

- the first deadline wordings the Vermont table missed: "Applications must be submitted by November 6, 2026" and
  "Through December 4, 2026, the Department is currently accepting applications";
- six applicant phrasings, each added to the shared applicant sentences with Vermont held to identical hashes;
- HMGP's "serve as the sub-applicant on behalf of homeowners or businesses" tagged a household and a business; an "on
  behalf of ..." clause is now cut before tagging, and a bare "sub-applicant" is not an applicant sentence (only
  "serves as the sub-applicant" is);
- some pages put a `<form>` ahead of `<main>`, so the fixture scrub keeps forms (Vermont's drops them).

## The platform

Every agency is a section of one Sitecore portal, `https://portal.ct.gov`. Its `robots.txt` allows everything but
`/sitecore/*` and a list of beta sites; the agency paths below are allowed. The portal serves three page templates,
and the page reader (`connectors/connecticut_portal.py`) takes the program text from whichever is present, in this
order:

| Template | Seen on | Program text |
|---|---|---|
| tabbed content | DEMHS grant pages | `main .tabs-content` |
| new layout, main column | DOT LOTCIP, Carbon Reduction | `.cg-l-main-content` |
| new layout, sections only | DOT CCGP, Bus Stop Enhancement | every `main .content-block-section`, in order |
| older layout | DOH, DEEP | `main .columns.medium-8 > .content` (else `main .content`) |

The title is the page's `h1` (on the older layout it is a screen-reader `h1.show-for-sr` with the same text). Contact
lines (`@ct.gov`, "Phone:") are dropped.

## The pages (2026-11-04)

| Connector | Agency (code) | Category label | Pages |
|---|---|---|---|
| `ct_doh` | Department of Housing (`CT-DOH`) | community development | CDBG Small Cities |
| `ct_dot` | Department of Transportation (`CT-DOT`) | transportation | LOTCIP, Community Connectivity Grant Program, Bus Stop Enhancement, Carbon Reduction |
| `ct_deep` | Department of Energy and Environmental Protection (`CT-DEEP`) | recreation and conservation | Open Space and Watershed Land Acquisition (OSWA), Urban Green and Community Garden (UGCG) |
| `ct_demhs` | Division of Emergency Management and Homeland Security (`CT-DEMHS`) | emergency management | Municipal Grant Program, FMA, BRIC, HMGP, EMPG, HSGP, State and Local Cybersecurity |

Left out, on purpose (Saj's call 2026-11-04, the Vermont line: the navigator is about what a town applies for):
the formula entitlements every town receives each year with no round (LoCIP, Town Aid Road, Municipal Grants in Aid,
Mashantucket Pequot/Mohegan Fund) and OPM's tax relief reimbursements. Also out: OPM's Regional Services Grant (the page
is an 88-character stub), DRIP (direct grants to public school operators), STEAP (no page of its own: it runs through
DEMHS's Municipal Grant Program, which is in), DOT's Safe Routes page (its only dated line is a sticker contest), and
DOT pages that describe no funding (NEVI, Vision Zero, traffic noise and the like).

## Round sentences, as the pages write them

- DEEP OSWA: "Through November 6, 2026, the Department is currently accepting applications from municipalities ..."
  and "Applications must be submitted by November 6, 2026, Appraisals must be submitted by December 4, 2026".
- DEEP UGCG: "Through December 4, 2026, the Department is currently accepting applications from municipalities ...".
- DOH Small Cities: "Please be advised that the 2026 CDBG Small Cities Application Submission deadline has been extended to
  September 11, 2026, 11:59pm" (past). Its training notice, "Registration is NOW Open", is about a course, not the
  round. Applicants: "This program is only available to Connecticut towns and cities with populations of less than
  50,000."
- DOT CCGP: "The CCGP 2025 Solicitation period is now closed."
- DOT LOTCIP: "provides State funds to urbanized area municipal governments in lieu of Federal funds"; no round.
- DEMHS EMPG and HSGP: the State (DESPP) "is the State's eligible applicant"; no round on any DEMHS page probed.

## Field mapping and status

The agency-page table in `connectors/hand_list.py` (the Vermont table, moved there when Connecticut reused it; see
docs/connectors/vermont.md for each rule): a deadline next to its word, the opening date, closed wording, a past
deadline as `unknown` ahead of a stale "now open", undated open wording; applicants from short items under an applicant
label plus applicant sentences; a page's own "Funding source:" line, else a named federal source, decides
`pass_through`. Connecticut added two deadline wordings to the shared table: "submitted by" a date, and "through" a
date in a sentence that says applications are being accepted. Vermont's 17 fixtures produce identical `record_hash`
before and after the move.

## Decisions

1. **One base for the portal** (`connecticut_portal.py`), each agency its own connector, the Vermont pattern.
2. **The shared table moved to `hand_list.py`** at its second state; the Vermont base re-exports the moved names.
3. **The formula entitlements are left out** (Saj, 2026-11-04).
4. **OSWA's application date is `closes_at`**, not the appraisal or appraisal-review dates that follow it.
