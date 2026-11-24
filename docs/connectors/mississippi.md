# Mississippi Development Authority: survey (12.9, 2026-11-24)

Mississippi has no public state index of funding programs (`docs/surveys/state_portals.md`). The Mississippi Development
Authority (MDA) is the state's CDBG agency and runs the state's infrastructure grants and loans for towns and counties.
Surveyed read-only with the connectors' User-Agent, 3 s apart, pages saved and read from disk.

| Agency | Host | CMS | robots | Verdict |
|---|---|---|---|---|
| Mississippi Development Authority | `mississippi.org` | WordPress (theme `mda`, Yoast) | `User-agent: * / Disallow:` (nothing disallowed), no `Crawl-delay` | **readable**, built: `ms_mda` |

No other Mississippi host was on this session's allowlist (MDOT, MDEQ, MEMA were not surveyed).

## What MDA gives

"Community Resources > Community Incentives" (`/community-resources/incentives/`) is one page of cards: a program name
(`h3.c-card__title`), one paragraph, and a "Download" link to a one-page PDF. The page prints nine cards; a pager button
loads two more ("Energy Infrastructure Revolving Loan Program", "Mississippi Alternative Fuel School Bus and Municipal Motor
Vehicle Loan Program") by a **POST** to `/wp-admin/admin-ajax.php` (`action=filter_community_incentives&page=2`; the same
address by GET answers page 1 whatever the `page`). There is no page per program. No card dates a round, so every record
is `unknown` ("Status not confirmed").

`/community-resources/community-and-rural-development/` describes the bureau and links the forms library; it holds no
program.

## Scope: one record per card on the page as served, eight of nine

In: the Capital Improvements Revolving Loan Program (CAP), CDBG for Public Facilities Projects, the Small Municipal and
Limited Population Counties Grant Program (SMLPC), the Airport Revitalization, Freight Rail Service and Port Revitalization
revolving loan programs (county and municipal authorities apply), the CDBG Economic Development Program and the Development
Infrastructure Grant Program (DIP).

Out: the **Mississippi Rail Grant Program** ("provides grants to public and private railroads": a railroad applies, not a
town). Its card is a named tail in the split, so its text joins no other record.

Not read: the two cards of pager page 2 (they need a form POST, which the hand-list base does not make: a follow-up, below);
the PDFs behind "Download" (amounts, terms and the application route are there, not on the page); the business incentives
under "Doing Business" (tax incentives, out of scope); MFLEX; the minority and small business loans.

## Field mapping

The agency-page table in `connectors/hand_list.py`, with a reader of this module's own:

- **Text**: `#community-incentives-results`, one label block per card title and one paragraph block per card paragraph.
  Nothing else on the page is read (the intro names the bureau; the forms and the newsletter are chrome).
- **Split**: one page, eight records, through `SPLITS` built from the card titles (`CARDS`). CAP, the first card, keeps the
  page's `source_id` (`community-incentives`); the others are `community-incentives#<sub>`. A card whose title is not in
  `CARDS` (the Rail Grant today, any card MDA adds later) is a tail: no record, and its paragraph joins no other record.
- `name`: the card title as printed.
- `source_url`: the page (there is no address per card).
- `status`: `unknown`; no card states a round.
- `funding_type`: the shared keyword on the name ("Loan", "Grant").
- `funding_source`: the shared rule (CDBG Public Facilities names "the U.S. Department Housing and Urban Development");
  CDBG Economic Development is `pass_through` by `FUNDING_SOURCES` (the same block grant; its card names the "national
  objectives" and no agency). The rest are state programs: `direct`.
- `eligibility_text` and applicants: the shared reader ("... may apply for loans", "is available to provide loans to state,
  county, or municipal port authorities") plus the sentences this module names itself (`OWN_APPLICANT_RE`): "provides
  loans/grants to municipalities and counties", "provides municipalities and counties funding", "can be used by
  municipalities and counties". What the money is for ("to assist with the location, expansion or retention of
  businesses", "to finance ...") is cut before tagging, so a business the project serves is not tagged as an applicant; the
  stored text keeps the whole sentence.
- **Contacts**: the sentence that gives the Financial Resources Division's telephone number is removed from the paragraph
  ("For more information on Airport and Port Revolving Loans, contact ... at ...", "To learn more, contact ...").
- Amounts ("a maximum state grant amount per project of $600,000 ...") are not parsed: the amount parser stays deferred
  (roadmap); the sentences stay in the stored text.

## Sample of the raw data (2026-11-24)

```
h1  Mississippi Community Incentives
h3  Capital Improvements Revolving Loan Program (CAP)
p   CAP provides loans to municipalities and counties to finance public infrastructure improvements in Mississippi. CAP Loan
    funds may be used by local governmental authorities in support of business location and expansion projects and other
    community-based projects.
a   Download -> /wp-content/uploads/capital-improvements-revolving-loan.pdf   (not read)
h3  Community Development Block Grants (CDBG) for Public Facilities Projects
p   Mississippi's CDBG Public Facilities Program provides municipalities and counties funding for public infrastructure
    needs. The program provides for a maximum state grant amount per project of $600,000 for cities and counties with a
    population greater than 3,500 people and $450,000 for cities and counties with a population under 3,500. CDBG requires
    that at least 51% of the persons benefited must be persons of low and moderate income as determined the U.S. Department
    Housing and Urban Development.
h3  Airport Revitalization Revolving Loan Program
p   County and municipal airport authorities authorized to operate in Mississippi may apply for loans for the airport
    authority or on behalf of a new or expanded industry. [For more information ..., contact ... at ...]   (removed)
```

## Implemented (2026-11-24)

`connectors/ms_mda.py`, a reader of its own on `AgencyPageConnector`; `scripts/probe_mississippi.py` saved the fixture
(`tests/fixtures/ms_mda/community-incentives.html`). `tests/test_mississippi.py`: 7 tests. Not run through `cli.py run`
(the connector table in `pipeline/run.py` is added centrally): the module was called directly, as the probe does. The
probe's lines, live, 2026-11-24:

```
== ms_mda
  community-incentives                       unknown    open=None close=None direct       ['municipality', 'county'] |
  community-incentives#cdbg-public-facilities unknown    open=None close=None pass_through ['municipality', 'county'] |
  community-incentives#smlpc                 unknown    open=None close=None direct       ['municipality', 'county'] |
  community-incentives#airport-loan          unknown    open=None close=None direct       ['municipality', 'county'] |
  community-incentives#freight-rail-loan     unknown    open=None close=None direct       ['municipality', 'county'] |
  community-incentives#port-loan             unknown    open=None close=None direct       ['municipality', 'county', 'state'] |
  community-incentives#cdbg-economic-development unknown    open=None close=None pass_through ['municipality', 'county'] |
  community-incentives#dip                   unknown    open=None close=None direct       ['municipality', 'county'] |
```

| Record | Status on 2026-11-24 | Applicants tagged | Type, source |
|---|---|---|---|
| Capital Improvements Revolving Loan Program (CAP) | unknown (no round stated) | municipality, county | loan, direct |
| Community Development Block Grants (CDBG) for Public Facilities Projects | unknown | municipality, county | grant, pass_through (HUD) |
| Small Municipal and Limited Population Counties Grant Program | unknown | municipality, county | grant, direct |
| Airport Revitalization Revolving Loan Program | unknown | municipality, county | loan, direct |
| Freight Rail Service Revolving Loan Program | unknown | municipality, county | loan, direct |
| Port Revitalization Revolving Loan Program | unknown | municipality, county, state | loan, direct |
| Community Development Block Grants (CDBG) Economic Development Program | unknown | municipality, county | grant, pass_through (set by hand) |
| Development Infrastructure Grant Program (DIP) | unknown | municipality, county | grant, direct |

The Mississippi page will show 0 open and 8 under "Status not confirmed".

Requests to `mississippi.org`, survey and probe together: 7 (the home page, two community pages, the theme's pager script,
the pager address once by GET and once by POST to see what page 2 holds, the probe), plus the `robots.txt` read before the
session. No `Crawl-delay`; the module makes one GET a run.

## Gaps and follow-ups

- **Pager page 2** (two loan programs local governments apply for: Energy Infrastructure Revolving Loan Program,
  Mississippi Alternative Fuel School Bus and Municipal Motor Vehicle Loan Program): needs a POST to
  `/wp-admin/admin-ajax.php` with `action=filter_community_incentives&page=2`. `robots.txt` does not disallow it, but the
  hand-list base only GETs. Two ways in: a `fetch` of the module's own that posts the form, or a look at whether the WordPress
  REST API (`/wp-json/`, not probed) lists the cards. Ask Saj before posting a form on every run.
- **Rounds, amounts, terms**: on each card's one-page PDF under `/wp-content/uploads/` and in the forms library
  (`/community-resources/forms-library/`), not on the page. The CDBG application cycle is announced there or by mail; every
  record stays `unknown` until a page dates a round.
- **Site development grants** (the brief's list) are not on the Community Incentives page; "Special Programs"
  (`/community-resources/special-programs/`) and the Office of Energy page were not read.
- **A card not in `CARDS`** makes no record: if MDA renames a card, its record goes missing in the diff rather than turning
  into a wrong one. A missing record is the signal to update `CARDS`.
- Mississippi's other municipal agencies (MDOT's local programs, MDEQ's revolving funds, MEMA's mitigation grants) were not
  surveyed: none of their hosts was on this session's allowlist.
