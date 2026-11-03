# Virginia DCR connector (`va_dcr`): source, raw data and field mapping

Milestone 11, Virginia's third agency (the municipal five, decision 2026-11-03). Written 2026-11-03 from a read of the
Department of Conservation and Recreation's "Recreation Oriented Grants" index and the six program pages it links,
before the parser. Parks, trails and land conservation: the Land and Water Conservation Fund, the Recreational Trails
Program, Trail Access grants, ORLP, battlefield acquisition and the Virginia Land Conservation Foundation.

## Implemented (2026-11-03, same day)

`connectors/va_dcr.py` follows this doc. First live run on a fresh database: 6 records added, 0 errors; second run 0
changed. Three closed on the page's own words (LWCF "now closed", RTP "closed on May 5, 2026", VLCF "closed"), three
`unknown` (ORLP "due to the National Park Service by November 1 of each year", Trail Access "not anticipated until 2027
or later", the battlefield grants state nothing). Four tag a municipality and county (LWCF, RTP, Trail Access, VLCF: the
VLCF page does name "local governments", correcting the survey table below), ORLP and the battlefield grants none.
Four are `pass_through` on the page's federal wording. The Virginia page: 0 open municipal rows, 3 more between
rounds (RTP with its date, LWCF and VLCF without). Found while writing the parser: the first "round sentence" rule
took any sentence mentioning a grant round and picked RTP's "most competitive in odd-year grant rounds" over "closed
on May 5, 2026"; a sentence that states closed, due or accepting now comes first.

## The source

`https://www.dcr.virginia.gov` is a hand-built PHP site (pages end in `.php` behind clean URLs). `robots.txt` disallows
a few unrelated paths (`/other/`, blog and data directories); nothing here. The index,
`https://www.dcr.virginia.gov/recreational-planning/grants`, is one page of six `<h2>` headings, each a paragraph and a
"Learn more" link. The connector reads the six linked pages by hand list (decision 1): the index is a brochure that
changes rarely and the pages are the records.

| Slug | Page | Program |
|---|---|---|
| `lwcf` | `/recreational-planning/lwcf` | Land and Water Conservation Fund State and Local Assistance |
| `orlp` | `/recreational-planning/orlp` | Outdoor Recreation Legacy Partnership Program |
| `trailfnd` | `/recreational-planning/trailfnd` | Virginia Recreational Trails Program (RTP) |
| `trail-access-program` | `/recreational-planning/trail-access-program` | Trail Access Grants Program |
| `abpp-grants` | `/recreational-planning/abpp-grants` | American Battlefield Protection Program Battlefield Land Acquisition Grants |
| `vlcf` | `/land-conservation/vlcf` | Virginia Land Conservation Foundation |

Six GETs a run, 0.3 s apart. The host answered intermittent proxy 502s on the survey day; a dropped page falls back to
the stored copy. Not read: the Open Space Conservation and Recreation Fund page (`/checkoff`, the tax check-off that
funds Trail Access, not a program) and grants.gov.

### A page

```html
<main id="startContent"><div id="page">
  <div id="breadcrumb">...</div>
  <h1>Land and Water Conservation Fund - General Information</h1><br>
  <h2>2026 LWCF Grant Round is now closed.</h2>
  <p>The Land and Water Conservation Fund Act of 1965 established a federal reimbursement program ...</p>
  ...
  <h3 class="section-title2">LWCF State &amp; Local Assistance Grant</h3>
  <p>The 2026 Land &amp; Water Conservation Fund State &amp; Local Assistance (LWCF) Virginia DCR Grant Round is now closed. LWCF is federal funding as a 50/50% matching reimbursement grant program for eligible projects. The 2027 DCR LWCF Grant Round is contingent upon available federal apportionment.</p>
  <p><strong>Entities eligible to compete for LWCF funding</strong></p>
  <ul><li>Counties, cities and towns</li><li>Park and recreation authorities</li><li>Tribes</li><li>State agencies</li></ul>
```

Prose, headings and lists in document order; no labelled fields. What the six pages said on 2026-11-03:

| Page | Round sentence | Applicant sentence |
|---|---|---|
| LWCF | "2026 LWCF Grant Round is now closed." (an `h2`); "The 2027 DCR LWCF Grant Round is contingent upon available federal apportionment." | the bold label and list above |
| ORLP | "DCR accepted preapplications for the 2026 ORLP grant round from July 14 - Sept. ..." | none in prose (urban areas listed; "Any project eligible for the ORLP Program is also eligible for the LWCF ...") |
| RTP | "The 2026 RTP grant closed on May 5, 2026."; "Applicants will be notified of status in July 2026." | "Funding may be awarded to city, county, town, tribal or other government entities. Registered nonprofit organizations partnered with a government body are also eligible." |
| Trail Access | "At current accumulation rates, the next grant round is not anticipated until 2027 or later." | "Eligible applicants include local (city, county, town) or tribal governments or recreation departments and code-designated park and recreation authorities." |
| Battlefield | none | "DCR serves as a pass-through entity to nonprofit organizations who are not eligible to apply for BLAG funding directly." |
| VLCF | "The VLCF grant round closed on Aug. ..."; "The Surry-Skiffes Creek grant round closed." | "State agencies, local governments, other public bodies, state and federally-recognized Indian Tribes and nonprofit land trusts are eligible to receive matching ..." |

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `va_dcr` |
| source_id | hand list | the slug |
| source_url | hand list | `https://www.dcr.virginia.gov<path>` |
| external_number | none | null |
| name | `h1` | as written, whitespace collapsed (`Land and Water Conservation Fund - General Information` is what the page says) |
| level / jurisdiction | constant | `state` / `VA` |
| administering_agency | constant | `Department of Conservation and Recreation` |
| agency_code | constant | `VA-DCR` |
| funding_type | name, then constant | the shared keyword; else `grant` (the index is "Recreation Oriented Grants" and every page is a grant program) |
| funding_source | page text | `pass_through` when a sentence says the money is federal (`federal reimbursement program`, `federal funding`, `pass-through entity`, `Federal Highway Administration`); else `direct`. Decision 3 |
| amount_min / amount_max | none | null |
| match_required | page text | `True` when a sentence states a matching percentage or "matching reimbursement" (`50-50% matching`, `80-20 matching`); else null |
| match_pct | none | null (the pages give a ratio, not a percentage of what) |
| status | the round sentence | see status rules |
| opens_at | none | null |
| closes_at | the round sentence | a full date in a sentence that says `closed on`, `due`, `deadline`, `by` or `through`; else null |
| closes_at_text | the round sentence | verbatim: the first heading or sentence that mentions a grant round, a deadline or applications being accepted, closed or due |
| rolling | none | null |
| summary | first paragraph | the first paragraph after the `h1` (a round headline is a heading, not a paragraph) |
| eligibility_text | applicant passage | the list under a label that mentions eligibility, plus every sentence that says who may apply (`eligible applicants`, `entities eligible`, `funding may be awarded to`, `are also eligible`, `eligible to apply`, `may apply`), one per line |
| eligibility_structured | none | null |
| applicant_types | applicant passage | the shared tagger, sentence by sentence, negated sentences dropped ("nonprofit organizations who are not eligible to apply ... directly" tags nothing on its own) |
| categories | the index | `parks`, source_code `Recreation Oriented Grants`, for the five pages the index lists under that title; none for VLCF (land conservation) |
| alns | none | always empty |

### Status rules

| The page says | Status |
|---|---|
| the round sentence says `closed` | closed (with the date it names, if any) |
| the round sentence says `now open`, `accepting` or `are due` with a full date on or after today | open |
| anything else | unknown |

### What happens when a page leaves

A hand-listed page that answers 404 is `unknown` (resolve_missing makes no request: the list is the enumeration).

### Change detection

The hash is over the Program; six pages, every run.

## Decisions (defaults; override at review)

1. **A hand list of six pages, not a crawl of the index.** The index is one brochure page whose six links changed
   never in the survey window; a seventh program is a one-line addition. The index is not fetched.
2. **Applicants from the applicant sentences and the labelled list only.** ORLP and the battlefield grants name none
   in prose (the latter names nonprofits only to say they cannot apply directly) and carry no tag; the manuals say
   who may, the pages do not.
3. **`pass_through` when the page says the money is federal.** LWCF ("federal reimbursement program ... on behalf of
   the National Park Service"), RTP ("administered by the Federal Highway Administration"), ORLP ("subprogram of the
   Land and Water Conservation Fund") and the battlefield grants ("DCR serves as a pass-through entity") say it in
   words; Trail Access (tax check-off) and VLCF (state fund) do not.
4. **`parks` from the index title.** "Recreation Oriented Grants" is the agency's own grouping of five of the six.
5. **"Questions?" blocks are not read**: a named contact on every page.

## Known gaps

- ORLP and the battlefield grants carry no applicant tag (decision 2).
- No page states an open round on the survey day; LWCF, RTP and VLCF are closed with 2026 dates, Trail Access says
  "not anticipated until 2027 or later" (unknown), ORLP and the battlefield grants state nothing (unknown).
- `closes_at` is the date a round closed where the page names one; a round that reopens next year is a change on the
  same record (the agency reuses its page), which the change log will show.

## Out of scope

The LWCF and RTP manuals and application documents, the Open Space fund page, grants.gov.

## Verification

- `tests/test_va_dcr.py` against `tests/fixtures/va_dcr/` (the six pages, "Questions?" blocks and e-mail addresses
  removed, written by `scripts/probe_va_dcr.py`): the labelled list, each applicant-sentence form, the round
  headline and the closed-on date, federal wording, the category rule, `fetch` fallback, `resolve_missing`.
- Two live runs: all added, then 0 changed.
