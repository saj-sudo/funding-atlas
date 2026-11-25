# Georgia's agency pages: survey (12.9, 2026-11-24)

Georgia has no public state index with structured rows (`docs/surveys/state_portals.md`). Surveyed read-only with the
connectors' User-Agent, 3 s apart, every page saved and read from the saved copy. One agency, the breadth-first rule.

| Agency | Host | CMS | robots | Answer | Verdict |
|---|---|---|---|---|---|
| Department of Community Affairs (DCA), with the OneGeorgia Authority's pages | `dca.georgia.gov` | Drupal (the state's GovHub theme), behind Cloudflare | the stock Drupal file: `User-agent: *`, no `ClaudeBot` rule, no `Crawl-delay`, nothing under `/financing-tools` or `/community-assistance` disallowed | 200 on all fifteen requests, no challenge | **readable**, built (`ga_dca`) |

Cloudflare obscures the e-mail addresses in the pages ("[email protected]"); it did not challenge any request. No other
Georgia host was requested (only this one is on the session's allowlist).

## What DCA would give

"Financing Tools > Infrastructure" holds the programs a local government applies to. Its menu, read from the page:

- **Community Development Block Grants (CDBG)**: Annual CDBG Competition, CDBG Innovative Grant, CDBG Section 108 Loan,
  Employment Incentive Program, Immediate Threat and Danger, Redevelopment Fund, Revolving Loan Fund, and reference pages
  (Revitalization Area, Consolidated Plan, Compliance, photo galleries).
- **OneGeorgia Authority**: Equity Fund (with Site Development Initiative, Workforce Housing Initiative and Workforce
  Housing Construction Loan under it), EDGE Fund.
- Appalachian Regional Commission, Southeast Crescent Regional Commission, Neighborhood Stabilization Program.
- Elsewhere on the site: Rural Downtown Redevelopment Grant, REBA, the Downtown Development Revolving Loan Fund, Certified
  Local Government Grants and the Georgia Heritage Grant (Historic Preservation), CHIP, the tax incentives, CDBG-DR.

## Scope, one record per program page

Surveyed: two hubs and six program pages. Built: five.

- **In**: the Annual CDBG Competition; the three CDBG set-asides a local government applies to, Employment Incentive
  Program (EIP), Redevelopment Fund (RDF) and Immediate Threat and Danger (ITAD); the OneGeorgia Equity Fund.
- **Rural Downtown Redevelopment Grant: out.** "This program is no longer accepting applications. Awards for this one-time
  funding were made in June 2022." (South Dakota's closed one-time grant rule).
- **Out, by the brief**: CDBG-DR; the tax incentives (job tax credits, opportunity zones, enterprise zones); the EDGE Fund
  and REBA (deal-closing funds for a company's location); the small-business credit programs.
- **Out, not surveyed** (the request budget, about fifteen a host): CHIP (the home page links a 2026-10-02 press release,
  "DCA announces the availability of $10 million in 2027 CHIP program grants"; its program page was not looked for), CDBG
  Innovative Grant, Section 108, the Revolving Loan Fund page, the Equity Fund's three sub-pages, ARC and SCRC, DDRLF, the
  two historic preservation grants.

## Field mapping

The agency-page table in `connectors/hand_list.py`, with a reader of this module's own (no other Georgia agency is read):

- **Text**: `main.content-page__main`. The embedded cards (`article.embedded-entity`) are dropped: the contact card, a
  flyer, "OneGeorgia Equity Regulations", "Documents & Downloads". **A card whose title starts "Apply" is kept as a
  heading.** The read stops at "Frequently Asked Questions"; the "Review the ... FAQs here" line is dropped.
- `name`: the `h1` (it sits in a `header` inside `<main>`, so the fixtures keep headers there). "Equity Fund" is stored as
  "OneGeorgia Equity Fund" and "Immediate Threat and Danger" as "Immediate Threat and Danger Program" (the page's own
  first words).
- `status`: **`unknown` on every page today; no page dates a round.** The Annual Competition's only round line is the
  card "Apply for the FY2027 CDBG Annual Competition" (a fiscal year, no date, no "open"): kept as `closes_at_text`. The
  Equity Fund's "Online Applications are accepted quarterly on the 2nd Friday of the following months:" and its list
  (January, April, July, October) are joined into one sentence and kept; a weekday rule with no year is not a date.
- `eligibility_text` and applicants: the "Eligible Applicants" section where the page has one (Annual, Equity) and the
  eligible-applicants sentence (ITAD). RDF and EIP say who receives the money without an eligibility word ("The RDF
  provides local governments access to flexible financial assistance ...", "A provider of infrastructure financing to
  local governments ..."); the module adds those sentences. **HUD's "units of general local government" / "units of
  general purpose local government" is tagged as "units of local government"** (municipality, county), and what follows
  "excluding" (entitlement cities and urban counties) is not tagged; the stored text is the page's wording, unchanged.
- `funding_source`: set by hand. The four CDBG pages are `pass_through`: each says it is the state CDBG program or a
  set-aside of it, and DCA's Infrastructure page says "The CDBG Program is a federally-funded grant for states". The Equity
  Fund is `direct` (the OneGeorgia Authority's own; the page names no federal source).
- `match_required`: null on the Annual Competition by hand ("Grants up to $500,000 ... no matching funds required", 5%,
  10%, 15% above that: it depends on the grant). ITAD's "provides 50% matching funds ... Local funds must comprise at least
  10% of project costs" is not a wording the match reader knows: null.
- `funding_type`: `grant` on all five. The Equity Fund's page says "grants, loans and any other forms of assistance"; the
  model holds one type, and its name carries no keyword.
- Maximum awards ("$1,000,000 for Single-Activity", "$500,000 per project") are not parsed; they stay in the stored text.

## Sample of the raw data (Annual CDBG Competition, 2026-11-24)

```
h1  Annual CDBG Competition
card  Contact CDBG  [email protected]                                   (dropped)
p   The Community Development Block Grant Program (CDBG) provides funding to assist a wide range of eligible activities,
    including housing improvement projects, public facilities such as water and sewer lines, ...
p   The maximum amount available per applicant is $1,000,000 for Single-Activity during regular competition and
    $1,500,000 for Multi-Activity during regular competition.
card  h2 Apply for the FY2027 CDBG Annual Competition   [Apply Now]     (the title is kept as a heading)
h2  Local Match Requirements - Annual Competition
li  Grants up to $500,000, or grants for single activity housing projects - no matching funds required.   (three more)
h2  Eligible Applicants
p   Eligible applicants are units of general local government, excluding metropolitan cities, urban counties, and units
    of government eligible to participate in the urban counties or metropolitan cities programs of the U.S. Department
    of Housing and Urban Development. ...
card  h2 Annual CDBG Competition: Documents & Downloads                 (dropped)
```

## Implemented (2026-11-24)

`connectors/ga_dca.py`; `scripts/probe_georgia.py` saved the fixtures (`tests/fixtures/ga_dca/`, contact cards removed);
`tests/test_georgia.py`. The module is not in `pipeline/run.py` or the workflow yet (done centrally), so no run against the
database has been made. The probe's live read, 2026-11-24:

```
== ga_dca
  cdbg-annual                                unknown    open=None close=None pass_through ['municipality', 'county', 'municipality', 'county'] | Apply for the FY2027 CDBG Annual Competition
  cdbg-eip                                   unknown    open=None close=None pass_through ['municipality', 'county'] |
  cdbg-redevelopment                         unknown    open=None close=None pass_through ['municipality', 'county'] |
  cdbg-itad                                  unknown    open=None close=None pass_through ['municipality', 'county', 'municipality', 'county'] |
  onegeorgia-equity                          unknown    open=None close=None direct       ['municipality', 'county', 'municipality', 'county', 'special_district'] | Online Applications are accepted quarterly on the 2nd Friday of the following mo
```

| Record | Status on 2026-11-24 | Applicants tagged | Source |
|---|---|---|---|
| Annual CDBG Competition | unknown: "Apply for the FY2027 CDBG Annual Competition" (kept, no date) | municipality, county | pass_through |
| Employment Incentive Program | unknown (no round stated) | municipality, county | pass_through |
| Redevelopment Fund | unknown (no round stated) | municipality, county | pass_through |
| Immediate Threat and Danger Program | unknown (no round stated) | municipality, county | pass_through |
| OneGeorgia Equity Fund | unknown: "accepted quarterly on the 2nd Friday of ... January, April, July, October" (kept) | municipality, county, special district (development authorities) | direct |

### Gaps and follow-ups

- **Every record is `unknown`.** The Annual Competition's dates are in its application manual and DCA's news posts, not on
  the page; EIP, RDF and ITAD are probably open year-round but their pages do not say so.
- **Wanted, not made (shared rules)**: (1) the tagger does not know "units of general local government" or "units of
  general purpose local government" (HUD's term, on every state's CDBG page); the module rewrites it for tagging; (2) the
  tagger reads "cannot" anywhere in a sentence as a negation of who may apply ("... projects that cannot be undertaken with
  the usual ... programs"), so the module tags RDF's and EIP's recipient sentences by their matched phrase; (3) the
  applicant-sentence reader does not know "provides local governments access to" or "financing to local governments";
  (4) the match reader does not know "provides 50% matching funds" or "Local funds must comprise at least 10%".
- **12.11 (2026-11-25): four more records, 9 in all.** **CHIP** (`/affordable-housing/housing-development/
  home-investment-partnerships-program-home/community-home`): "The 2027 CHIP grant cycle is now open through January 31,
  2027", so `open`, closing 2027-01-31; "Eligible Applicants: Local Governments, Nonprofits ..., Public Government
  Authorities"; HUD's HOME money, `pass_through`; category housing. Two reading changes, both local to this module and
  measured (no other fixture record moved): the page prints its round in an "Application Portal" section after
  "Documents & Downloads", where the read stops, so that one section is read first (`PORTAL_RE`); and an open round's
  "open through <date>" is its closing date (`OPEN_THROUGH_RE`; the shared reader takes "through" only beside
  "accepting"; a third case would lift it). **DDRLF** (municipalities and counties of 100,000 or less and development
  authorities; a loan, "accepted throughout the year and as loan funds are available", `unknown`): the small-business
  template prints no `h1`, so its name is the page's `<title>` before " | Georgia ...". The Equity Fund's **Site
  Development Initiative** ("Applicant must be a development authority", tagged `special_district`) and **Workforce
  Housing Initiative** ("Units of general-purpose local government ... as well as local, regional, and state
  authorities"; quarterly, `unknown`; category housing). One live run on the restored database: added 4 (the second run
  was skipped to stay near the host's request budget: 18 requests to `dca.georgia.gov` this session).
  **Surveyed and left out** (page names no applicant): CDBG Innovative Grant ("allow our local governments flexibility"
  is not an applicant sentence), ARC ("eligible applicants", unnamed), SCRC (no applicant; its pre-application deadline was
  May 27, 2025). Not opened: Section 108, the Revolving Loan Fund, Rural Workforce Housing Construction Loan, Certified
  Local Government Grants, the Georgia Heritage Grant, and the HOME page.
- Other Georgia agencies (GDOT's LMIG and TA, GEFA's water loans, GEMA's mitigation, DNR's LWCF and trails) are on hosts
  this session could not reach and were not requested.
