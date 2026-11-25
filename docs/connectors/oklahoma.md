# Oklahoma's agency pages: survey (12.9, 2026-11-24)

Oklahoma has no public state index (`docs/surveys/state_portals.md`: OKGrants and the Oklahoma Grant Exchange are logins).
Breadth first (Saj, milestone 12.9): the CDBG agency, then a second agency only if cheap. Surveyed read-only with the
connectors' User-Agent, 3 s or more between requests, pages saved and read from disk.

| Agency | Host | CMS | robots | Result | Verdict |
|---|---|---|---|---|---|
| Department of Commerce (CDBG, community development) | `www.okcommerce.gov` | WordPress + Elementor, nginx | `User-agent: *`, only `wp-admin`, `wp-includes`, plugin, cache, search, feed, tag and author paths disallowed; no `ClaudeBot` rule, **no `Crawl-delay`** | 200 on every page asked | **readable, built** (`ok_commerce`) |
| Oklahoma Grant Exchange (OGX), where every CDBG application is filed | `ogx.ok.gov` | login-only portal | `Disallow: /` (the caller's survey) | never fetched | **not read** |
| OKGrants (`grants.ok.gov`, the SITES/PREP rounds' portal) | `grants.ok.gov` | login | not asked (off the network allowlist) | never fetched | **not read** |
| ODOT, Water Resources Board (OWRB), Emergency Management, DEQ, Tourism and Recreation | other hosts | not surveyed | not asked: only `www.okcommerce.gov` is on this session's network allowlist | never fetched | **not surveyed** (follow-up) |

## What Commerce gives

The CDBG hub (`/community-development/local-governments-edos/community-development-block-grant-programs/`) is one page:
"Eligibility", "Application" (everything is filed in OGX), meeting dates and a public-hearing notice, "Program Results",
then **"Programs"**: an `h3` and one paragraph per program, each with a link to its 2026 guidance PDF, then "Resources".
**No program states a round**: the dates on the page are trainings, a State Plan hearing and its comment period. The
rounds are in the guidance PDFs and in OGX. So every CDBG record is `unknown` ("Status not confirmed").

## Scope, one record per program (the split rule)

Surveyed: the hub and four more pages. Built: two pages, eight records.

- **In, the hub's seven programs**: Capital Improvement Planning (CIP), Small Cities, Community Revitalization,
  Water-Wastewater Construction, Economic Development Infrastructure Financing (EDIF), Water + Wastewater Engineering,
  Rural Economic Action Plan (REAP).
- **Out, on the hub**: the Coronavirus Relief Program (CDBG-CV, a closed one-time appropriation whose link is a reporting
  page) and the three CDBG Disaster Recovery entries (the brief's rule). The DUNs/UEI how-to, "Save the Dates", the State
  Plan notice (its "comments will be accepted until December 18, 2026" is a comment period, not a round) and "Resources"
  are not read.
- **In, the Oklahoma Disaster Mitigation and Recovery Matching Fund (ODMRMF)**
  (`/reporting-compliance/oklahoma-disaster-mitigation-and-recovery-matching-fund-program/`): state money that leverages
  federal mitigation grants. **Its applicants are the eleven Substate Planning Districts / Councils of Government, not
  towns**; it is in because a COG is a body of local governments and the page says the fund exists "to help local
  governments and related entities". A scope call for Saj: one line in `PAGES` to drop.
- **Out, Oklahoma Main Street** (`/community-development/main-street-revitalization/`, which redirects to
  `/community-development/oklahoma-main-street/`): the page carries a dated line for the Main Street Incentive Program
  ("Applications open September 1, 2026 and close September 30, 2026") but never says who applies; the program reads as
  an incentive for development in Main Street districts. Not built without the applicant; follow-up.
- **Out, the SITES Program**: its two PREP Fund rounds are 2023 and 2024 ("Additional details and timelines will be
  announced when available"), applications in OKGrants.
- **Out, Community Incentives**: Remote Quality Jobs, the Quality Events Act, the P3 Pooled Finance Program and the
  Enterprise Zone Incentive Leverage Act are one paragraph each on a page of incentives (the brief leaves tax incentives
  out). The Leverage Act and Quality Events do pay local governments: follow-up if Saj wants them.
- **Out by the brief**: CSBG, ESG and Weatherization (community action agencies), every CDBG-DR page.

## Sample of the raw data (the hub, 2026-11-24)

```
h1  Community Development Block Grant Programs
h2  Eligibility
p   Eligibility is generally limited to units of general local government such as cities, towns, and counties.
h2  Application
p   All grant applications must be submitted through Oklahoma Grant Exchange (OGX). See guidance documents for each
    program for complete details.
h2  DUNs Number and Unique Entity Identifier ...                         (section not read)
h2  Save the Dates ...                                                    (section not read)
h2  Notice: State Public Input Session & Hearing Plan Year 2027 ...       (section not read)
h2  Program Results
p   ... Our Community Development team administers Community Development Block Grants (CDBG) from the U.S. Department of
    Housing and Urban Development (HUD) to support economic development in Oklahoma communities. ...
h2  Programs
h3  Capital Improvement Planning (CIP)
p   This grant opportunity provides funding for units of general local government (cities, towns, and counties) to
    undertake a comprehensive inventory of all governmentally owned assets. ...
li  CIP Guidance                                                          (a PDF link, not read)
h3  CDBG Small Cities
p   Oklahoma's Small Cities program helps fund infrastructure and economic improvement projects for Oklahoma communities
    with a population between 15,000 and 50,000 ...
...
h3  CDBG Coronavirus Relief Program (CDBG-CV)                             (a tail: no record)
h2  Resources                                                             (the read stops)
```

## Field mapping

The agency-page table in `connectors/hand_list.py`, with a reader of this module's own (WordPress + Elementor; Arkansas's
WordPress base reads another theme, and no second Oklahoma agency is read).

- **Text**: `div.elementor-location-single` (the page template's body: the `h1` and the content; the header, footer and
  pop-ups are other Elementor locations). Icon lists (the PDF link labels) and forms are removed. A section whose `h2` is
  the DUNs how-to, "Save the Dates" or the "Notice: ..." is not read; the read stops at "Resources", "Policies &
  Procedures", "Annual Reporting" or "Your ... Team". Lines with a phone number or an e-mail address are dropped.
- **Records**: the hub through `SPLITS`, one per `h3` under "Programs"; "Eligibility", "Application" and "Program Results"
  sit above the first program and follow each record. CIP, the first, keeps the page's id `cdbg`; the others are
  `cdbg#small-cities` and so on. ODMRMF is its page.
- `name`: the hub's records are named by hand from their headings, with "CDBG" in front where the heading omits it; ODMRMF
  from its `h1`.
- `status`: the shared table. No sentence states a round on either page, so `unknown`.
- `eligibility_text`, applicants: the sentence under "Eligibility" (hub); the "Eligible Applicants" list (ODMRMF).
- `funding_source`: the shared rule (the hub names HUD: `pass_through`; ODMRMF is "provided by the State Treasury":
  `direct`).
- Categories: `community development`; the two water and wastewater programs `environment and water`; ODMRMF `emergency
  mitigation`.
- Amounts are not parsed (the hub states none).
- `ODMRMF`: its purpose sentence ("dedicated state funding to help local governments and related entities secure ...
  federal ... funds") matches the shared applicant rule ("funding to ... local governments") and would tag municipality and
  county; the module drops that line from the applicant lines, so the record's applicants are the "Eligible Applicants"
  section alone and it carries **no applicant tag** (the tagger has none for a council of governments).

## Implemented (2026-11-24)

`connectors/ok_commerce.py` (`AGENCY_CODE` `OK-COMMERCE`, `DELAY_S = 3.0`), `scripts/probe_oklahoma.py` (saved the
fixtures; its scrub also removes the Elementor header, footer and pop-ups, the team carousel and every line with an e-mail
address, a phone number or a named contact), `tests/test_oklahoma.py` (6 tests). One live probe run, 2026-11-24, 2 GETs,
no errors. The module was not run through `cli.py run` (the pipeline's registry is edited centrally), so no database run
is recorded here. The probe's lines:

```
== ok_commerce
  cdbg                                unknown  open=None close=None pass_through ['county', 'municipality'] |
  cdbg#small-cities                   unknown  open=None close=None pass_through ['county', 'municipality'] |
  cdbg#community-revitalization       unknown  open=None close=None pass_through ['county', 'municipality'] |
  cdbg#water-wastewater-construction  unknown  open=None close=None pass_through ['county', 'municipality'] |
  cdbg#edif                           unknown  open=None close=None pass_through ['county', 'municipality'] |
  cdbg#water-wastewater-engineering   unknown  open=None close=None pass_through ['county', 'municipality'] |
  cdbg#reap                           unknown  open=None close=None pass_through ['county', 'municipality'] |
  odmrmf                              unknown  open=None close=None direct       [] |
```

(The live run printed each tag once per phrase that carries it, "cities", "towns", "counties", "units of general local
government"; they are shown here once.) The fixtures were scrubbed of contacts after the run; every record's payload is
identical before and after.

| Record | Status on 2026-11-24 | Applicants tagged | Source |
|---|---|---|---|
| CDBG Capital Improvement Planning (CIP) | unknown (no round stated) | municipality, county | pass_through (HUD) |
| CDBG Small Cities | unknown | municipality, county | pass_through |
| CDBG Community Revitalization | unknown | municipality, county | pass_through |
| CDBG Water-Wastewater Construction | unknown | municipality, county | pass_through |
| CDBG Economic Development Infrastructure Financing (EDIF) | unknown | municipality, county | pass_through |
| CDBG Water + Wastewater Engineering | unknown | municipality, county | pass_through |
| CDBG Rural Economic Action Plan (REAP) | unknown | municipality, county | pass_through |
| Oklahoma Disaster Mitigation and Recovery Matching Fund Program (ODMRMF) | unknown | none (planning districts and councils of government) | direct (State Treasury) |

Requests to `www.okcommerce.gov` in this session: 7 (the hub and four pages in the survey, two in the probe), plus the
caller's `robots.txt` and home page.

### Gaps and follow-ups

- **Rounds**: the 2026 guidance PDFs linked under each program (`/wp-content/uploads/2026-CDBG-...-Application-Guidelines.pdf`)
  and OGX hold the dates; the page holds none, so all seven stay "Status not confirmed". Hand-quoting the deadlines from
  the guidance PDFs is the MDOT precedent, a session of its own. The PDFs were not opened.
- **REAP's applicants**: the page says only that it was "developed in partnership with the Substate Planning Districts";
  the record carries the hub's general eligibility sentence. Its guidance PDF would say who files.
- **ODMRMF** is in on a scope call (its applicants are councils of government); drop its `PAGES` line if Saj reads the
  navigator as towns only.
- **Main Street Incentive Program** (dated: "Applications open September 1, 2026 and close September 30, 2026", now past):
  build when a page says who applies. **12.11 (2026-11-25)**: the "Application" page (`/oklahoma-main-street/application/`)
  was read once: it is the application to become a Main Street program (a designation: "Interested communities will then
  submit a Letter of Intent by November 13, 2026, followed by the full application by January 8, 2027"), not the
  incentive grant, so not built; the incentive program still has no page that names its applicant.
- **Community Incentives**: the Enterprise Zone Incentive Leverage Act (state match for local units of government) and the
  Quality Events Act (communities reimbursed for hosting events) pay local governments; one paragraph each, no round.
- **SITES / PREP Fund**: restore if a new round is announced ("Additional details and timelines will be announced").
- Other agencies (ODOT's local programs and TAP, OWRB's loans and REAP grants, Emergency Management's mitigation, DEQ,
  Tourism and Recreation's LWCF and RTP) were not surveyed: their hosts are not on this session's network allowlist.
- No shared-rule change was needed for Oklahoma beyond the purpose-sentence case above (a rule that reads "funding to help
  local governments" as naming a beneficiary, not an applicant, would remove the module's filter).
