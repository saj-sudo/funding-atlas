# Maryland Department of Emergency Management connector (md_mdem): source, raw data and field mapping

Milestone 7, item 3 (the roadmap's 2026-11-03 "Start here" order: MDEM, MDOT, MDE). Live survey 2026-11-03. Third
agency on the `MarylandSharePointConnector` base (`maryland_sharepoint.md`), which gained one thing for it: MDEM's
pages name the rich-text control `ctl00`/`ctl01` instead of `RichHtmlField1`, so the base now falls back to the
control's suffix when the exact id is absent (the exact id is still tried first; MEA's and DNR's fixtures parse
byte-for-byte as before).

## Implemented (2026-11-03, same day)

`connectors/md_mdem.py` follows this doc on the `MarylandSharePointConnector` base. Live run on a copy of the published
database: 4 records (1 closed, 3 unknown) in five requests, as expected below; the second run reports no changes. All
four carry a municipality tag except NSGP (nonprofits only). Nothing is open: FMA (closed, local governments) joins
Maryland's between-rounds group (17 → 18 rows); the open municipal count stays at 13. The record the roster says is
open (NSGP, "Yes", deadline 4/26/2023) is `unknown` with its real window (June 30 to July 15, 2026) kept, because the
roster is stale and the page's window has passed.

## Source

`https://mdem.maryland.gov`, SharePoint on the state's `mdgov` theme, behind Cloudflare. `robots.txt` disallows only
`/_vti_bin/`, `/_layouts/` and `/_catalogs/`. No sitemap.

### The roster

`/Pages/grants.aspx` ("GRANT OPPORTUNITY ROSTER") is a SharePoint list ("Grant Opportunities List") rendered server-side
as one `<table class="ms-listviewtable">` in the page's second `mdgov-section`. The page still carries the banner
**"NOTE: THIS PAGE STILL IN DEVELOPMENT; NOT ALL CURRENT GRANT OPPORTUNITIES WILL APPEAR"** that the milestone 7 survey
recorded on 2026-10-16, and the same two items. The table's `o:WebQuerySourceHref` points at
`/_vti_bin/owssvr.dll?...&XMLDATA=1`, the list's XML export: robots-disallowed, so the HTML table is the source.

One item is a run of `<tr>`s: a `td.ms-vb-title` with the title (linked to an edit form, never followed), then
`td.ms-vb-tall` cells in a fixed order:

```html
<tr><td class="ms-vb-title"><div class="ms-vb itx" id="1" ...><a ...>Nonprofit Security Grant Program (NSGP)</a></div></td></tr>
<tr><td class="ms-vb-tall">...Funds physical and cybersecurity enhancements ... <a href="/Pages/Nonprofit-Security-Grant-Program.aspx">[Learn More]</a></td></tr>
<tr><td class="ms-vb-tall">Who is Eligible?<br>1. Nonprofit entities within designated urban areas<br><div>2. Nonprofit entities not within designated urban areas</div></td></tr>
<tr><td class="ms-vb-tall">Applications Open?:
          Yes</td></tr>
<tr><td class="ms-vb-tall">Apply:
          <a href="/Pages/Nonprofit-Security-Grant-Program.aspx">Apply Here</a></td></tr>
<tr><td class="ms-vb-tall">Application Deadline:
          4/26/2023 11:59 PM</td></tr>
```

| Item | Who is Eligible? | Applications Open? | Application Deadline | Learn More |
|---|---|---|---|---|
| Nonprofit Security Grant Program (NSGP) | 1. Nonprofit entities within designated urban areas; 2. Nonprofit entities not within designated urban areas | Yes | 4/26/2023 11:59 PM | `/Pages/Nonprofit-Security-Grant-Program.aspx` |
| Flood Mitigation Assistance (FMA) | Local Governments and State Agencies (Individuals, businesses, and organizations are not eligible, but a government/agency may sponsor the project on their behalf) | No | (blank) | `/community/Pages/Mitigation.aspx` → 302 → `/Pages/hazard-mitigation.aspx` |

The NSGP page itself says "The NSGP application period for FFY 2026 begins on June 30! Applications will be accepted
from June 30, 2026 until 4:00pm on July 15, 2026." The roster's `Yes` with a 2023 deadline is a stale row, and the
page's dated window is the fact. The hazard-mitigation page names no program (a request-info form, FAQs, and a link
to the loan fund below).

### The hand-added pages

The "Explore Funding Opportunities" menu lists nine pages. Two describe a program that is not on the roster:

- `/Pages/rlf-fund.aspx`, **Resilient Maryland Revolving Loan Fund**: "offers low-interest loans (no more than 1%)
  to local governments to help finance projects and activities that mitigate the effects of natural hazards"; "Local
  governments can take out RLF loans on behalf of: Homeowners, Businesses, Nonprofit organizations, Communities"
  (beneficiaries, not applicants); an "I am Interested in Applying for a Loan" form; "founded via the Safeguarding
  Tomorrow Through Ongoing Risk Mitigation (STORM) Act". No application window.
- `/community/Pages/Public-Assistance-Program.aspx`, **Public Assistance**: "provides supplemental financial
  assistance to State, local governments and certain private non-profit organizations for response and recovery
  activities as a result of a Presidentially-declared disaster"; "Federal grant assistance ... 75% Federal/25%
  applicant"; "There are currently no public notices". No window: the trigger is a declaration.

The other seven are not programs: the old funding page (a redirect notice), the Cyber Preparedness Unit, Individual
Assistance (FEMA's household program, applied for with FEMA), the Food System Resiliency Council, the Whole Community
Integration Branch, the hazard-mitigation page, and "Technical Grant Assistance Resources" (BRIC/FMA training videos).

### Page skeleton

As `maryland_sharepoint.md`, with the control-name difference above. H1 in `#ctl00_PlaceHolderMain_editmodepanel2`
on every page (empty on the roster page). Every page carries the theme's boilerplate `<meta name="description">`.
Contact blocks name people and obfuscated e-mails (Cloudflare `data-cfemail`); they are removed from the stored body.

## Enumeration and change detection

- `fetch()` GETs the roster (non-200 or no table or no items aborts the run: a changed layout must fail loudly, not
  mark every row missing), reads each item into `roster` facts (`title`, `description`, `eligible_lines`,
  `applications_open`, `deadline`, `deadline_text`, `apply_url`), keys the entry by the source id of its Learn More
  link as written (`pages/nonprofit-security-grant-program.aspx`, `community/pages/mitigation.aspx`; the FMA redirect
  is followed by the client, no extra request), then adds `HAND_ADDED` (`pages/rlf-fund.aspx`,
  `community/pages/public-assistance-program.aspx`) with `roster: null`, `listed: false`.
- Every page every run, five requests. The payload is the shared one plus `roster` and `listed`, so a roster edit
  (Yes → No, a new deadline) changes the record even when the page does not.
- `resolve_missing`: as the base, page-only. A row dropped from the roster whose page still exists gets the page's
  own reading (NSGP: `unknown` either way; FMA: `unknown` instead of `closed`). De-listing is enumeration.
- A second roster row pointing at a page another row already uses would collide on the key; the first wins
  (`setdefault`). Not solved until it happens.

## Field mapping

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `md_mdem` |
| source_id | the Learn More link, or the hand list | lowercased path |
| name | roster title, else `<h1>` | "Flood Mitigation Assistance (FMA)" rather than the hazard page's "Hazard Mitigation" |
| level / jurisdiction | constant | `state` / `MD` |
| administering_agency / agency_code | constant | `Maryland Department of Emergency Management` / `MD-MDEM` |
| funding_type | name keywords, then the text | `loan` (Resilient Maryland Revolving Loan Fund), `grant` where the name says so (NSGP) or the roster description / first page sentences say "grant" (FMA: "Annual competitive grant funding"; PA: "Federal grant assistance") |
| funding_source / alns | hand map, each quoted | NSGP 97.008 ("Federal Emergency Management Agency (FEMA), provides ... the Nonprofit Security Grant Program"), FMA 97.029 ("Apply Here [via FEMA]", fema.gov/grants/mitigation/floods), PA 97.036 ("Federal grant assistance ... 75% Federal"); all three numbers carried by Grants.gov records of the same names in the registry (2026-11-03). RLF `direct`: the STORM Act capitalised the fund, the loans are the state's. |
| amount_min / amount_max | none | null |
| match_required | shared wording over the body | null today (PA's "75% Federal/25% applicant" is a share, not a match sentence) |
| status | roster first, then the page | see status rules |
| opens_at | the window sentence | the first full date in it (NSGP: 2026-06-30) |
| closes_at | roster deadline, else the window sentence | the roster's `M/D/YYYY` when it is ahead; else the window's last full date |
| closes_at_text | roster line + window sentence | `Applications Open?: Yes; Application Deadline: 4/26/2023 11:59 PM` plus the page's window sentence, so either changing is a visible change |
| rolling | the page | "year-round" / "at any time" / "rolling basis" in an accepting sentence |
| summary | roster description, else meta | the roster's description text without the "[Learn More]" link; the meta is boilerplate on every page |
| eligibility_text | roster "Who is Eligible?" clauses, else page applicant sentences | what the tagger read |
| applicant_types | shared tagger over the same lines | NSGP `nonprofit`; FMA `municipality`, `county`, `state`; RLF `municipality`, `county`; PA `municipality`, `county`, `nonprofit` ("State" alone is not a phrase the shared table reads) |
| categories | constant | `public_safety`, source_code `mdem` |

### Status rules

1. Roster `Applications Open?: No` → `closed` (the roster deadline, if any, as `closes_at`).
2. Roster `Yes` with a deadline on or after today → `open`, `closes_at` = that deadline.
3. Roster `Yes` with a past or blank deadline: the roster is stale, the page decides. Its window sentence
   ("Applications will be accepted from June 30, 2026 until 4:00pm on July 15, 2026"): end date ahead → `open`;
   end date passed → `unknown` with `closes_at` kept (DelDOT's stale call-out rule); no window → `unknown`.
4. No roster facts (hand-added pages): the window rule; an accepting sentence with "year-round" / "at any time" /
   "rolling basis" → `open`, `rolling`; else `unknown`.

Expected on 2026-11-03: NSGP `unknown` (closes 2026-07-15, window passed), FMA `closed`, RLF `unknown`, PA `unknown`.

### Applicant lines

The roster's "Who is Eligible?" cell is read line by line, each line split into clauses: the text outside parentheses,
then each parenthetical on its own. A clause matching the shared negation (`not`, `ineligible`, ...) is dropped, the
rest kept. This is what lets FMA keep "Local Governments and State Agencies" and lose "(Individuals, businesses, and
organizations are not eligible ...)"; a sentence splitter alone would drop the whole line because it ends in a
parenthesis, not a period. NSGP's second line ("Nonprofit entities **not** within designated urban areas") is dropped
by the same rule, which costs nothing here (the first line tags `nonprofit`) and is recorded as the next shared-tagger
gap: "not within" is a place, not a negation of the applicant.

A page without roster facts contributes sentences that say who the money goes to (`eligible`, `may apply`,
`available to`, `assistance to`, `loans ... to`), minus negated ones. The RLF "on behalf of" list is beneficiaries and
never matches.

## Decisions

1. **The roster row is the record and lives at its Learn More page.** The roster has no page per item; the Learn More
   link is the page the agency itself points a reader to. FMA's link is the hazard-mitigation page, which names no
   program, so FMA's facts (name, eligibility, status) all come from the roster and the page adds nothing but a URL.
2. **A roster `Yes` with a past deadline is stale, not open.** The page's own dated window wins; with no window the
   row is `unknown`. Reading `Yes` as open would list a 2023 round.
3. **The owssvr XML export is not read.** `/_vti_bin/` is disallowed; the rendered table carries every field.
4. **Two pages are hand-added** because the roster says it is incomplete. The five other menu pages are not programs
   (above). Individual Assistance is FEMA's household program and is applied for with FEMA, not MDEM.
5. **Contact names and e-mails are removed from the stored body** (the WebGrants rule): the PA page names its officer.
6. **RLF is `direct`.** The page says the state used STORM Act money to establish the fund; the loans are state loans
   (no federal pass-through sentence, no FEMA application).
7. **`future_marker` moved into the base** (from `md_dnr.py`) because MDE is the third month-only forecast case;
   DNR's behaviour is unchanged (its tests still import the name from `md_dnr`).

## Known gaps

- NSGP's "not within designated urban areas" line is dropped as negated (above). No effect today.
- "State" as a bare applicant word ("to State, local governments and ...") tags nothing; the shared table reads
  "state agencies". PA's page therefore carries no `state` tag although the state is an applicant.
- The roster says it is incomplete. MDEM's other pass-throughs (HMGP, BRIC, EMPG, HSGP) have no page that names them
  as programs; when the roster grows, the connector reads the new rows with no code change.

## Out of scope

The Individual Assistance page (households, FEMA), the Cyber Preparedness Unit, the Food System Resiliency Council and
the Whole Community Integration Branch (membership programs, no money); the BRIC/FMA training-video page.

## Fixtures

`tests/fixtures/md_mdem/`: `index__pages__grants.json` (`url`, `main_html`: the whole `main#mdgovMain`, because the
roster sits in the page's second section) and one JSON payload per page, written by
`uv run python scripts/probe_maryland_sharepoint.py md_mdem` and scrubbed of contact details by the connector itself.
