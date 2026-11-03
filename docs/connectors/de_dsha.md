# Delaware State Housing Authority connector (`de_dsha`): source, raw data and field mapping

Milestone 11, Delaware's fourth agency (the municipal five, decision 2026-11-03). Written 2026-11-03 from a read of
Housing Delaware's "Build & Develop" pages, before the parser. CDBG for Kent and Sussex localities, the
Neighborhood Assistance Act, Downtown Development Districts, Home4Good, ESG, HOPWA, the housing development funds:
the one Delaware source that states its rounds with dates.

## Implemented (2026-11-03, same day)

`connectors/de_dsha.py` follows this doc. First live run: 17 records added (14 sections and 3 one-program pages), 0
errors; second run 0 changed. 4 open (Downtown Development Districts and the Strong Neighborhoods fund, rolling to
2027-05-30; ESG, whose dated list says the FY2026 round opened 2026-10-14 and is due 2026-12-01; LIHTC, "Current round
2025–2026"), 4 closed on the page's words (Home4Good, Mixed Income Market Fund, Special Populations, Permanent
Supportive Housing), 9 `unknown`. Two tag a municipality: CDBG ("Local and county governments in Kent and Sussex
Counties are eligible to apply") and ESG ("Units of general local government located in Kent and Sussex Counties").
The Delaware page: **2 open municipal rows** (ESG, due 2026-12-01; DNREC's Asset Management) and 1 between rounds.
Found while writing the parser: "Eligible activities" is not an eligibility heading; a status badge sits inside the
section heading; and dated list lines from past rounds (LIHTC's 2023 deadline) must not override a status card that
says the current round is open, so list lines are read only when a program has no card.

## The source

`https://www.destatehousing.com` ("Housing Delaware", the authority's new name; WordPress; `robots.txt` is
`User-agent: * / Disallow:`). The "Build & Develop" section holds program pages of two shapes, read by hand list:

| Page | Shape | Programs |
|---|---|---|
| `/community-benefit/` | sections | Home4Good, Community Development Block Grants (CDBG), CDBG Recovery Housing Program, Emergency Solutions Grants (ESG), Housing Opportunities for Persons with AIDS (HOPWA), Neighborhood Assistance Act (NAA) |
| `/arpa-programs/` | sections | Catalyst Fund, Mixed Income Market Fund, Accelerator and Preservation Fund, Market Pressure Relief Fund |
| `/supportive-housing/` | sections | Special Populations Housing Fund, HDF Statewide Emergency Shelter, Housing Trust Fund Permanent Supportive Housing, ARP Homelessness Assistance |
| `/ddd-program/` | one program | Downtown Development Districts |
| `/homeownership-production/` | one program | Strong Neighborhoods Housing Fund |
| `/lihtc/` | one program | Low Income Housing Tax Credit |

Six GETs a run. `/local-municipalities/` and `/planning-assistance/` are technical-assistance pilots (zoning reform,
disaster housing), not funding, and are not read.

### A page

```html
<div class="hd-hdr ..."><p class="hd-hdr-eyebrow">Build &amp; Develop</p>
  <h1 class="hd-hdr-title">Downtown Development Districts</h1>
  <p class="hd-hdr-lede">Investors who make Qualified Real Property Investments in a designated Downtown Development District may apply to Housing Delaware for a rebate ...</p>
  <div class="hd-hdr-meta">
    <div><span class="hd-hdr-meta-k">Small Project rebates</span><span class="hd-hdr-meta-v">Rolling from July 15, 2026 through May 30, 2027</span></div>
    <div><span class="hd-hdr-meta-k">Large Project reservations</span><span class="hd-hdr-meta-v">Not currently accepting applications</span></div>
    <div><span class="hd-hdr-meta-k">Who applies</span><span class="hd-hdr-meta-v">Investors in a designated district</span></div></div></div>
...
<h2 id="cdbg" class="wp-block-heading hd-sec-h2 mb-3">Community Development Block Grants (CDBG)</h2>
<p class="wp-block-paragraph">This program, operated in Kent and Sussex Counties only, provides funding ...</p>
<div class="hd-panel hd-panel--tint mb-5"><h3 class="wp-block-heading h6 mb-2">Eligibility &amp; administration</h3>
  <p>Local and county governments in Kent and Sussex Counties are eligible to apply. ...</p>
  <p>Towns, municipalities and local and county governments are eligible to apply, receive funds and administer them locally as grants to homeowners. ...</p></div>
<h3 class="hd-subhead">Current program (FY26)</h3> <ul class="hd-doc-list">...</ul>
```

Every page opens with a header card: the title, a lede, and `hd-hdr-meta` key/value pairs (a status line per
sub-program, `Who applies`, `Questions`). On a sections page each `h2.hd-sec-h2` starts a program; its paragraphs,
`h3` subheads, tinted panels (`Eligibility & administration`, `Important dates`) and lists follow until the next
`h2`. What the pages said on 2026-11-03:

| Program | Status words | Who applies |
|---|---|---|
| Home4Good | header: "2026 round: Applications closed June 25 — awards announced December 2026"; Important dates: "May 12, 2026 — Home4Good 2026 funding round opens.", "June 25, 2026 — Home4Good applications due" | "501(c)(3) nonprofit organizations" |
| CDBG | "Current program (FY26)" | "Local and county governments in Kent and Sussex Counties are eligible to apply"; "Towns, municipalities and local and county governments are eligible to apply" |
| Downtown Development Districts | "Small Project rebates: Rolling from July 15, 2026 through May 30, 2027"; "Large Project reservations: Not currently accepting applications" | "Investors in a designated district" |
| Strong Neighborhoods Housing Fund | "Applications Open July 15, 2026 — rolling through May 30, 2027" | (nonprofit and for-profit developers, in the text) |
| LIHTC | "Current round 2025–2026 — see round documents" | "Nonprofit and for-profit developers" |
| Mixed Income Market Fund | "Round 2 closed Aug 1, 2024" | developers |
| Special Populations Fund & PSH | "Not currently accepting applications" | "Developers and 501(c)(3) nonprofits" |
| ARP Homelessness Assistance | "The 2021 application round is closed and the timing of the next round is not yet known." | |

Contact cards ("Questions about this program?", a phone, "Send an email") and `Questions` meta values name a
department or a person and are never read.

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `de_dsha` |
| source_id | page, section | the page slug for a one-program page (`ddd-program`); `<slug>#<section id>` for a section (`community-benefit#cdbg`) |
| source_url | page, section | the page URL, with `#<section id>` for a section |
| external_number | none | null |
| name | `h1.hd-hdr-title`, or the section `h2` | as written |
| level / jurisdiction | constant | `state` / `DE` |
| administering_agency | constant | `Delaware State Housing Authority` |
| agency_code | constant | `DE-DSHA` |
| funding_type | name, lede | the shared keyword on the name; else `rebate` when the lede says rebate; else null |
| funding_source | text | `pass_through` when the program's text says the money is federal (`federal grant`, `federal funding`, `HUD`, `Federal Home Loan Bank` is not federal money and does not count); else `direct` |
| amount / match | none | null |
| status | the status line | see status rules |
| opens_at / closes_at | the status line | full dates: `from X through Y` and `Open X — rolling through Y` give both; `due X` the close alone |
| closes_at_text | the status line | verbatim: the header meta value for the program (a meta key that begins with the program's name, or the only sub-program line on a one-program page), else the first sentence in the program's text that says closed, open, due, accepting, round or rolling |
| rolling | the status line | `True` when it says rolling |
| summary | first paragraph | the lede for a one-program page; the first paragraph after the `h2` for a section |
| eligibility_text | `Who applies`, the eligibility panel | the `Who applies` meta value, then the paragraphs of a panel or subsection whose heading mentions eligibility, who applies or applicant qualifications, then sentences that say who is eligible to apply, one per line |
| eligibility_structured | header meta | `{"status_lines": {"Small Project rebates": "Rolling from ..."}}` for a one-program page with several sub-program lines |
| applicant_types | eligibility_text | the shared tagger, sentence by sentence |
| categories | none | none (the VA DHCD rule) |
| alns | none | always empty |

### Status rules

| The status line says | Status |
|---|---|
| `closed`, `Not currently accepting` | closed |
| `rolling` or `open` with a closing date on or after today, or a due date on or after today, or `Current round` | open |
| `rolling` or `open` with no date | open |
| anything else | unknown |

A one-program page with two sub-program lines (DDD: rebates rolling, reservations not accepting) takes the first
line that is open; if none is, the first line.

### What happens when a program leaves

`resolve_missing` is `unknown` without a request: a section the page drops is not a closure the agency stated.

## Decisions (defaults; override at review)

1. **A hand list of six pages in two shapes.** The site is small and typed; a new program page is one line.
2. **A section is a program when it has an `h2.hd-sec-h2` with an id and is not "On this page", "Questions" or
   "Archived programs."**
3. **The header meta is the status of record** where its key names the program; the text's own status sentence
   otherwise. The agency maintains the card by hand each round.
4. **`Who applies` is applicant text**, as are the eligibility panels: the agency's words about who may apply.
5. **No category**, as for Virginia DHCD.
6. **Contact cards and `Questions` values are never read.**

## Known gaps

- "Applications closed June 25" carries no year on the card (the Important dates list does); `closes_at` comes from
  the dated list line when it exists.
- The ARPA funds and supportive housing programs are for developers and nonprofits; CDBG, NAA and the Downtown
  Districts (through their designated towns) are the municipal ones.

## Verification

`tests/test_de_dsha.py` against the six saved pages (`scripts/probe_de_dsha.py`); two live runs.
