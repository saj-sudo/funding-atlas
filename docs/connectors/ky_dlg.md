# Kentucky DLG Portal connector (`ky_dlg`): source, raw data and field mapping

Milestone 12.5, the JavaScript shells. Written 2026-11-04 from a read-only probe of the portal, before the parser. The
50-state census (`docs/surveys/state_portals.md`) recorded Kentucky's Department for Local Government portal as a
Dynamics-style "EYGA Grants Management Portal" whose Opportunities tab is a JavaScript shell, and stopped there. The
probe found what New York's had: the shell's grid is filled by one plain GET the page itself makes, answered with
JSON by a server-side template, no login and no token. So the stop rule does not apply and the connector reads that
JSON plus one server-rendered page per opportunity.

## Implemented (2026-11-04, same day)

`connectors/ky_dlg.py` follows this doc. First live run on a fresh database: 4 added in 4 seconds (two JSON lists, four
pages), 0 errors; second run 0 changed. All four `open`, no dates. Applicants: LMPP municipality and county ("City
governments, County governments"), Legislative Line-Items municipality and county ("distribution to local
governments"), LGEDF county ("eligible coal-producing counties"), RDAAP nothing (special district since 10.4). The Kentucky page: 2 open municipal
rows (Line-Items, LMPP). Found while writing the parser:

- the template leaves its last `h2` unclosed (`<h2>Application Process<h2>`), so the last section nests inside the
  heading; sections are read by their label element (`.xrm-attribute-value`), not by `h2` siblings;
- LMPP's applicant list runs into bulleted requirements with no sentence break, and one bullet says "DLG will not fund
  more than 50%", which dropped the whole line as a negation; bullets and starred headings now end a line;
- "The Local Government Economic Development Fund (LGEDF)" tagged a municipality from the program's own name; a
  Title Case name followed by its acronym is removed before tagging;
- **a shared-tagger gap, closed the same day (roadmap 10.4)**: RDAAP's "grants to Special Purpose Governmental
  Entities ... and in partnership with county governments" tagged nothing, because the tagger had no rule for special
  districts at all. `connectors/text.py` now reads "special (purpose) district(s)" and Kentucky's statutory "Special
  Purpose Governmental Entity" / "SPGE(s)" as `special_district`: RDAAP tags `special_district`, Line-Items ("local
  governments, public agencies, SPGEs") gains it. "In partnership with county governments" stays untagged on purpose:
  the counties authorize the grant by Fiscal Court resolution, the grantee is the SPGE.

## The source

`https://www.dlgportal.ky.gov/en-US/grants/` (Microsoft Power Pages; `robots.txt` answers 404, so nothing is
disallowed). The page lists the portal's programs and tags in its own script and fills its results table by calling

```
GET /en-US/Services/GetGrantOpportunities/?page=1&applicationStatus=Open
```

(the unprefixed `/Services/...` path answers 302 to the `/en-US/` one). The answer is a Liquid web template that
prints JSON after a few blank lines:

```json
{
    "moreRecords": false,
    "totalRecordCount": 4,
    "itemsPerPageCount": 10,
    "results": [
        {
            "name": "Local Match Participation Program",
            "program": "Local Match Participation Program",
            "startdate": "",
            "enddate": "",
            "shortname": "LMPP",
            "applandingpage": "/FCLMPP/LMPP",
            "programlandingpage" : "/FCLMPP"
        }
    ]
}
```

The status filter on the page has two values, `Open` and `Expired`. On 2026-11-04: Open 4 rows (Legislative Line-Items
and Special Programs, LGEDF Coal Severance, Local Match Participation Program, Regional Development Agency Assistance
Program), Expired 0. No row carries a start or end date. The portal's program dropdown also names the CDBG-DR 2021 and
2022 programs (housing, infrastructure, small business, resilience planning); none of them has an opportunity in
either list today, so none becomes a record.

Each `applandingpage` (under `/en-US`) is server-rendered:

```html
<main class="page-content page-opportunity-details">
  <div class="banner"><div class="container">
    <h1 class="program-title">Local Match Participation Program</h1>
    <div class="override-rich-text"> ... the summary ... </div>
  </div></div>
  <div class="body-content"><div class="container">
    <h2> ... Eligibility Criteria ... </h2>
    <div class="override-rich-text"> ... </div>
    <h2> Required Documentation </h2> ...
    <h2> Award Details </h2> ...
    <h2> Application Process </h2> ...
```

LMPP's Eligibility Criteria: "Eligible applicants: City governments, County governments, Joint applicants (City-County
or Multiple Counties)." RDAAP's banner: "a system of grants to Special Purpose Governmental Entities ... and in
partnership with county governments." LGEDF: "eligible coal-producing counties". Line-Items: "entities identified in
legislative appropriations and designated to the Kentucky Department for Local Government for distribution to local
governments, public agencies, SPGEs, and other authorized recipients."

Requests per run: two JSON GETs (Open, Expired; more pages only while `moreRecords` is true) and one page per row,
with the shared 0.3-second pause.

## Field mapping

| Program field | From |
|---|---|
| `source_id` | `shortname` (`LMPP`, `LLISP`, `LGEDFSCCS`, `RDAAP`) |
| `source_url` | `https://www.dlgportal.ky.gov/en-US` + `applandingpage` |
| `name` | the page's `h1.program-title`, else the row's `name` |
| `level`, `jurisdiction` | `state`, `KY` |
| `administering_agency`, `agency_code` | Kentucky Department for Local Government, `KY-DLG` |
| `funding_type` | `funding_type_for(name)`, else `grant` (every row is a grant program) |
| `funding_source` | `direct` (state bond funds, coal severance, General Assembly appropriations) |
| `status` | the list the row came from: `Open` → `open`, `Expired` → `closed` |
| `opens_at`, `closes_at` | `startdate`, `enddate` when present (US `M/D/YYYY`, time dropped); null today |
| `rolling` | null: the portal states no window, and an empty date is not a promise |
| `summary` | the banner text |
| `eligibility_text` | the Eligibility Criteria section |
| `eligibility_structured` | `required_documentation`, `award_details`, `application_process`: the other sections verbatim |
| `applicant_types` | the shared tagger over the Eligibility Criteria sentences plus the banner sentences that name a recipient ("grants to", "eligible", "applicant"), negated sentences dropped |
| `categories` | none: the portal's tags (Coal Severance, Line Item, LMPP, RDAPP) are program codes, not topics |
| `amount_*`, `match_*`, `alns`, `external_number` | null or empty: the pages state none |

## Decisions

1. **Status is the portal's own filter.** A row listed under `Open` is open on the run date; under `Expired`, closed.
   The portal states no dates, so none is stored and `rolling` stays null.
2. **A row that leaves both lists** becomes `unknown` (`hand_list.resolve_missing`), the WebGrants rule.
3. **A page that cannot be read** keeps the stored page by `shortname` (the hand-list fallback); a list that cannot be
   read raises, because without it nothing is known.
4. **No CDBG-DR records** until the portal lists an opportunity under one of those programs.
5. **The banner's recipient sentence counts** (RDAAP names its grantees only there); other banner sentences do not,
   because the banners also describe what the money is for.
