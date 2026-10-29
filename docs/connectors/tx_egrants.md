# Texas Governor's eGrants connector (`tx_egrants`): source, raw data and field mapping

Milestone 9, connector 6. Written 2026-10-28 from the 50-state census (`docs/surveys/state_portals.md`), before the
parser. One state office, one public list, every round stating who may apply in plain text: the cheapest source in the
census for the municipal page.

## Implemented (2026-10-28, same day)

`connectors/tx_egrants.py` follows this doc. First live run on a fresh database: 147 records added in 7 seconds (3
open, 144 closed; 76 grants by title keyword, 71 with no stated type), 0 errors. Second run: 0 changed, 0 missing.
On the Texas page: 1 open municipal row (ALERRT Travel Assistance FY2027, likely) and 29 between rounds, the county and
city rounds that recur every fiscal year (Border Zone Fire Departments, State Homeland Security Program, Texas
Anti-Gang, Operation Lone Star, ...). The other two open rounds are county-only (invitation only) and nonprofit-only,
and are not municipal. Found while writing it: 22 cards hold their eligible text outside any `<p>`, which a first
count that looked only for paragraphs read as "no text"; the parser reads the bare block, and the corrected count is 127
of 147 rounds with an applicant tag.

## The source

The Office of the Governor (OOG) posts its funding announcements on eGrants, `https://egrants.gov.texas.gov`. Two
public pages carry the same card markup; both are plain server-rendered HTML (no JavaScript, no session, no login):

| Page | What | Cards on 2026-10-28 |
|---|---|---|
| `/fundingopp` ("Active Opportunities") | the announcements the office currently lists | 4 |
| `/fundingopp/archive`, then `/archive/P25`, `/P50`, `/P75`, `/P100`, `/P125` | the archive, 25 cards a page, back to due dates in 2023 | 143 (5 full pages and 18 on the last) |

A page past the end (`/archive/P150`) answers 200 with no cards, which is the stop signal. 147 distinct rounds in all, no
slug on both lists today. `robots.txt` is a 404 (no restrictions). The site is on a framework that puts a CSRF token in
its forms; every request here is a plain GET and needs none. About 7 requests a run, 0.3 s apart.

**"Active" does not mean open.** The Violence Against Women Justice and Training Program round is on the Active page
with a due date of 02/12/2026, eight months before this survey. Status therefore comes from the dates on the card, never
from which page lists it.

### One card

```html
<div class="opp-list-item" id="music-educational-and-community-programs-fy2027">
  <div class="opp-list-namegroup"><div class="opp-label">Name:</div>
    <div class="opp-title"><a href="/fundingopp/page/music-educational-and-community-programs-fy2027">Music Educational and Community Programs, FY2027</a></div></div>
  <div class="opp-list-dategroup">
    <div class="opp-date-box"><div class="opp-date-name">Available</div><div class="opp-date">10/05/2026</div></div>
    <div class="opp-date-box"><div class="opp-date-name">Due Date</div><div class="opp-date">12/07/2026</div></div></div>
  <div class="opp-list-details"><div class="opp-label">Purpose:</div>
    <div class="opp-detail"><p>The Texas Music Office (TMO) is a division within the Office of the Governor's ...</p></div></div>
  <div class="opp-list-details"><div class="opp-label">Eligible Organizations:</div>
    <div class="opp-detail"><p>Only 501(c)(3) nonprofits based in Texas may apply. ...</p><p>•Be a nonprofit organized and based in Texas;</p></div></div>
  <div class="total-funds-group"><div class="total-title">Total Funds</div><div class="total-value">$TBD</div></div>
  <a class="readmore" href="/fundingopp/page/music-educational-and-community-programs-fy2027">Read More</a>
</div>
```

The `id` is the slug that ends the round's page URL, and it carries the fiscal year (`...-fy2027`), so each year's round
is its own record. The card text is complete (the eligible-organizations text is not truncated). **A round's own page
(`/fundingopp/page/<slug>`) is not usable:** fetched with a plain GET it holds none of the round's content (no purpose,
dates or eligibility), only the site chrome and the office's contact and address block, so it is filled in by script or
needs a session. Per CLAUDE.md no browser workaround is attempted; the card is the whole public record.

### What the 147 cards held (2026-10-28)

| Field | Values |
|---|---|
| Available, Due Date | `MM/DD/YYYY` on all 147; no due date before its available date |
| status by those dates | closed 144, open 3 (one of the 4 Active-page rounds is closed) |
| Purpose | present on all 147 |
| Eligible Organizations | on all 147 cards. 22 hold their text as a bare block with no `<p>` (for example rounds of the State and Local Cybersecurity Grant Program and Operation Lone Star), the rest 1 paragraph (58 cards), 2 (28), 3 (32), up to 8; at most 1,170 characters; `Invitation Only` on 3 (County Essential Services, FY2025 to FY2027) |
| Total Funds | `$TBD` 105, `$N Million` 28, `$N` 7, `$` 2, `$NM` 2, and one each of `$TBD - at least N% of available SHSP funding`, `$N - NM`, `$N K` |

Applicant text examples: "Applications may be submitted by independent school districts, institutions of higher
education, units of local government, and other educational institutions employing peace officers under Article 2.12 ...";
"Invitation Only. Applications may only be submitted by Texas counties."; "Only 501(c)(3) nonprofits based in Texas may
apply." Through the shared tagger (negated sentences dropped), **127 of 147 rounds carry an applicant tag**: county 110,
municipality 93, tribe 62, nonprofit 57, higher_ed 54, state 43, school 41.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `tx_egrants` |
| source_id | card `id` | the slug (`alerrt-travel-assistance-fy2027`) |
| source_url | card link | `https://egrants.gov.texas.gov/fundingopp/page/<slug>` |
| external_number | none | null |
| name | card title | whitespace collapsed |
| level / jurisdiction | constant | `state` / `TX` |
| administering_agency | constant | `Office of the Governor`: the host office, which the page names as the solicitor ("OOG may solicit applications") |
| agency_code | none | null |
| funding_type | name | the shared `funding_type_for` keyword rule; else null |
| funding_source | none | `direct`: the card makes no claim about whose money it is |
| amount_min / amount_max | none | null: Total Funds is a program total, not an award |
| match_required / match_pct | none | null: no labelled field |
| status | Available, Due Date | see status rules |
| opens_at / closes_at | Available / Due Date | the dates as written |
| closes_at_text | a date cell that is not a date | verbatim; none seen |
| rolling | none | null: every card has a due date |
| summary | Purpose | the first paragraph, whitespace collapsed |
| eligibility_text | Eligible Organizations | the paragraphs, one per line (the bare block as one line); null when empty |
| eligibility_structured | card | `{"total_funds": "$15 Million", "invitation_only": true}`, keys only when present; Total Funds verbatim, `invitation_only` when the eligible text begins "Invitation Only" |
| applicant_types | Eligible Organizations | see decision 2 |
| categories | none | none: the card states no topic |
| alns | none | always empty |

### Status rules

In order; the first that applies wins. A card always has both dates.

| The card says | Status |
|---|---|
| Available after today | forecasted |
| Due Date before today | closed |
| otherwise | open |

The day of the due date is open. Which page lists the round does not matter.

### What happens when a round leaves

`resolve_missing(source_id)` returns `unknown` and makes no request. Rounds are not removed, they move to the archive,
and the archive is read in full every run, so a slug that is on neither list was taken down, which the source does not
state as a closure.

### Change detection

The hash is over the Program. The cards carry no modified stamp, so everything is read every run: about 7 requests.

## Decisions (defaults; override at review)

1. **Status comes from the dates, not the page.** The Active page lists a round eight months past its due date.
2. **Applicants are the Eligible Organizations text, sentence by sentence.** Split into sentences, drop any sentence the
   shared `NEGATION_RE` matches, then the shared `applicant_types_for`. That drops "Non-profit applicants seeking to
   provide direct services to victims of crime are not eligible under this solicitation" and "Volunteer Fire
   Departments are not eligible" and tags nothing from them. It also drops "includes, but is not limited to", which
   costs nothing today because the nonprofit is named in another sentence. Same rule as `webgrants`.
3. **Total Funds is kept as the source's words and never read as an award.** `$TBD`, `$15 Million` and `$TBD - at
   least N% of available SHSP funding` are program totals in no common unit; `amount_min` and `amount_max` stay null.
4. **"Invitation Only" is recorded, not acted on.** County Essential Services is tagged `county` because the source says
   counties may apply, and `eligibility_structured["invitation_only"]` says the county needs an invitation. The
   municipal views do not read that key, but they also do not need to: a round tagged only `county` is not on the town
   page (checked on the live data: County Essential Services FY2027 is open and absent from it).
5. **The archive is read in full every run.** Closed rounds are the history the between-rounds group needs (the same
   county and city rounds recur every fiscal year), and it is five requests.
6. **A page that cannot be read aborts the run.** Otherwise every archived round would look missing and be marked
   `unknown`. Dropped connections are retried three times; an HTTP error status is not retried.
7. **Paging stops at the first page with no cards, capped at 20 pages**, so a changed pager cannot loop. If the archive
   ever needs more than 20 pages the cap is a one-line change.
8. **No category.** The card names no topic, and the rounds are mostly public safety and criminal justice, which is
   knowledge about the office, not a field on the page.

## Known gaps (the source's wording, not the parser's)

- 20 of 147 rounds carry no applicant tag: their text names none of the applicants the shared tagger knows.
- The shared negation rule reads "but is not limited to" as a negation (decision 2).
- The Funding Sources page (`/funding`) says whether a program is federal or state money; it is not read, so
  `funding_source` is `direct` for every round.

## Out of scope

Each round's own page (empty to a plain GET, see above) and its Request for Applications (RFA) document; the Funding Sources page; the other Texas
agencies (the census found no other public Texas listing).

## Verification

- `tests/test_tx_egrants.py` against `tests/fixtures/tx_egrants/` (the Active page, two trimmed archive pages and an
  empty page, written by `scripts/probe_tx_egrants.py`): card parsing, dates and statuses including the past-due Active
  round, deduplication, paging, the applicant text cases, Total Funds shapes, `fetch` with a stub client (retry, a
  failing page aborts), `resolve_missing`.
- Two live runs: all added, then 0 changed.
