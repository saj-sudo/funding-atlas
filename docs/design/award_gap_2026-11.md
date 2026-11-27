# What it would take to win design awards: third review (2026-11-26)

This follows `docs/design/redesign_plan_2026-11.md`. Saj asked for a ground-up breakdown of the gap between the
site as it stands and award-level design. It rests on three read-only audits: every file in `web/`, the design docs
and decisions log, and the published `gh-pages` build of 2026-11-25, rendered at 1440 and 390 wide, light and dark.
Update the status table at the end of every sitting. Decisions go in the roadmap's decisions log.

## The honest verdict

The site is well made and it will not win anything as it is. It reads as a careful government design-system page (your own second review said "a clean admin page, not a reference someone would recognise", `docs/design/redesign_plan_2026-11.md:15`). More polish on the current direction gets you a nicer admin page.

Awards go to work that has three things, and Funding Atlas has half of one:

1. **One idea a juror can repeat in a sentence, visible in the first five seconds.** You have the idea (a registry that shows what the source said, what it did not say, and what changed) but it lives in footnotes and disclaimers, not in the look.
2. **Craft with no weak corners.** Solid base, about a dozen specific failures listed below.
3. **A story with evidence.** Nothing yet. The outreach log is empty (`docs/outreach.md:78`), there is no usability testing, no analytics, no named user. Civic and social-impact juries score impact; no CSS substitutes for a clerk who found a grant.

Pushback on the framing: "design award" is the wrong target if it means Awwwards. That lane rewards motion-heavy agency sites and would pull you away from the clerk on a phone. The lanes this can credibly compete in are data and civic ones: Information is Beautiful Awards, the Sigma Awards (open data), Webby (Government and Civil Innovation), Fast Company Innovation by Design (social good), Anthem Awards. Dates, fees and eligibility for each need checking before committing; I have not verified them.

## Layer by layer

### 0. Strategy and proof (the biggest gap, and not a design task)
- Pick one lane. Recommendation: data and civic lanes, with Information is Beautiful as the craft bar and a civic category as the impact bar.
- Send the outreach note. Five clerks' reactions are worth more than any session below, and they supply the case study juries ask for.
- Five moderated phone tests with real clerks (task: "find something your town can apply for this month"). Labels like "Status not confirmed" and "May fit" have never met a reader (`ux_review_2026-11.md:143`).
- Decide whether privacy-respecting counts (server logs do not exist on Pages) matter; if yes, that touches the "no external requests" rule and is your call.

### 1. Concept and identity
- **Signature idea: absence has a look.** The hatched "blocked" tiles and dashed "directory only" tiles on the map are the most distinctive thing on the site. Make that one visual grammar everywhere: solid means the source stated it, hatched means the source did not say, dashed means we cannot read it. Apply it to the card's amount and deadline slots (today: grey "Amount not published" on 68% of state cards), the date column when there is no date, the charts, the share image. That turns the honesty rule in `CLAUDE.md` into the brand.
- **The name is unpaid.** Nothing about the site is an atlas. Either earn it (plates, a gazetteer-style index, map-first state pages) or stop leaning on it.
- **Mark and wordmark.** The nine-square grid is a placeholder and the wordmark is set in the body sans while every heading is serif (`web/app.css:142`). A real mark should come from the tile map and the solid/hatched/dashed grammar. This is the one place a professional identity designer would outperform us; budget for it or accept a competent in-house version.
- **Voice.** The tone is a strength (plain, hedged, provenance-first). It is also repetitive: the same disclaimers on every page. Write a one-page voice guide, state each caveat once where it matters.

### 2. Information architecture
- **Programs have no page.** A program is a `#p=slug` dialog (`web/app.js:1018`). No shareable URL with its own preview, nothing for search engines, nothing a juror can be linked to. A real page per listed program (about 770 today) is the largest structural change and the one most reviewers would notice.
- **Page length.** California is 26 phone screens, Maryland 23 (`redesign_plan_2026-11.md:30`), and no session ever set a target.
- **The index stops after the map.** Below it: a bulleted list and grey prose. An award-level front page tells the national story: what closes this week, what changed, what no index covers (the pass-through gap from `docs/SPEC.md:13`).
- **The map shows how a state is read, not what is there.** Eleven connected states display "0", including Virginia with 25 unconfirmed programs. First-time readers see a broken product.
- The planner's desktop "Compare" table (deferred, `docs/ROADMAP.md:561`) is still the right second view.

### 3. Data quality as seen (jurors click things)
- Default "Likely fit" on Delaware includes "NEA Jazz Masters Tribute Concert" and "US-Greece & US-UK Artist Exchange". One of those on screen ends a jury's trust. This is `connectors/text.py` and the tier views, measured with `scripts/measure_tagger.py`.
- Grant numbers glued to titles ("F26AS00083..."), 33 titles over 100 characters, a 2022 NOFA listed as open in California, stale "Spring 2023" rows (your open question at `ROADMAP.md:156`).
- Display-only cleanups are already an accepted category (`ROADMAP.md:560`); source wording stays untouched.

### 4. Visual system
- **Tokens stop at colour.** 22 font sizes, four weights including 650, nine radii, 23 gap values, all typed by hand in `web/app.css`. Award-level craft means a type scale of about eight steps, a spacing scale, three radii, and nothing outside them.
- **Borders fail contrast.** `--line` is 1.3:1 against the surface and is the only edge on every input, select, button and chip. `--s3` on white is 2.8:1.
- **Default controls.** System selects, default checkboxes, a bare textarea for the digest, dark-box tooltips.
- **Cards are generic** apart from the date column and the yellow caution pill. Those two are the keepers; rebuild the card around them and the absence grammar.
- **Typography.** Source Serif 4 and Public Sans are good and are also the USWDS look. Keep them, and get distinction from scale contrast, old-style and tabular figures used on purpose, optical sizing, and a real display size on the index.
- Cleanup with it: duplicated dark-token block, two conflicting 899px media blocks, unused classes, mismatched backdrops (`app.css:371` against `:441`).

### 5. Data visualisation (where the trophies are)
- **Charts shrink on phones.** Fixed 900-unit SVGs scale to roughly 4px labels at 360 wide (`app.css:310`). Each chart needs a phone layout, not a smaller picture.
- **Tooltips are mouse-only** (`app.js:248`); only one chart has a table.
- **One colour means three things.** Federal blue is "federal", "states a status" and "the source changed" in different charts.
- **"What sources state"** is tall, sparse and stacks dots at 0% and 100%. It is also your thesis chart: structured portals state the basics, agency pages do not. It deserves a redesign and an annotated headline.
- **No narrative.** Five figure cards, left-aligned, no annotation, no headline number. The About page should read as an essay with the charts as evidence.
- A piece built for this lane: one annotated visual essay on what American states do and do not publish about their own funding, drawn entirely from the registry. That is the Information is Beautiful entry, and the site becomes its supporting tool.

### 6. Interaction and motion
- Today: three sub-200ms transitions, no entry animation on the drawer. Fine for the clerk, flat for a jury.
- Add restraint, not spectacle: cross-page view transitions from a map tile into its state page, a drawer entry, filter results that settle rather than snap, all off under reduced motion. No scroll effects.
- Fix: no focus trap or `inert` behind the phone tray, tabs lack Home/End, the timeline is `role=img` with buttons inside it, and it is hidden on phones while its URL still opens it.

### 7. Accessibility
- Lighthouse 100 is not a claim a jury or a state CIO accepts. Publish a WCAG 2.2 AA statement and meet it: the contrast failures above, touch targets (filter chips about 26px, map tiles about 22px at 320 wide), table captions and scopes, figure captions, a `nav` landmark in the top bar.
- Your own review found readers over 65 are 43% slower and asked for larger text and spacing (`ux_review_2026-11.md:119`); only part was done.

### 8. Performance
- 137KB of CSS and JS is inlined into all 53 pages and never cached; `federal.js` (574KB raw) loads synchronously; California is 452KB against your 300KB target (`ROADMAP.md:336`).
- **Conflict to settle:** external cached `app.css` and `app.js` fix this and break "one self-contained file that works as an email attachment" (`README.md:76`), which `tests/test_build_site.py:366` enforces. My recommendation is to drop the attachment property, since a live link is the outreach route now. Your call.
- Minify at build, preload the two fonts, defer `federal.js`.

### 9. Brand surface
- A domain. An award entry on `saj-sudo.github.io/funding-atlas` reads as a side project.
- Per-state and per-program share images, a web manifest, touch icons, JSON-LD `Dataset` markup, a sitemap, a privacy note. None exist.

### 10. Submission kit
- Case study page (problem, the no-index gap, method, what the registry found, who used it), a 60 to 90 second screen film, high-resolution stills, a short method note. Playwright screenshots added to the repo as visual regression checks, so craft does not rot as connectors change.

## Sequence and size

Each line is one session unless noted, in the repo's one-feature-per-session rhythm, mockup first where the change is bigger than polish (`ROADMAP.md:584`).

| Phase | Sessions | What |
|---|---|---|
| A. Proof | calendar time, not sessions | Send outreach; five phone tests; pick the lane and check its dates |
| B. Trust | Done 2026-11-26 except two items left by decision. Built: migration 0011 (unrestricted notices not 'likely' by category alone); titles without their own number; the map's bare zeros (see C). Measured and left: old-year open rounds are what the source states; stale unconfirmed rows stay listed (Saj). Left open: the NEA rows (Saj: leave for now; requiring a municipal topic was measured and would move 183 listed rows). Long titles move to the card rebuild in D |
| C. Concept | Mockup picked 2026-11-26. The index map is built in the grammar (hatched: listed, no status; dashed: cannot be read). The mockup showed Virginia as 20; the built map counts 25 from `v_navigator_unstated`. Cards, charts and mark C not built yet |
| D. System | 3 | Scales and tokens; controls and borders; card rebuild |
| E. Structure | Done 2026-11-26: cached `app.css` and `app.js`; a page per listed program (772); phone paging with federal notices folded (California 26 to 7.3 phone screens); the index's three daily blocks; the change log on demand (California 350KB to 209KB, every state page under 300KB). Not done, by choice: closed-recently rows stay in the page. Small leftovers: a per-program link preview image, a tombstone for programs that leave the lists |
| F. Charts | 4 | Phone layouts and keyboard access; thesis chart; About as essay; the entry piece |
| G. Finish | 3 | Motion; accessibility statement and fixes; brand surface and domain |
| H. Entry | 2 | Case study, film, stills, visual tests |

About 20 to 23 sessions plus the calendar time in A. B and C are worth doing even if you never enter anything. If the answer to A is "nobody replied", stop before E and rethink, because the impact half of the scorecard stays empty.

## What I would not do
- Chase Awwwards-style motion, 3D or a geographic map. All three work against the phone reader and the no-asset rule.
- Add AI matching, accounts or anything in the spec's non-goals (`SPEC.md:64`).
- Infer dates or statuses to make cards look fuller. The gaps are the story; design them, do not fill them.

## Decisions (Saj, 2026-11-26)

From the concept mockup (https://claude.ai/artifact/S28KDf5ijasvzUFcfqEys3, private):

| Question | Pick |
|---|---|
| The solid, hatched, dashed rule across the site | Yes |
| The map legend swap: hatched moves from "blocked" to "listed, no status"; blocked becomes dashed | Yes |
| Fixed Amount and Match slots on every card, hatched when empty, replacing the grey line | Yes |
| The mark | C, one tile, part solid and part hatched; the nine-square grid is retired |

From the plan:

| Question | Pick |
|---|---|
| Award lane | Data plus civic |
| Page assets | Cached `app.css` and `app.js`; the self-contained page (and its test) goes |
| Program pages | Yes, for listed programs only |
| Identity | In-house, from mark C |
| Domain | Yes, before outreach; Saj chooses and buys the name |

## Status

| Phase | State |
|---|---|
| A. Proof | Not started. Outreach waits on the domain |
| B. Trust | Begun 2026-11-26: migration 0011, unrestricted notices no longer 'likely' by category alone (7 listed federal rows move to "May fit"). Open: the NEA rows (eligible by the source's own words, a relevance call for Saj), grant numbers glued to titles, stale rows, map zeros |
| C. Concept | Mockup picked 2026-11-26; nothing built in `web/` yet |
| D. System | Built 2026-11-26: type, weight and corner scales; control borders at 3:1; the card with Amount and Match slots and a hatched no-date column. Left: a spacing scale, styled selects and checkboxes, long titles (33 over 100 characters), the duplicated dark token block |
| E. Structure | Begun 2026-11-26: cached `app.css` and `app.js` (index 173KB to 32KB, California 491KB to 349KB). Next: a page per listed program, with a shared head partial; then the index as a front page and state page length. California's own rows still put it over 300KB |
| F. Charts | Begun 2026-11-26: charts drawn at shown width with narrow layouts (labels 12px on a phone, were about 4px), tap notes, a table for every chart; 2026-11-27 the history strip on program pages at real size (11px labels, were 7.6px on a phone). Picked 2026-11-27 from https://claude.ai/artifact/YbPatmH6BUDU6dZAwBPvfy (private): the sources chart as a hundred squares per kind of source; hue says who, fill says stated or not, ink for the rest; About as an essay, argument first; headline "97 of every 100 ... 36". Built 2026-11-27: the sources chart as squares (figure 1,865 to 1,360px on a phone); one colour rule across the charts (heat map orange, status changes ink; every ramp step's number at 4.5:1 or better); About as an essay, argument first, every sentence from the counts. Entry piece picked 2026-11-27 (https://claude.ai/artifact/RMgaokSreomFyr5KxQnqpy, private): About becomes the piece with the atlas hero, the coverage map and three real records; About stays live and dated editions are frozen beside it. Built 2026-11-27: the atlas; how each state is read; one federal program in three states; dated editions (`cli.py edition`, or the site workflow run by hand with `make_edition`). Phase F done; the entry edition's date is Saj's |
| G to H | Not started |

## Verification
- Trust: `scripts/measure_tagger.py` and `scripts/measure_fixtures.py` before and after; zero arts or exchange notices under default "Likely fit" on five sampled states.
- System: a test counting distinct font sizes, radii and gaps in `web/app.css` against the scales; computed contrast of every token pair at or above 3:1 for controls and 4.5:1 for text.
- Structure: phone screens per state page, bytes per page against 300KB, first program card inside the first 390 by 844 screen (existing measure).
- Charts: label height at 360 wide at or above 11px; every chart reachable by keyboard with a table version.
- Whole site: `ruff check .`, `pytest -q`, and Playwright screenshots of index, a large and a small state, a program page and About, both themes, compared across builds.
- The real test: a clerk completes the phone task unaided, and says so in a sentence you can quote.
