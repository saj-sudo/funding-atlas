# Navigator UX review, 2026-11-14

A full pass over the live site (https://saj-sudo.github.io/funding-atlas/) before more states: user flow, layout,
visual design and copy, plus research on how comparable tools present funding data. Measured on the live build of
2026-11-14 at 1366px desktop and an iPhone 13 (390 x 664 visible), with counts from the published `atlas.db`.

## Summary

The registry is honest and the page is careful, but **the page hides the thing that makes it worth visiting**: a
state's own programs. Every state page leads with the same 125 federal notices; Maryland's 20 state rows are mixed
into them, Virginia's 16 sit collapsed 13,400px down, and 84 eligible state programs (status not stated) appeared on
no page at all. On a phone, no program was visible before the reader scrolled 1.6 screens.

What changed in this session (milestone 13.1, built and tested): the state page now leads with the state, shows the
84 hidden programs as **Status not confirmed**, puts the first program at the fold on a phone (y=662, was 1066),
gives every card one layout with status and deadline first, makes the default "Likely fit" filter visible and
removable, and opens the detail panel with five plain answers. A mockup with three visual directions is published
for Saj to pick from (13.2): https://claude.ai/artifact/TD8a8dMrft9jA4rRkmHG7e (private until shared).

What is left, in order: 13.2 the visual direction, 13.3 page weight and the phone filter tray, 13.4 a change feed
for humans, 13.5 the index page. Each is one session (roadmap, milestone 13).

## Who the page is for (from SPEC.md)

| Reader | Needs | Reads on |
|---|---|---|
| Town administrator or clerk, no grants staff | what is open, when it closes, am I eligible, where do I apply | a phone, between meetings |
| COG or regional planner | everything member towns could apply for this quarter, by category | desktop, to paste into a newsletter |
| Grant consultant | the change feed, first to a reopened round | feed reader, desktop |

The clerk is the hardest case and the one the page should be designed around; the other two have desktop and the
feed.

## Audit: what the reader met on 2026-11-14

### Flow and structure

1. **The state's own programs were buried.** Maryland: 125 federal and 20 state rows in one deadline sort. Virginia:
   0 state rows in the list ("125 federal and 0 from Virginia agencies"), its 16 closed-recently rows collapsed at the
   bottom. Alaska and Nebraska looked identical to Virginia. The federal list is the same on all 51 pages, so the only
   part of a state page that is about the state was the part a reader was least likely to reach.
2. **84 eligible state programs appeared nowhere.** `v_navigator_program` takes open and forecasted rows;
   `v_navigator_between` takes closed ones and `unknown` ones with a date. A program page that states no status and
   no date fell through both: VA 24, MO 12, DE 10, KY 7, OR 7, VT 6, CT 5, ND 5, MD 4, WV 4. 18 carry the source's
   cycle wording ("the spring of every year, with a second round in the fall"). Some are stale (WV "Spring 2023").
3. **Nothing above the fold on a phone.** The sticky header wrapped to two rows (256 of 664px, 38% of the screen);
   then a three-sentence lede, two coverage pills and three stacked tiles. First card: y=1066.
4. **Pages are heavy and long.** 700KB to 1.16MB of inline JSON per state page; 20,000 to 29,000px tall on a phone,
   because every card renders. Fine on wifi, slow on a county office's LTE.
5. **The default filter was silent.** "Likely" is preselected; the only sign was "Showing 89 of 145".
6. **The index feed is the whole country's log,** housekeeping included ("agency, agency code, source URL" as a
   change) and federal notices no town wants (artist exchanges).

### Cards and detail

7. **Four pills before every name** (tier, status, level, Updated, in caps). The eye parsed a chip row to find the
   title. GOV.UK tested uppercase tags as harder to read.
8. **Contradictory signals.** 4 federal rows read **Forecasted** and **closes tomorrow** at once (Grants.gov's own
   status).
9. **Source noise shown raw.** ALL-CAPS agency names, office codes ("69A345 Office of the Under Secretary for Policy"),
   agency codes on every card, "$0 to $500,000" (a form default), "Funding source: Direct" with no gloss.
10. **The drawer led with a summary paragraph.** The clerk opens it to answer "can we apply, by when, for how much";
    eligibility was below a 300-word summary.

### Copy

11. Jargon without a gloss on the page: Likely / Possible, Between rounds, Forecasted, pass-through, registry,
    connector. The footer explains them; few readers reach a footer.
12. The index stats mix scales in one tile ("3865 state programs read, 161 open, 227 between rounds").
13. Ledes ran 40+ words. Headings were honest and plain, which is worth keeping.

### What already works (keep)

- Shareable links: filters and the open program live in the URL hash. Simpler.Grants.gov's testers asked for exactly
  this.
- Verbatim eligibility and deadline wording, and "blank means the source did not say". This is the product's trust.
- The change feed with permanent ids, and Atom beside every page.
- Accessible bones: skip links, a real dialog with focus return, keyboard tabs, reduced motion, print styles, dark
  mode.

## Research: how others present this, and what the evidence says

Sources were fetched and read unless marked *(search snippet only)*.

**Comparable products**
- **Simpler.Grants.gov** (HHS and Nava; 32 participants, 35 interviews). Results lead with close date, status, title,
  agency, award min and max; filters for "next 7/30/90/120 days"; missing values shown as "--" or "TBD". Testing
  replaced "Posted" with **Open**; whether **"Forecasted"** is understood was *inconclusive*. Novices "have difficulty
  determining their eligibility" and struggle with acronyms. Shareable links were a top request.
  https://simpler.grants.gov/search ·
  https://wiki.simpler.grants.gov/design-and-research/content-guidelines/terminology-usage ·
  https://wiki.simpler.grants.gov/design-and-research/user-research/grants.gov-archetypes ·
  https://www.navapbc.com/case-studies/modernizing-grants.gov-iteratively
- **California Grants Portal** (14 months, 1,000+ grant seekers, 120+ state staff). Each card opens with status and
  deadline ("Active 12/5/26", "Active Ongoing"); an amount with no range reads "Dependent", never blank.
  https://www.grants.ca.gov/a-new-way-to-find-grants/
- **UK Find a grant.** Question-style labels ("Who can apply", "How much you can get"), no status badges. Also the
  failure mode: placeholder closing dates (31 March 2030) "because the tool requires one". Our no-guess rule is on the
  right side of that line. https://www.find-government-grants.service.gov.uk/grants
- **Instrumentl** marks estimated deadlines "Predicted" in a distinct style and lets users filter to confirmed ones.
  https://help.instrumentl.com/en/articles/3730725-what-is-a-predicted-deadline
- **USDR, "No Front Door"** (350+ small communities): towns find funding through newsletters, list-servs and "luck";
  NOFOs are "intimidating and time-consuming to assess"; the question is "is the amount worth the effort to apply?".
  Recommends executive summaries and eligibility checklists.
  https://go.usdigitalresponse.org/hubfs/Grants/U.S.-Digital-Response-No-Front-Door-Federal-Grant-Research.pdf
- **DSIRE** reviews each record at least yearly *(search snippet only)*: a per-record "last checked" date matters.

**Layout and interaction (NN/g)**
- Cards are for browsing mixed content; for scanning similar items, a consistent list with the key fields in a
  predictable place works better. https://www.nngroup.com/articles/cards-component/
- Tables: human-readable first column, columns by importance, show active filters clearly; on mobile a wordy table
  fits about two readable columns. https://www.nngroup.com/articles/data-tables/ ·
  https://www.nngroup.com/articles/mobile-tables/
- Mobile filters: a tray over the results, the word "Filter" not an icon, the result count always visible, batch
  apply with a button. https://www.nngroup.com/articles/mobile-faceted-search/ ·
  https://www.nngroup.com/articles/applying-filters/
- Empty states say what happened and offer the next step.
  https://www.nngroup.com/articles/empty-state-interface-design/
- Older users (65+) completed 55% of tasks against 75% for ages 21 to 55 and were about 43% slower: larger text and
  targets, spacing between links. https://www.nngroup.com/articles/usability-seniors-improvements/

**Design systems**
- USWDS tags: users mistake tags for buttons, so static tags get no hover; don't flag everything.
  https://designsystem.digital.gov/components/tag/
- GOV.UK tags: adjectives, as few statuses as possible, sentence case, never colour alone.
  https://design-system.service.gov.uk/components/tag/ ; grey text for "cannot start yet", red for errors only:
  https://design-system.service.gov.uk/patterns/complete-multiple-tasks/
- USWDS summary box: 3 to 5 key facts at the top of a detail page.
  https://designsystem.digital.gov/components/summary-box/ ; GOV.UK summary list: a missing value points to where to
  find it. https://design-system.service.gov.uk/components/summary-list/
- Type: 16px body or larger, 45 to 90 characters a line (66 ideal), line height 1.5.
  https://designsystem.digital.gov/components/typography/
- Change notes say what changed and skip typo-level edits; a clear "see all updates" link got about 4x the views.
  https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/change-notes/ ·
  https://insidegovuk.blog.gov.uk/2013/08/13/redesigning-change-notes-and-measuring-the-result/

**Plain language**
- Split sentences over 25 words; explain a specialist term the first time.
  https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/clear-language/
- USAGov's benefit finder frames results as things you "may qualify to receive": a hedge about fit, not a ruling.
  https://www.usa.gov/blog/2023/08/new-life-events-and-features-for-usagovs-benefits-locator

Not found anywhere: published research on how to display deadlines specifically, or on "unknown" versus a dash. The
precedents ("TBD", "Dependent", "Active Ongoing", "Predicted") all name the uncertainty in words, which is what 13.1
does.

## What 13.1 changed (built 2026-11-14)

| Finding | Change | Measured after |
|---|---|---|
| 1, 2 | Sections in order: **[State] programs open or announced**, **Status not confirmed** (collapsed), **Closed recently** (collapsed), **Federal notices**. New view `v_navigator_unstated` (migration 0008). Empty state with a next step: "No Virginia programs are open or announced right now. 19 have no status on the agency's page and 7 closed recently: see below." | VA's first state content at y=701 desktop (was 13,407) |
| 3 | One-row header (state picker label hidden on phones), coverage as one line with a disclosure, compact tiles in one row on phones | first card y=662 on iPhone 13 (was 1066); header 53px (was 256) |
| 5 | Active filters shown as removable chips with "Showing 113 of 169 · Filtered to Likely fit × · Show all 169" | |
| 7, 8 | One status tag per card, sentence case, static; status and deadline as the first line, then name, then agency · level · fit, then amount and match in fixed spots. Labels: Open, **Announced** (forecasted), **Status not confirmed** (unknown), Closed | |
| 9 | Display only: capitals agency names title-cased, leading office codes and $0 minimums dropped, agency codes off cards; "Amount not published" instead of a blank | |
| 10 | Drawer opens with five answers (Is it open? When does it close? How much? Who can apply? Where do I apply?), then eligibility as written, then summary, then "More details" | |
| 11 | Inline glosses: "Likely fit" / "May fit: check eligibility", "Where the money comes from: Federal money passed through the state" | |

The data vocabulary does not change (`forecasted`, `unknown`, `v_navigator_between`); only labels do.

## Three visual directions (for 13.2)

The mockup renders the same structure three ways on real Maryland and Virginia data:
https://claude.ai/artifact/TD8a8dMrft9jA4rRkmHG7e

| | A. Civic (recommended) | B. Ledger | C. Agenda |
|---|---|---|---|
| For | the clerk on a phone | COG planners, consultants | "what do I do this week" |
| Look | blue-biased paper, navy ink, Source Serif headings, Public Sans body (the US federal design system's face) | cool grey, IBM Plex with mono numbers, one teal accent | Atkinson Hyperlegible (made for low-vision readers), calendar tiles |
| Signature | a date column: the deadline is the first thing the eye lands on | a 90-day deadline strip and a sortable table | programs under This week / This month / Later / No date |
| Cost | airy, about five programs per desktop screen | tables fail on phones (stacks below 640px); reads like software, not a public service | weak for browsing by topic; most state rows land in "No date" |

**My recommendation:** A as the base, with C's "closes this week" headers inside the state section when the sort is
"closing soonest", and B's table later as an optional desktop "Compare" view for planners. Two web fonts would be
the site's first external request; the alternative is to self-host them in `web/` (same origin), which keeps the "no
external requests" rule. Decide that with the direction.

## The rest of milestone 13 (one session each)

- **13.2 Visual direction.** Apply Saj's pick: type scale, palette tokens, card layout, the date column if A; dark mode
  and print checked; fonts self-hosted or system.
- **13.3 Page weight, paging, phone filters.** First 30 per section with "Show more"; federal rows moved to one shared
  `federal.json` on the same origin (target under 300KB per state page); filters in a slide-in tray with Apply and a
  live count on phones.
- **13.4 A change feed for humans.** Housekeeping-only changes (agency code, URL, summary wording) hidden behind "Show
  minor edits"; the index feed limited to new rows and status flips, with one summary line per state.
- **13.5 The index page.** Map coloured by open state programs, not just "connected"; a start-here picker; stats
  rewritten one sentence each; "Closed recently" and "Status not confirmed" counts per state.

## Open questions for Saj

1. Which direction (A, B, C, or a mix)?
2. Web fonts: self-host in `web/` (keeps the no-external-requests rule) or stay on system fonts?
3. Stale "status not confirmed" rows (WV "Spring 2023", "No further solicitations expected"): list them as the source
   says, or drop rows whose page has not changed in, say, two years? Today they are listed; dropping is a rule on
   `last_changed`, not a guess.
