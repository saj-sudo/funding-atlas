# grants.wv.gov connector (`wv_grants`): source, raw data and field mapping

Milestone 9, connector 2. Written 2026-10-18 from the Mid-Atlantic survey (`docs/surveys/mid_atlantic.md`), before the
parser. The second state outside Maryland and the first fed by a JSON API with no HTML at all.

## Implemented (2026-10-18, same day)

`connectors/wv_grants.py` follows this doc. First live run on a fresh database: 124 records added in three seconds
(5 open, 1 forecasted, 83 closed, 35 unknown; 3 rolling; 4 pass-through; 30 grants and 2 loans by title keyword, 92
with no stated type), 0 errors. Second run: 0 changed, 0 missing. Applicant tags on 49 records (county 31,
municipality 13, nonprofit 33); 75 carry none, because `EntityEligible` is empty or names applicants the shared map
does not know. On the West Virginia page: 1 open row (Clean Water State Revolving Fund Assistance, likely) and 0
between rounds, because the view requires a `municipality` tag and the recent municipal rounds (the Solid Waste
Management Board's FY2026 and FY2027 grants, closed April 2025 and April 2026) name counties only. The CDBG and law-
enforcement rounds a town would want are all 2023 postings nobody re-listed; this connector's value is the day they are.

## The source

West Virginia's state grants portal, `https://grants.wv.gov`, is SharePoint on-prem (the same release as Maryland's
SharePoint agencies). Its "Funding Opportunities" page, `https://grants.wv.gov/grants/Pages/default.aspx`, is a client-
side list filled from a state-run JSON API: the page's script posts to `https://apps.wv.gov/SharePoint/api/search` with
`siteurl=grants.wv.gov`, `listname=AvailableGrants`, an OData-style `query` built from the filter form, and
`maxItems=1000`. With an empty query the API returns the whole `AvailableGrants` list: 124 items on 2026-10-17,
693 KB. One POST per run.

The page defines the three statuses in its own filter: **Active** is `PostedDate <= today <= DueDate1`, **Not Active**
is the complement on dates, **Forecasted** is `Forecasted ne ''` (any item with text in the `Forecasted` column,
whatever its dates). Per-grant pages `https://grants.wv.gov/grants/Pages/grantdetails.aspx?grantid=<Id>` are shells
filled by the same API and are the connector's `source_url`, never fetched. `robots.txt` and `sitemap.xml` are both 404
(no restrictions published). `/grants/_api/web/lists` is anonymously readable.

The connector waits for nothing: one request, then normalization.

### One item

```json
{"Id": "76", "Title": "Chesapeake Bay Implementation Grant (CB)",
 "PostedDate": "2027-01-01T05:00:00Z", "DueDate1": "2027-06-01T04:00:00Z",
 "Details": "Grant to provide program funds to help states manage their regulatory, assessment, compliance and enforcement efforts in the Chesapeake Bay region.",
 "FullDetails": "<div class=\"ExternalClass478D7DA43A524EDDBB5EBC8CC5D11F33\">Project funds are available to implement projects that reduce nitrogen, phosphorous and sediment pollution in the area.</div>",
 "EntityEligible": "State governments in the Chesapeake Bay watershed can apply.  Projects are reviewed by the Chesapeake Bay Potomac Tributary Team ...",
 "TypeOfGrant": "Non-Competitive", "Forecasted": "Ongoing",
 "Division": "Department of Environmental Protection Division of Water and Waste Management/Office of Water Resources",
 "Guidelines": "", "HowToApply": "", "LinkToApply": "",
 "LinkTitle1": "", "LinkURL1": "", "LinkTitle20": "", "LinkURL2": "", "LinkTitle3": "", "LinkURL3": "",
 "ImportantDateTitle1": "", "ImportantDate1": "", "ImportantDateTitle2": "", "ImportantDate2": "", "ImportantDateTitle3": "", "ImportantDate3": "",
 "ContactType1": "", "ContactName1": "", "ContactPhone1": "", "ContactEmail1": "", "ContactAddress1": "",
 "ContactType2": "", "ContactName2": "", "ContactPhone2": "", "ContactEmail2": "", "ContactAddress2": "",
 "ReadMoreLinkURL": "https://dep.wv.gov/wwe/watershed/wqmonitoring/pages/chesapeakebay.aspx",
 "Created": "...", "Modified": "...", "AuthorId": "...", "EditorId": "...", "GUID": "...",
 "ContentTypeId": "0x0100...", "FileSystemObjectType": "0", "ServerRedirectedEmbedUri": "", "ServerRedirectedEmbedUrl": "",
 "ComplianceAssetId": "", "OData__UIVersionString": "...", "Attachments": "..."}
```

The response is `{"properties": [item, item, ..., ""]}`; the page filters falsy entries and so does the connector.

### What the list held on 2026-10-17

124 items from 28 divisions (DHHR Bureau for Family Assistance 24, Homeland Security 22, Arts Office 13, Economic
Development / Community Advancement 11, Behavioral Health 15, DEP 10, Rehabilitation Services 4, Broadband 4, Solid
Waste Management Board 3, Workforce WV 2, ...). `TypeOfGrant`: Competitive 56, Non-Competitive 49, Formula 9,
Pass-through 4, Renewal 3, Entitlement 1, "Competitive and applicant" 1, empty 1. By the page's own date rule: 5
active (all DEP, non-competitive), 1 posted in the future (the Chesapeake Bay grant above, 2027), 83 past due, 35
with no due date. `Forecasted` text on 36 items: `May 2023` 7, `Annual deadline of April 1st` 5 (+1 capitalised),
`Annual deadline of April 1st and October 1st` 3, `Spring 2023` 3, `Summer 2023` 3, `Fall 2023` 2, `Ongoing` 2,
`rolling deadline` 1, `March 18, 2024`, `February 19, 2024`, `October 1, 2024`, `Tentative Fall 2022`, `September 2023`,
`THIRD ROUND - GRANT OPPORTUNITY`, `No further solicitations for applications expected due to grant timelines.`,
`Awaiting announcement of next DERA award.`. `ImportantDateTitle1..3` are filled on 38 items ("Funding Opportunity
posted to Vendor Self-Service (VSS) website" 20, "Forecasted Opening Date" 9, "Intent to Apply due" 3, "Deadline to
apply" 2). No amount, match or ALN fields exist. `Modified` runs 2022-06-07 to 2026-05-18; 14 items were touched in
2026. 31 items name counties or municipalities in `EntityEligible`; one of them was active.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `wv_grants` |
| source_id | `Id` | as a string (`76`) |
| source_url | constant + `Id` | `https://grants.wv.gov/grants/Pages/grantdetails.aspx?grantid=76` |
| external_number | none | null |
| name | `Title` | whitespace collapsed, zero-width characters dropped |
| level / jurisdiction | constant | `state` / `WV` |
| administering_agency | `Division` | whitespace collapsed (the source's wording, "WV DHHR, Bureau for Family Assistance") |
| agency_code | none | null: the division names are free text, no code is stated |
| funding_type | `Title` keywords | the shared `funding_type_for` (tax credit, loan, voucher, grant, first match); no keyword → null |
| funding_source | `TypeOfGrant` | `Pass-through` → `pass_through`; everything else → `direct` (Formula and Entitlement are not claimed as pass-through: the record does not say whose money) |
| alns | none | always empty |
| amount_min / amount_max / match_required / match_pct | none | null |
| status | `PostedDate`, `DueDate1`, `Forecasted` | see status rules |
| opens_at / closes_at | `PostedDate` / `DueDate1` | ISO → date; kept as stated |
| closes_at_text | `Forecasted`, else the `ImportantDateTitleN: ImportantDateN` pairs | verbatim `Forecasted` text when present (`Annual deadline of April 1st`, `May 2023`); otherwise the important dates that carry a date, joined with `; ` as `Title: YYYY-MM-DD` (a title with no date, as on CWSRF's "Forecasted Opening Date", is dropped); empty → null |
| rolling | `Forecasted` | matches `ongoing`, `rolling`, `continuous` → True; else null |
| summary | `Details`, else `FullDetails` | HTML stripped |
| eligibility_text | `EntityEligible` | verbatim, whitespace collapsed; null when empty |
| eligibility_structured | `TypeOfGrant` | `{"type_of_grant": "Competitive"}` when present (the source's competition type, kept where SQL can see it) |
| applicant_types | `EntityEligible` | the shared keyword tagger (`connectors.maryland_drupal.applicant_types_for`); `source_code` = the matched phrase |
| categories | `Division` keywords | `Homeland Security`, `Justice` → public_safety; `Water Development` → water; `Broadband` → broadband; `Workforce` → workforce; `DHHR`, `Health`, `Behavioral`, `Family Assistance`, `Rehabilitation` → health; `Economic Development`, `Community Advancement` → infrastructure; anything else (`Environmental Protection`, `Arts`, `Solid Waste`) → other. `source_code` = the division text, so the map can be redone in SQL |

### Status rules

In order; the first that applies wins.

| The item says | Status | Why |
|---|---|---|
| `PostedDate <= today <= DueDate1` | open | the page's own "Active" |
| `PostedDate` after today | forecasted | a round announced for later (Chesapeake Bay, 2027) |
| `Forecasted` text names a month, season or full date on or after today | forecasted | `Forecasted Opening Date`-style text that is still ahead |
| `Forecasted` text names a month, season or full date before today | closed if `DueDate1` has passed, else unknown | a stale forecast ("Spring 2023") is a stale page, not a status; the MEA rule |
| `Forecasted` text with no parseable date (`Annual deadline of April 1st`, `Ongoing`, `rolling deadline`, `No further solicitations ...`) | closed if `DueDate1` has passed, else unknown | the cycle wording goes to `closes_at_text`, where the between-rounds view shows it |
| `DueDate1` before today, no `Forecasted` text | closed | the page's "Not Active" |
| no `DueDate1` | unknown | the page never shows these as Active |

Season words map to a date for the comparison only: Spring → March 1, Summer → June 1, Fall → September 1, Winter →
December 1; a month name → the first of the month; "Tentative" and trailing punctuation are ignored. Nothing from
that comparison is written to a date column.

`resolve_missing(source_id)`: re-read the list. The item still there (the list shifted under us) → the rules above
with `closes_at`; gone → `unknown` (an item leaving the list is not a closure the source stated); the API unreachable
→ `None`, which the pipeline records as `unknown`.

### Change detection

The record hash covers the mapped fields only; `Modified`, `Created`, `EditorId` and the contacts stay in the payload
and never change the hash. `prior` is accepted and ignored: the whole list is one request.

## Decisions (defaults; override at review)

1. **Status follows the page's own filter, then the MEA rules for forecast text.** Active and future-posted are the
   portal's definitions; a `Forecasted` text is a forecast only while the date in it is ahead, otherwise it is cycle
   wording for the between-rounds group or a stale page.
2. **`Formula` and `Entitlement` are not pass-through.** Four items say `Pass-through`; the others say how the money is
   competed, not where it comes from.
3. **No agency code.** Twenty-eight free-text division names; a code would be invented. The exporter falls back to the
   agency name.
4. **Categories by division keyword, with the division as `source_code`.** Coarse on purpose; DEP's water and mine-land
   grants both land in `other` until a second source makes a title-keyword map worth writing.
5. **Important dates become `closes_at_text` only when `Forecasted` is empty.** They are labelled milestones ("Intent
   to Apply due"), not a second deadline column.
6. **Fixtures**: one API response trimmed to the items `78` (active, CWSRF, municipalities named), `76` (posted 2027,
   `Ongoing` → forecasted, rolling), `201` (SWMB FY2027, past due, municipal), `131` (Arts, past due, `Annual deadline
   of April 1st` → closed with cycle text), `141` (`rolling deadline`, past due → closed, rolling), `142` (no dates,
   "No further solicitations" → unknown), `95` (no dates, `Spring 2023` → unknown, stale forecast), `94` (CDBG, past
   due), one `Pass-through` item, and one item whose `Forecasted` text is a future month or whose important dates are
   filled, chosen by the probe on the day.

## Known gaps (the source's wording, not the parser's)

- "State governments in the Chesapeake Bay watershed can apply" tags nothing: the shared keyword map knows `state agencies`, not `state governments`. Adding the phrase is a shared-map change that touches the Maryland connectors; left for the next case that needs it.
- Eight of the ten fixture items land in category `other`: the division map is coarse by design (decision 4).

## Out of scope

- The wvOASIS Vendor Self Service portal (CGI Advantage), where applications are filed: a single-page app behind the
  state's procurement system; not read.
- Agency sites (WVCAD, DEP) for the rows the portal does not carry.
- `LinkToApply`, `ReadMoreLinkURL`, `HowToApply`, `Guidelines`, contacts: in the payload, not mapped.

## Verification

1. `uv run ruff check .` and `uv run pytest -q` green against fixtures only.
2. On a scratch database: a full run (one request): about 124 added; a second run: 0 changed, 0 missing.
3. `SELECT name, status, opens_at, closes_at, closes_at_text, rolling FROM program WHERE source_connector='wv_grants'
   ORDER BY status, closes_at;` against the page's own Active / Not Active / Forecasted filters for `78`, `76`, `131`.
4. `SELECT COUNT(*) FROM v_navigator_program WHERE state='WV';` (expected small: the one active municipal item) and
   `v_navigator_between WHERE state='WV'` (the 2025 and 2026 municipal rounds); `cli.py export` shows a WV page.
