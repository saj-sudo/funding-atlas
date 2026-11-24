# Hawaii: survey, stopped (12.9, 2026-11-24)

Hawaii has no public state grants index (`docs/surveys/state_portals.md`) and no municipalities: four counties (Honolulu,
Hawaii, Maui, Kauai) are its only general local governments, and HUD sends CDBG to each of them directly, so the state runs
no "small cities" CDBG competition for a town to apply to. The breadth-first rule (the community development agency first)
therefore lands on DBEDT, the Department of Business, Economic Development and Tourism.

| Agency | Host | CMS | robots | Read | Verdict |
|---|---|---|---|---|---|
| DBEDT | `dbedt.hawaii.gov` | WordPress (the state's `hawaii.gov` theme) | `User-agent: *`, `Crawl-delay: 10`, no `Disallow`, no `ClaudeBot` rule | home page and `/site-map/`, 10 s apart, both 200 | **nothing a county applies for; no connector** |

## What the two pages hold (read 2026-11-24)

The home page's menu: About Us, News, Director's Memoranda, DBEDT Reports, Latest Additions, State Careers; tiles for
Business Resources, Energy (`energy.hawaii.gov`), Economy (data and the Data Book), Foreign Trade Zone, Creative Industries
(`cid.hawaii.gov`) and Census. The site map lists every page of the WordPress site:

```
Accessibility | Business Resources | Contact | DBEDT Notice Under the ADA | Hawaii Genuine Progress Indicator |
DBEDT Websites | Information Resources | Language Access | Maui Economic Recovery | News Archive | News Releases |
Outlook for the Economy | Annual Reports & Reports to the Legislature | NELHA Reports 2022-2023 |
DBEDT Legislative Reports Archive | Pathways to Recovery | Search Results | Site Map |
Tax Credit for Research Activities (TCRA) & Hawaii Film Tax Credit | Frequently Asked Questions
```

No page is a grant or loan program with a public agency as its applicant. What the site does carry is out of scope by the
brief's own rules: business resources, two tax credits (business tax incentives), economic statistics, and news (the newest
release is the Hawaii Green Infrastructure Authority's loans to homeowners for cesspool conversions: individuals).

## Decision

**Stopped, no connector.** Nothing was stretched to make a record: a county cannot apply for anything this host lists.

## Gaps and follow-ups

- DBEDT's attached agencies keep their own sites (the tiles and the "DBEDT Websites" page point to them): the State Energy
  Office (`energy.hawaii.gov`), the Hawaii Green Infrastructure Authority, HHFDC (housing finance), HCDA, the Office of
  Planning and Sustainable Development (coastal zone management). None is on the session's network allowlist and none was
  requested; whether any of them runs a program a county applies to is **not verified**.
- The "DBEDT Websites" and "Business Resources" pages themselves were not opened (two requests were enough to see the site
  has no program pages; the 10 s crawl delay was honoured).
- Hawaii's other candidates for a later look, none surveyed: the Department of Health's Clean Water and Drinking Water State
  Revolving Funds (the four county water and wastewater agencies are the borrowers), HDOT's local programs, HI-EMA's FEMA
  pass-throughs.
