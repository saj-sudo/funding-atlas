# WebGrants storefront connector (`webgrants`): source, raw data and field mapping

Milestone 9, connector 5. Written 2026-10-28 from the 50-state census (`docs/surveys/state_portals.md`, the WebGrants
findings), before the parser. The first connector for a vendor platform rather than a state-run index: Iowa and
Montana's agency hosts serve the same public storefront, so the state is configuration.

## Implemented (2026-10-28, same day)

`connectors/webgrants.py` follows this doc. First live run on a fresh database: 40 records added in 20 seconds (29 Iowa,
11 Montana; all open; 6 rolling; 7 grants, 2 loans, 1 tax credit by title keyword, 30 with no stated type), 0 errors.
Second run: 0 changed, 0 missing. Applicant tags on 9 of the 40 rounds. On the Iowa page: 2 open municipal rows (both
likely: the two CDBG 2024 Disaster Recovery rounds, deadline 2026-11-13) and 0 between rounds; the Montana page: 0
municipal rows, as expected from a single Department of Agriculture host. Cross-checked every round's list deadlines
against the deadline heading on its own detail page: all 40 agree, and one round (687121) repeats its final date as its
pre-application date on the list, which the record leaves out.

## The source

WebGrants is Dulles Technology's grants-management system. Its public face is the **storefront**: a list of the
opportunities posted now, and one page per opportunity. Hosts on 2026-10-28:

| Key | Host | State | Rows | Notes |
|---|---|---|---|---|
| `ia` | `https://www.iowagrants.gov` | IA | 29 | seven agencies: Education 13, Economic Development Authority 7, Health and Human Services 4, Workforce Development 2, three more with 1 |
| `mtagr` | `https://mtagr.webgrantscloud.com` | MT | 11 | Department of Agriculture only |
| `mtfwp` | `https://mtfwp.webgrantscloud.com` | MT | 0 | the table is there with no rows; no `Pre-Application Due Date` column |

`https://funding.mt.gov` (Montana's statewide WebGrants host) answers 400 on `storefrontFOList.do`; its list is behind
the login, so it is not read. Whether other Montana agencies or other states run a public storefront is not known: the
census looked for WebGrants only where a state turned it up.

`robots.txt` is a 404 on all three hosts (no restrictions published). About 41 requests a run (3 lists, 40 details),
0.3 s apart, under a minute.

### The list (`storefrontFOList.do`)

One static `<table id="storefrontFO">`, no paging, no session. Closing tags are upper case (`</TD>`), so parse
case-insensitively. Columns, read by header name:

`ID, Status, Categorical Area, Agency, Program Area, Title, Posted Date, Pre-Application Due Date, Final-Application Due Date`

```html
<tr><td class="text-center">230028</TD>
    <td class="text-center"><span class="label label-Posted">Posted</span></TD>
    <td>Community Development,Economic Development,Energy</TD>
    <td>Economic Development Authority</TD><td>ENERGY</TD>
    <td><a href="viewStorefrontOpportunity.do?OIDString=1506540313360|Opportunity">Iowa Energy Center Grant Program</a></TD>
    <td class="text-center">Aug 24, 2026 3:25 PM</TD><td class="text-center">Sep 17, 2026 8:30 AM</TD>
    <td class="text-center">Nov 2, 2026 11:59 PM</TD></tr>
```

- Every one of the 40 rows has `Status` = `Posted`: it is a list of what is posted now, and a round that ends leaves it.
- Dates read `Mon D, YYYY h:mm AM`; a missing deadline reads `Not Applicable` (27 of 29 Iowa pre-applications, 6 of 29
  Iowa finals, 10 of 11 Montana pre-applications, 0 Montana finals).
- `ID` and `OIDString` are unique per host. `ID` is the number the page shows in its own title (`230028 - Iowa Energy
  Center Grant Program`); `OIDString` is the page key.
- `Categorical Area` is a comma list; it can be empty (12 of 40). Values seen: Agriculture 11, Education 8, Economic
  Development 7, Community Development 6, Rural Issues 5, Housing 3, Historic Preservation 2, Energy 2, Disaster
  Assistance 2, Disaster Preparedness 2, and one each of History, Tourism and Hospitality, Child Health, Health,
  Prevention/Treatment, IT/Telecommunications, Unspecified.

### The detail page (`viewStorefrontOpportunity.do?OIDString=<oid>|Opportunity`)

16 to 26 KB. A labelled field block of `<span class='field-label'>` / `<span class='field'>` pairs:

```
Status                   Posted
Posted Date              Aug 24, 2026 3:25 PM
Award Amount Range       No Limit - $1,000,000.00
Project Dates            12/09/2026 -
Award Announcement Date  01/19/2027
Categorical Area         Community Development,Economic Development,Energy
Recurring Opportunity    No
Program Officer / Phone / Email
```

Shapes across the 40: Award Amount Range `Not Applicable` 18, `No Limit - $N` 18, `$N - $N` 3, `No Limit - No Limit` 1;
Recurring Opportunity `Yes` 17, `No` 18, empty 5; Award Announcement Date empty on 33; Project Dates empty or partial on 13.

Then one rich-text blob, `<span class='field' id='OpportunitySynopsis_synopsis'>`, with no structure beyond HTML: 38
of 40 pages have it (the two Computer Science Incentive Fund pages do not). Headings inside it are bold-only
paragraphs (`<p><strong>Eligible Applicants</strong></p>`), occasionally an all-caps plain paragraph
(`ELIGIBLE APPLICANTS:`, `APPLICANT ELIGIBILITY`). 13 pages have an eligibility heading; 27 do not.

An id that is not on the list answers **HTTP 500**, so a round that has left the list cannot be read back.

A TLS connection reset happened once when the pages were read with `urllib` and never with `httpx` and a retry (0
failures in 40 pages), so the connector retries.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `webgrants` |
| source_id | host key and `ID` | `ia-230028`, `mtagr-27784` |
| source_url | host and `OIDString` | `<host>/viewStorefrontOpportunity.do?OIDString=<oid>|Opportunity` as the site writes it |
| external_number | `ID` | the number the page shows (`230028`); host-local, so it is not the key |
| name | `Title` | whitespace collapsed |
| level / jurisdiction | constant, host | `state` / `IA` or `MT` |
| administering_agency | `Agency` | verbatim (`Economic Development Authority`) |
| agency_code | none | null |
| funding_type | `Title` | the shared `funding_type_for` keyword rule (tax credit, loan, voucher, grant); else null |
| funding_source | none | `direct`: the page makes no claim about whose money it is |
| amount_min / amount_max | `Award Amount Range` | `$a - $b` is (a, b); `No Limit - $N` is (null, N); `Not Applicable` and `No Limit - No Limit` are null |
| match_required / match_pct | none | null: no labelled field (a few descriptions mention cost share in prose) |
| status | list row | see status rules |
| opens_at | `Posted Date` | the date part |
| closes_at | `Final-Application Due Date` | the date part; `Not Applicable` is null |
| closes_at_text | `Pre-Application Due Date`, `Recurring Opportunity` | `Pre-application due: <date>` when present and different from the final date (the list repeats the final date on some rounds, and the detail page then prints only the final one); `Recurring opportunity` when the field says `Yes`; joined with `; `; else null |
| rolling | `Final-Application Due Date` | `Not Applicable` is True; else null |
| summary | description | the synopsis's first non-empty paragraph, whitespace collapsed; null without a synopsis |
| eligibility_text | description | the text of the eligibility sections, headings included, one block per section; null if none |
| eligibility_structured | detail | `{"categorical_area": [...], "recurring": "Yes"}`, keys only when the cell is non-empty |
| applicant_types | eligibility sections | see decision 2 |
| categories | `Categorical Area` | per value through the shared `PORTAL_CATEGORIES` (`connectors/text.py`); the portal's word is the `source_code`; empty cell gives none |
| alns | none | always empty |

The program officer's name, phone and e-mail are on the page and are left out of the stored payload as well as the record: the database is published.

### Status rules

In order; the first that applies wins. The state's own word is `Posted`.

| The row says | Status |
|---|---|
| `Status` is not `Posted` | unknown (none seen) |
| `Posted Date` after today | forecasted |
| `Final-Application Due Date` before today | closed |
| otherwise | open |

All 40 were open on the day. The time of day is ignored: a round due today is open today.

### What happens when a round leaves the list

`resolve_missing(source_id)` returns `unknown` and makes no request. Leaving the list is not a closure the source states,
and there is nothing to read back: an id that is not on the list answers HTTP 500, and a detail page's key
(`OIDString`) cannot be derived from the visible `ID`, which is all `resolve_missing` receives. A round that returns
resumes with its dates. **The rule is unverified against a real removal**: none has been observed, and the 500 on an
unknown id is the only evidence. The first round that leaves a storefront settles it, and this doc is updated then.

### Change detection

The hash is over the Program. The detail page carries no modified stamp, so every page is read every run. The posted
date is mapped (`opens_at`), the program officer is not.

## Decisions (defaults; override at review)

1. **Hosts are configuration, columns are read by header.** `mtfwp` has no pre-application column, and a host that
   gains or loses one must not shift the others. The three hosts above are the whole set; a fourth is one line.
2. **Applicants come from the eligibility section only, sentence by sentence.** A heading paragraph that is exactly
   `Eligible Applicants`, `Eligibility`, `Eligibility Requirements`, `Applicant Eligibility`, `Who May Apply` or
   `Eligible Entities` (any case, optional colon) opens a section; the next short bold-only or all-caps paragraph
   closes it. Inside it the rules are the Drupal base's `applicant_lines` (the first line is the applicant statement;
   later lines only if they name who applies; stop at a condition lead-in such as "criteria:"), with one change kept in
   this connector: negation is judged **per sentence**, so "Units of government (cities, counties) are not eligible to
   apply for credits" drops while its paragraph's first sentence stays, and a first sentence is not lost to a later
   "not". The tags come from the shared `applicant_types_for`. Reading the whole description instead finds four more
   municipal rows on the day and was rejected: it tags incidental text (a potato research program tags `municipality`).
   The two Iowa CDBG disaster rounds are the municipal rows.
3. **The 27 pages without an eligibility heading get no applicant tags.** The source does not say in a labelled place;
   the record does not either.
4. **A `Posted` row is open until its own final deadline passes.** The storefront drops an ended round, so a past deadline
   on a listed row is a stale posting and reads `closed`, never `open`.
5. **`Recurring opportunity` goes to `closes_at_text`, not to `rolling`.** Recurring means the program repeats, which is
   what the between-rounds group reads; rolling means there is no deadline, and only `Not Applicable` says that.
6. **A host list that cannot be read aborts the run.** Otherwise every round on that host would look missing and be
   marked `unknown`. A detail page that cannot be read falls back to the last stored copy.
7. **Categories reuse the shared table.** Community development reads as infrastructure (the Grants.gov and pa.gov rule);
   disaster assistance and disaster preparedness as public_safety; child health and prevention/treatment as health;
   historic preservation, history, tourism, rural issues, education, agriculture and IT/telecommunications as other.

## Known gaps (the source's wording, not the parser's)

- 27 of 40 pages state eligibility only in prose or not at all, so most Iowa education and Montana agriculture rounds
  carry no applicant tag. Reading the description sentences is a separate, noisier feature.
- Montana's potato research page lists applicants as plain paragraphs under "Proposals for funding will be accepted
  from:"; the paragraph-list items are not picked up, so "Local Governments" there is missed.
- The shared tagger does not know "local units of government" (the word order on Iowa's forensic laboratory round), and
  `residents` tags a household on a business grant ("employ residents of Iowa"). Both are tagger items, not this
  connector's.
- The only evidence for the removed-round rule is the HTTP 500 on an unknown id.

## Out of scope

Other agency hosts and other states (not looked for); the login-only statewide list on `funding.mt.gov`; attachments
and website links on the page; Project Dates and Award Announcement Date as columns.

## Verification

- `tests/test_webgrants.py` against `tests/fixtures/webgrants/` (the three list pages trimmed, and the saved detail
  pages, written by `scripts/probe_webgrants.py`): header-based parsing including the empty and the no-pre-application
  tables, dates, awards, status, recurring and rolling, section-scoped tagging including the negated sentence,
  categories, `fetch` with a stub client (retry, fallback to stored copy, host failure aborts), `resolve_missing`.
- Two live runs: all added, then 0 changed.
