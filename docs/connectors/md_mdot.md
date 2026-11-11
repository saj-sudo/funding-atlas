# Maryland Department of Transportation connector (md_mdot): source, raw data and field mapping

Milestone 7, item 4 (the roadmap's 2026-11-03 order: MDEM, MDOT, MDE). Live survey 2026-11-03. Three hand-listed
pages of The Secretary's Office, the DCR/DelDOT pattern, **not** the SharePoint base: MDOT's pages are the mdgov
theme's newer Bootstrap layout (`main.mdgov-main`, `div.card` accordions, a `nav.mdgov-sectionNav` in the other
column) with no rich-text body control, so none of the base's selectors match.

## Implemented (2026-11-03, same day)

`connectors/md_mdot.py` follows this doc. Live run on a copy of the published database: 3 records (2 open, 1 closed)
in three requests, as expected below; the second run reports no changes. Two reach the Maryland page as likely municipal
rows, the TOD Capital Grant (closes 2026-11-20) and the Urban Tree Program (year-round); Bikeways (closed, "FY 2027
awards have now been announced") joins the between-rounds group. Maryland's open municipal count went from 13 to 15,
between rounds from 18 to 19.

Found on the way: SharePoint nests `<p>` inside `<p>` and a `<div class="row">` inside a `<p>`, so an element's full
text repeated every child and fused the banner with the paragraphs after it; each block contributes its own text only
(the base class's `_own_text` rule, written again here because this connector is not on the base). And the shared
tagger read "homeowner associations" as a household: guarded in `connectors/text.py`, measured on all 6,834 stored
records (0 move).

## Source

`https://www.mdot.maryland.gov`, SharePoint, pages at `/tso/pages/Index.aspx?PageId=<n>`. `robots.txt` is a 404
(SharePoint's error page), so nothing is disallowed. Behind Cloudflare (e-mails obfuscated). No central grants listing
(survey in `md_dhcd.md`): the "Federal Grants" section is a resource list about USDOT programs, and the grant programs
MDOT itself runs sit under "Active Transportation" and "Transit Oriented Development" in the section menu.

| Slug | PageId | Page | Section menu label | What it says today |
|---|---|---|---|---|
| `bikeways` | 28 | Kim Lamphier Bikeways Network Program | Active Transportation | "FY 2027 awards have now been announced!"; a "Who Can Apply" card (Maryland local governments, state agencies, MPOs, transit entities, non-profits, federal public lands agencies); "Matching Fund Requirements" and "Letter of Intent" cards; award lists back to FY12 |
| `urban-tree` | 165 | Urban Tree Program | Active Transportation | "Applications are accepted year-round, with funding determinations made twice a year. Applications received by January 15, will be evaluated for spring planting season and applications received by July 15 will be evaluated for the fall planting season."; applied for on DNR's Community Forestry Catalyst Fund; an awardee table |
| `tod` | 217 | Transit-Oriented Development (TOD) Capital Grant and Revolving Loan Fund | Transit Oriented Development | "provides financial assistance to local jurisdictions and development partners"; "MDOT's TOD Capital Grant Fund is now accepting applications for funding through November 20, 2026."; "Starting in FY27, applications for loans and capital grants will be offered separately. MDOT is currently accepting grant applications." |

### The comment trap

Every one of these pages keeps its old banners inside HTML comments. On the Bikeways page, "Applications are OPEN for
Bikeways FY27 funding! Submit your application on Maryland OneStop before May 31" and "MDOT is currently accepting
letters of intent for the FY27 Bikeways funding cycle" are commented out; on the TOD page, "MDOT's TOD Fund is
currently closed for applications", the FY25 "funding cycle is now open" banner, the "Eligibility Criteria" card and
the "Matching Fund Requirements: Local jurisdictions applying for a grant must commit a 10% match" card are all
comments. A reader sees none of it. The parser removes every comment node before reading anything, so the record is
what the page shows, and what the agency hid is never a fact.

### The Urban Tree eligibility quote

The Urban Tree page names no eligible applicant (the awardee table lists towns, a county planning department, schools
and churches, but awards are not eligibility). Its "UTP How to Apply FY27" PDF (`/OPCP/UTP_HowtoApply_FY27.pdf`, "Last
Update 4.15.2026") does: "Eligible Applicants: Non-profit organizations; schools; community/neighborhood associations;
places of worship; businesses; community business associations; homeowner associations, business service, youth and
civic groups; institutions of higher education; counties; municipalities; and forest conservancy district boards."
That sentence is quoted by hand in `HAND_QUOTES`, dated, and read through the shared tagger, the way Illinois's NOFO
quotes are (milestone 9.4.1). It is not fetched.

### Page skeleton

`main.mdgov-main` holds the content: an `<h1>`, paragraphs, a Bootstrap accordion of `div.card` (a `.card-header`
with the label, a `.card-body` with paragraphs and lists), tables of awards, and a contact line naming a person with
a Cloudflare-obfuscated e-mail. Comments as above.

## Enumeration and change detection

Hand list, three GETs a run, `DELAY_S` apart. A page that fails to load keeps its stored payload (`prior`), as DelDOT.
`resolve_missing` answers `unknown` without a request (a hand-listed page is only "missing" when the list changes). The
payload is `{page_id, section, page: {title, blocks}}`; the record hash moves when the visible text moves.

## Field mapping

| Program field | Source | Rule |
|---|---|---|
| source_connector / source_id | constant / slug | `md_mdot` / `bikeways`, `urban-tree`, `tod` |
| source_url | the PageId | `https://www.mdot.maryland.gov/tso/pages/Index.aspx?PageId=<n>` |
| name | `<h1>` | trailing non-breaking spaces dropped |
| level / jurisdiction | constant | `state` / `MD` |
| administering_agency / agency_code | constant | `Maryland Department of Transportation` / `MD-MDOT` |
| funding_type | name keywords, one override | `tod` → `grant` (the name says "Grant and Revolving Loan Fund" and the keyword table answers `loan` first, but the open call is for capital grants and the loan side is "later this year"); Bikeways and Urban Tree → `grant` (both pages call themselves grant programs) |
| funding_source / alns | constant | `direct`, none: state money (the Transportation Trust Fund), no federal sentence on any of the three |
| amount_min / amount_max | none | null (the Urban Tree PDF's "up to $5,000" is not on the page) |
| match_required | a card labelled "Matching Fund Requirements" or a match sentence in visible text | Bikeways `True`; TOD null (its match card is a comment) |
| status | the round sentence, in order | see status rules |
| opens_at | none | null |
| closes_at | the round sentence | the last full date in it (TOD: 2026-11-20) |
| closes_at_text | the round sentence | verbatim |
| rolling | the round sentence | "year-round" → True (Urban Tree) |
| summary | the first paragraph after the H1 | the program's own one-paragraph description |
| eligibility_text | the "Who Can Apply" / eligibility card items, applicant sentences, the dated quote | what the tagger read, each quote line prefixed with its source and date |
| applicant_types | shared tagger over the same lines | Bikeways: municipality, county, state, nonprofit; TOD: municipality, county ("local jurisdictions"); Urban Tree (from the quote): nonprofit, school, business, higher_ed, county, municipality |
| categories | constant per page | `transportation`, `source_code` = the section menu label |

### Status rules

In order, over the page's sentences with comments removed:

1. "accepting ... applications ... through/until/by <date>" → `open`, `closes_at` = the date; a past date → `unknown`
   with the date kept (DelDOT's stale call-out rule).
2. "accepted year-round" / "rolling basis" in an accepting sentence → `open`, `rolling`.
3. "awards have (now) been announced" → **`closed`**: the agency says the cycle is decided (Saj's call,
   2026-11-03; the stricter reading, `unknown`, would drop Bikeways from every list until spring).
4. "closed for applications" / "is now closed" → `closed`.
5. Otherwise `unknown`.

Expected on 2026-11-03: Bikeways `closed` (between rounds on the Maryland page), Urban Tree `open` rolling, TOD `open`
closing 2026-11-20.

## Decisions

1. **Not on the SharePoint base.** The roadmap assumed it; the pages have none of the base's markup. A hand list of
   three pages does not earn a second base either.
2. **Comments are not read.** The agency's hidden banners say the opposite of the visible page.
3. **"Awards announced" is closed** (above).
4. **The Urban Tree eligibility sentence is quoted from the PDF**, dated, not fetched (the Illinois precedent). The
   page's own text would leave a municipal program untagged. The quote's "homeowner associations" exposed a shared
   tagger gap: `homeowners?` tagged an association as a household; guarded in `connectors/text.py` and measured on
   every stored record (see the roadmap decision).
5. **TOD is a grant today.** Override, not the name keyword; revisit when the loan round opens (then two records, or a
   second funding type, is the question).
6. **Section labels are hand-listed**, not read from the menu: one selector fewer on a hand list.
7. **The contact line is dropped** (the WebGrants rule): each page names its program manager.

## Known gaps

- "Transit entities" tags `special_district` since 2026-11-11 (roadmap 10.6). MPOs stay untagged on purpose (Saj's
  call: a regional planning body has no applicant type), as do "Federal public lands agencies".
- The Bikeways cycle wording (letters of intent in winter, applications April to May 31) is only in comments, so the
  record carries no cycle text until MDOT un-hides a banner.
- The TOD match (10%) is in a comment; `match_required` is null although the NOFO requires it.

## Out of scope

Safe Routes to School (SHA's TAP money, administered on roads.maryland.gov, plus an MVA Highway Safety Office grant),
the "Federal Grants" pages (USDOT programs, a resource list), Complete Streets, Transportation Trails, Commuter
Choice, MTA's and SHA's own programs on other hosts. A `roads.maryland.gov` TAP connector when a town asks for it.

## Fixtures

`tests/fixtures/md_mdot/{bikeways,urban-tree,tod}.html`, written by `uv run python scripts/probe_md_mdot.py` with
scripts, comments, e-mail links, phone numbers and the named contacts removed. One inline test fixture keeps a comment
to prove the comment rule.
