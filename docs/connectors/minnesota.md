# Minnesota: DEED on mn.gov, stopped at Radware's bot manager (12.9, 2026-11-24)

Minnesota's state grants index was stopped in 12.8a (it lists agencies, by script, behind Radware). It is an agency state,
and the agency a town would start with is the Department of Employment and Economic Development (DEED), on `mn.gov`.

| Agency | Host | robots | Result | Verdict |
|---|---|---|---|---|
| DEED (Small Cities Development Program, Greater Minnesota Public Infrastructure, cleanup and redevelopment grants) | `mn.gov/deed` | `User-agent: *` disallows only cgi and two archive paths; **`Visit-time: 0000-1200`** (GMT) and **`Request-rate: 10`** | first page 200; then **302 to `validate.perfdrive.com`**, Radware Bot Manager's challenge | **stopped for good** |

## The visiting hours

`mn.gov/robots.txt` says `Visit-time: 0000-1200` ("0000-1200 GMT is 6PM to 6AM here"). The daily workflow's schedule is
`cron: "17 9 * * *"` (`.github/workflows/site.yml`), 09:17 UTC, inside the window, so the visiting hours alone would not
have stopped a connector. Every request of this survey was made between 00:27 and 00:31 GMT.

## What happened (2026-11-24, connectors' User-Agent)

1. `GET /deed/government/financial-assistance/` → 200, 468 kB, the full server-rendered page (`.jsp` paths).
2. Five further GETs through the survey script over the next minute (two program pages, retried) all failed in the client
   with a name-resolution error, which is what a redirect to a plain-`http` host looks like from behind the development
   proxy. They are counted as requests that reached `mn.gov`.
3. Two GETs with `curl`: one program page answered 200, the next 302 to its own directory address, both setting
   `__uzma`, `__uzmb`, `__uzmc`, `__uzmd`, `__uzme` cookies (ShieldSquare, now Radware Bot Manager).
4. One GET with redirects off, to see the answer itself:
   `302 Location: http://validate.perfdrive.com/<site id>/?ssa=...&ssc=https://mn.gov/deed/...&ssk=support@shieldsquare.com&sst=funding-atlas/0.1 ...`.
   `validate.perfdrive.com` is Radware Bot Manager's captcha page. The redirect was not followed.

Nine requests in about three and a half minutes. Most were 10 s apart; some of the retries were closer than that, which is
tighter than `Request-rate: 10` if it means one request per ten seconds. The rule for this state was: a Radware captcha on
any request ends Minnesota. It did, on the second page asked for.

A daily connector would ask for seven or eight pages in a row and would meet the same redirect; reading the one page that
gets through and falling back for the rest is not a source. No browser User-Agent, no cookie replay, no headless browser.

## What DEED would have given (from the one hub page read)

The hub "Financial Assistance for Local Governments" links, all under `/deed/government/financial-assistance/`:
Business Development Funding (Minnesota Investment Fund, Greater Minnesota Public Infrastructure Grant Program,
Border-Cities Enterprise Zone, Innovative Business Development Program, Transportation Economic Development
Infrastructure), Community Development Funding (Small Cities Development Program, Special Appropriations Grant, Greater
Minnesota Child Care Facility Grants), Site Cleanup and Redevelopment Funding (Contamination Cleanup and Investigation
Grants, Cleanup Revolving Loan Program, Redevelopment Grant Program, Demolition Loan Program). The Public Facilities
Authority and the Office of Broadband Development have their own sections.

## Sample of the raw data (the one program page that answered, `.../community-funding/small-cities.jsp`)

```
h1  Small Cities Development Program
    Our Small Cities Development Program (SCDP) helps cities, townships, and counties with funding for housing, public
    infrastructure and commercial rehabilitation projects.
    ... Cities with fewer than 50,000 residents, townships and counties with fewer than 200,000 residents are eligible.
    tabs: Eligibility | Apply | Forms | Consolidated Plans | Guides | Webinars | Contacts
```

Server-rendered and clean: had the host let the client through, this would have been an ordinary agency-page connector.

## Implemented

Nothing: no connector, no fixtures, no tests. The saved pages stay in the session's scratch directory, not in the repo.

## Gaps and follow-ups

- Do not re-probe `mn.gov` from the development proxy. Whether the Actions runner meets the same redirect is not known
  (12.8a met Radware on the state's grants page; from which network is in that session's notes, not checked here).
- The way in is permission: ask DEED (or MNIT) to allow the project's User-Agent, as with GOCPP.
- Minnesota agencies on other hosts (MnDOT's State Aid at `dot.state.mn.us`, the Pollution Control Agency at
  `pca.state.mn.us`, DNR at `dnr.state.mn.us`) were not surveyed: not on this session's allowlist. They are the next
  candidates if Minnesota is reopened, each with its own robots check.
