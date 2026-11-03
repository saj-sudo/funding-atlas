# Delaware DelDOT connector (`de_deldot`): source, raw data and field mapping

Milestone 11, Delaware's transportation agency (the municipal five, decision 2026-11-03). Written 2026-11-03 from a
read of DelDOT's program listing, before the parser. Two programs a town or a school applies for: the Transportation
Alternatives Program and Safe Routes to School. The rest of DelDOT's program listing (`/Programs/`, about fifty
entries) is how the department runs roads, not money it gives out.

## Implemented (2026-11-03, same day)

`connectors/de_deldot.py` follows this doc. First live run: 2 records added, 0 errors; second run 0 changed. TAP is
`unknown` with its past call-out kept ("deadline April 17th, 2026"), `pass_through` and matched, tagging municipality,
county, nonprofit and school from its sponsor list; Safe Routes tags schools. Neither is open on the survey day.

## The source

`https://deldot.gov` (the state CLF template; `robots.txt` disallows a few `/information/` and `/services/` paths,
nothing under `/Programs/`). Two hand-listed programs, three GETs:

| Slug | Pages | What they say (2026-11-03) |
|---|---|---|
| `tap` | `/Programs/tap/` and `/Programs/tap/index.shtml?dc=apply` | "Project Sponsors may include: Local Governments, Regional Transportation Authorities, A transit agency such as DART, MPO's ..., Natural Resource or public land agencies, School Districts and local education agencies, Non-Profits" (an `h4` and a list on the overview); "2026 Project Call-Out for New TAP Applications - deadline April 17th, 2026. DelDOT welcomes federal fiscal year 2026 applications statewide as they are now being accepted through April 17th, 2026." (the apply page); "TAP funding can be requested for up to 80% of a project" |
| `srts` | `/Programs/srts/index.shtml` | "Elementary and middle schools can receive funding through Delaware Safe Routes To School Program." No dates |

Content sits in `#main_content` beside a `#leftCol` menu column; the page's `h1` is the state banner, so the name
comes from the `<title>` before ` - Delaware Department of Transportation`.

## Field mapping

| Program field | Rule |
|---|---|
| source_id / source_url | the slug; the overview page |
| name | the `<title>` prefix (`Transportation Alternatives Program - TAP`, `Safe Routes to School`) |
| administering_agency / agency_code / jurisdiction | `Department of Transportation` / `DE-DELDOT` / `DE` |
| funding_type | the shared keyword; else `grant` (both are reimbursement grant programs by their own text) |
| funding_source | `pass_through` when the text names federal law or an agency (TAP: "Bipartisan Infrastructure Law", "Surface Transportation Block Grant Program"); else `direct` |
| match_required | `True` when a sentence states a share ("up to 80% of a project") |
| status | `open` when the cycle sentence carries a full date on or after today; `closed` when it says closed; else `unknown` (TAP's April 17, 2026 call-out had passed on the survey day: a stale page, unknown, the MEA rule) |
| closes_at / closes_at_text | the last full date in the cycle sentence; the sentence verbatim |
| summary | the first paragraph of the overview |
| eligibility_text | the list under a label mentioning sponsors or applicants, plus sentences that say who can receive funding or apply |
| applicant_types | the shared tagger, sentence by sentence |
| categories | none (TX rule) |

## Decisions

1. **Two programs by hand list.** DelDOT's `/Programs/` listing is operational; TAP and SRTS are the ones with a call
   for applications from outside the department.
2. **The apply page is read for TAP** because the overview states no dates and the apply page states the call-out.
3. **Contact blocks are not read** (a named coordinator and phone on each page).

## Known gaps

- TAP's call-out is a past date on a page that does not say the round closed: `unknown` with the sentence kept.
- SRTS names schools only; a town's role (co-sponsor) is in the guidelines, not on the page.

## Verification

`tests/test_de_deldot.py` against the three saved pages (`scripts/probe_de_deldot.py`); two live runs.
