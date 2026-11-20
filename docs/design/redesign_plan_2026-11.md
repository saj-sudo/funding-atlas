# Navigator redesign plan, second review (2026-11-18)

This follows `docs/design/ux_review_2026-11.md` and milestone 13. It is Funding Atlas's part of a
design pass across Saj's builds: the live site was read on a phone (390 by 844) and a desktop
(1440 by 900) and judged on structure, first screen and identity, not on finish. The "Civic"
direction Saj picked on 2026-11-14 stays. The proposals below push it further; none replace it.
Update the status table at the end of every sitting. Decisions go in the roadmap's decisions log.

## Verdict: rework

The concept and the trust model are the strongest parts, and the program dialog is already at the
level of a public reference: five plain answers (is it open, when does it close, how much, who can
apply, where to apply), then the source's own wording. The limit is structure. The index does not
direct a clerk, the state page puts a pile of controls ahead of the first program, and the pages
are very long. After that, identity: it reads as a clean admin page, not as a reference someone
would recognise.

## What the review saw (live site, 2026-11-18)

- **Index.** Headline, a four-sentence lede and four number cards fill the first phone screen.
  "Pick a state" starts at about 759px, at the fold, and the state grid is below it. The grid is
  the page's best asset (shaded by how much of each state's funding is read, with the count of
  open programs) and it is the one thing a clerk came for.
- **Index length.** 7.1 phone screens. "Latest changes across every source" runs for about 3.8 of
  them before "What this is".
- **State page, phone (Maryland).** Before the first program name: the read-daily line, the
  closing-this-week box, three tabs, search, sort, the star filter, "Filter 1", a "Likely fit"
  chip, "Show all 157", a section heading and "Closes within 7 days · 3". About ten controls and
  labels. The first program title is at about 652px.
- **State page length.** Maryland is 22.9 phone screens, California 26.1.
- **Topic badge.** A single letter in a circle ("E") that needs the legend to decode. The legend
  is a row of its own on desktop.
- **Headings.** Section labels are 12.5px grey capitals, smaller than the 18px card titles they
  sit over.
- **About page.** Chart captions print the database view name (`v_navigator_program`). Two of the
  five charts serve a clerk; three serve a methods reader.
- **Identity.** No share image, a favicon in a blue that is not in the palette, no mark beyond a
  nine-square grid.

Kept as it is, because the first review measured it and was right: the lede hidden on small
phones, the deadline-first card order, the verbatim "as written by the source" blocks, "blank
means the source did not say", the coverage lines that say when a state refuses automated readers,
and links that keep filters in the URL.

## Proposal (what the mockup will show), one feature per session

1. **Brand surface.** Social meta from `SITE_URL`, a committed share image, an icon in the
   palette, `theme-color`, one new test. Link previews are blank today and outreach is running, so
   this goes first. Files: `web/{index,state,about}.html`, `scripts/build_site.py`,
   `tests/test_build_site.py`.
2. **The index leads with the map.** One instruction ("Pick your state. Your state's own programs
   come first.") and the state map inside the first phone screen; the four number cards become one
   sentence each (this is 13.5); the national change log moves behind the Changes link (this is
   13.4's index half). Files: `web/index.html`, `web/app.css`, `web/app.js`.
3. **The state page gets to the first program sooner.** Sort, starred and filter in one row; the
   closing-this-week box as one sentence; "Likely fit" said once. Files: `web/state.html`,
   `web/app.js`, `web/app.css`.
4. **Topics as words.** The word, or a colour plus the word, in place of the letter; the legend
   row goes. Topic colours get their own tokens (they reuse the chart series colours today, so one
   colour means two things). Section headings larger than card titles. Files: `web/app.css`,
   `web/app.js`.
5. **About page for two readers.** Plain captions, view names moved to a "Data and code" note,
   the two clerk charts first and the three methods charts under "For researchers".
   Files: `web/about.html`, `scripts/build_site.py`.
6. **A theme switch.** The `[data-theme]` hook exists and nothing sets it; add the dark block and
   re-render the charts, which read tokens through computed style.

## What would move (each needs Saj's yes on the mockup)

- The four number cards on the index: to one sentence each.
- "Latest changes across every source" on the index: behind a link.
- The single-letter topic badge and its legend row: replaced by the word.
- View names in chart captions: to a footnote.

## Rules this touches

- No external requests from any page; `tests/test_build_site.py` forbids `<script src` (except
  `federal.js`), stylesheet links, `@import`, `url(http` and the substring `cdn`. An absolute
  `og:image` built from `SITE_URL` passes. Icons stay URL-encoded, not base64.
- Python only fills slots in the `web/` templates. No framework, no build step.
- Wording quoted from a source is never changed; only our own labels may change.
- One feature per session; decisions in the roadmap's decisions log; the commit author is Saj's
  GitHub noreply identity.
- Rendering the share image with a headless browser is treated as allowed: the no-headless rule is
  written about reading sources.

## Measures of success

- Index: the state map inside the first screen on a 390 by 844 phone (about 759px down today).
- State page: the first program title above 400px on a phone (652px today).
- A link to any page shows a title, a description and an image when pasted into a chat.
- `uv run ruff check .` and `uv run pytest -q` pass.

## Finish items to fold into those sessions

From the code audit of 2026-11-18: font weights 750 and 800 changed to 700 (only 400 to 700 is
declared, so they clamp); the star and close buttons from 40px to 44px.

## Stages and status

| Stage | State | Link | Date |
|---|---|---|---|
| Second review of the live site | Done | this file | 2026-11-18 |
| Mockup of session 2, the index (one screen, today beside proposed, at Saj's word) | Done: map top on a phone 881px to 312px, page 7.0 to 3.3 phone screens; prototype only, `web/` unchanged | https://claude.ai/artifact/RyZbBVmhoV1ep7QFM8Rg64 | 2026-11-19 |
| Saj picks session 2 | Done: as shown, the change log folded on the index, the desktop side panel | roadmap decisions log | 2026-11-20 |
| Mockup of sessions 3 to 5 (state page, topics, About) | Not started | | |
| Saj slots sessions 3 to 6 against the connector queue | Waiting on the mockup of sessions 3 to 5 | | |
| Session 1, brand surface (needs no mockup) | Not started | | |
| Session 2, the index leads with the map | Done (13.19): map top on a phone 881px to 312px, desktop 706px to 253px, index 7.0 to 3.3 phone screens | roadmap Done, 13.19 | 2026-11-20 |
| Sessions 3 to 6 | Not started | | |

## Starting a session on this work

Paste this into a fresh session that has this repository attached:

> Read `docs/design/redesign_plan_2026-11.md`, `CLAUDE.md` and the roadmap's "Start here" block.
> We are doing the next open stage in the plan's status table, and only that stage, as one
> feature for this session. Restore `atlas.db` from `gh-pages` and run `cli.py export` to see the
> pages. For the mockup stage: capture today's index and Maryland pages at 390 by 844 and 1440 by
> 900 and publish a mockup page that shows them beside the proposed ones, with the "what would
> move" list, then stop for my pick. For a build stage: write the roadmap entry and the
> decisions-log line, build it, check the measures of success, and commit as Saj's noreply
> identity.
