# The hand-list base (`connectors/hand_list.py`): what it holds, how an agency goes on it

Milestone 12.1, 2026-11-04. Seven connectors had grown one shape by hand, an agency at a time, between 2026-11-03's
Virginia and Delaware sessions and Maryland's MDOT: `va_dcr`, `va_vdot`, `de_dnrec`, `de_dema`, `de_deldot`,
`de_dsha`, `md_mdot`. The third-case rule that produced `maryland_drupal.py` and `maryland_sharepoint.py` was long
past, so the shared parts moved into one module, with the same gate as those two: every fixture of every one of the
seven produces the same `record_hash` before and after.

## Gate result (2026-11-04)

56 fixture records (va_dcr 6, va_vdot 6, de_dnrec 12, de_dema 10, de_deldot 2, de_dsha 17, md_mdot 3), each run
through the stubbed `fetch()` and `normalize(r, date(2026, 11, 3))` against the merged `main` (ddf6801) and against
this change: identical hash, identical canonical record, identical payload keys, identical `fetch(limit=3)` order.
`ruff check .` clean, 912 tests pass. The seven tests changed two lines each where the module moved onto the class
(the network stub now patches `hand_list.get` and `hand_list.time.sleep`); `va_vdot` and `de_dema` tests are untouched.

## What the module holds

Only what was byte-identical across the modules that call it. Anything that differed from one agency to the next
(the regexes, the status table, the field mapping) stayed in the agency's module, because that is where the next
difference will appear too.

| Name | What | Who used it before |
|---|---|---|
| `DELAY_S`, `TIMEOUT_S`, `USER_AGENT` | 0.3 s between GETs, 30 s timeout, the project User-Agent | all seven |
| `DATE_RE`, `DATE_ORDINAL_RE` | "March 1, 2027"; the second also "March 1st, 2027" | dcr, dnrec, vdot; deldot, mdot. DSHA keeps its own (abbreviated months) |
| `client()`, `get(client, url)` | the HTTP client and one GET; tests patch `get` | all seven |
| `soup(html)` | BeautifulSoup with HTML comments removed (stale banners live there) | all seven |
| `li_text(el)` | a list item's own text, the whole item when it has none | dcr, dnrec, deldot (mdot and dsha read items their own way and do not call it) |
| `blocks_from(content, tags, stop_re, drop_re, bold_max)` | `(kind, text)` in order: `label` for a heading or a short all-bold block, else the tag; drop contact lines; stop at a "Questions?" heading | dcr, dnrec, deldot |
| `label_lines(blocks, label_re, applicant_re, keep_kinds, keep_label)` | the lines under a matching label (every kind or `keep_kinds`, the label too when `keep_label`) plus the applicant sentences elsewhere | dcr (`li`,`p`), dnrec (all), deldot and mdot (`li`, label kept) |
| `first_sentence(blocks, re)`, `first_p(blocks)`, `last_date(text, re)` | the cycle sentence, the summary, the deadline | all but dsha for the first; dnrec, deldot, dsha for the second; all but dsha for the third |
| `quote_lines(hand_quotes, slug)` | hand-quoted eligibility lines, dated and attributed | mdot (Illinois has the same idea in `NOFO_QUOTES`) |
| `applicant_tags(lines)` | the shared tagger over every sentence, negated sentences dropped | all seven |
| `resolve_missing(source_id)` | a hand-listed page that could not be read is `unknown`, no request | all seven |

One unification that is not byte-identical in code (it is on the fixtures): the bold-label check in `blocks_from`
compares the bold run with the block's text as read (a list item's own text), where `va_dcr` compared it with the
item's full text. The two differ only for a list item that is bold and has a nested list; none of the pages has one.

## The class

```python
class HandListConnector:
    CONNECTOR, BASE, AGENCY, AGENCY_CODE, JURISDICTION, PAGES   # constants; PAGES is slug -> whatever the agency needs
    def urls_for(self, slug, spec) -> list[str]                # default: [BASE + spec]
    def parse_page(self, html) -> dict                         # the agency's page reader
    def records_for(self, slug, spec, pages, count) -> list[(source_id, payload)]   # default: one record, {"page": pages[0]}
    def fields(self, raw, today) -> dict                       # every Program field the agency decides
    def fetch(self, limit, prior) / normalize(raw, today) / resolve_missing(source_id)
    def round_sentence(self, blocks) / closes_at_for(sentence) / status_for(sentence, closes_at, today)   # the default table
```

`fetch` walks `PAGES` in order, pauses before every GET but the first, and when a slug's page cannot be read appends
every stored record of that slug (`slug` or `slug#...`) from `prior`, or skips it; it stops once `limit` records
exist. `normalize` fills the fields that are the same for every hand-listed agency (`level="state"`, the agency
constants, no external number, no amounts, no ALNs) and takes the rest from `fields`. Modules keep their public
names as aliases (`fetch = SITE.fetch`, ...) because the pipeline and the tests read module attributes.

**The default status table** is MDOT's, for an agency that has not shown a reason to differ: the round sentence is
the first that says accepting with a date, then accepting at all, then awards announced, then closed; accepting with a
date is `open` while the date is ahead (else `unknown`), year-round or rolling is `open` and `rolling`, awards announced
or closed wording is `closed`, nothing is `unknown`. The four earlier agencies keep their own tables, which differ in
regexes and in check order (DCR: closed first and open needs both wording and a future date; DNREC: wording or a
future date; DelDOT: a future date alone; DSHA: four arguments and `forecasted`); unifying them would have moved
records, and the roadmap's rule is one measured change at a time.

## The agency-page table's hooks (12.6d)

`AgencyPageConnector` (Vermont, Connecticut, North Dakota, Kentucky) takes three optional per-record maps beside its
constants, all keyed the same way:

- `SPLITS[slug] = [(sub_slug, name, heading_re), ...]` for a page that holds several programs (Saj's rule, 2026-11-11:
  one record per program). `split_sections` cuts the page's blocks at the `label` blocks that match; a split whose name is
  `None` is a tail (a funding note, a link list) that belongs to no record; the text above the first heading follows every
  section. A first split with no pattern is the page's **head** (its blocks up to the first match are that program, nothing
  is shared: Vermont's HMGP), and `SPLIT_KINDS[slug] = ("label", "p")` lets a paragraph be a heading (a page that names its
  programs only in paragraphs). The first declared program keeps the page's own `source_id`; the others are `slug#sub_slug`. A page whose
  headings changed falls back to one record under the page's id.
- `FUNDING_TYPES[source_id]` for names with no funding-type keyword (KIA's "Fund A - Wastewater" is a loan);
  `FUNDING_SOURCES[source_id]` where a page names a federal agency without being federally funded (Vermont's FRCF).
- `CATEGORY_LABELS[source_id]` for an agency that covers several topics (the portal-table label a record would carry).

The table also reads an application window ("Applications Accepted: April 1, 2026 - September 1, 2026") as opening and
closing dates when the sentence is about applications and no deadline word exists on the page; it skips the labelled
metadata lines some pages print under a heading when picking a summary; and it drops a "may partner with" sentence before
tagging. See `docs/connectors/kentucky.md` for the measurement.

## How a new agency goes on it

A module of about forty lines plus its regexes, in this order: the constants and `PAGES`; the two regexes (the label
that heads the applicant list, the sentence that names an applicant) and any the page needs for federal wording or a
match; `parse_page` (which selector holds the body, which lines are contacts, `blocks_from(...)`); a class with
`parse_page`, `fields` (name from the title, `round_sentence`/`closes_at_for`/`status_for` from the class, applicant
lines from `label_lines`, summary from `first_p`), and `urls_for`/`records_for` only when a slug is several pages or a
page is several programs; the aliases. Then `tests/fixtures/<id>/` with the pages scrubbed of scripts and contacts,
a test that patches `hand_list.get`, the connector doc, two live runs, one commit. `va_vdot` (an index crawl) and
`de_dema` (two fixed pages, no blocks) are the shape this class does not cover; they import the helpers only.

## Decisions

1. Five modules on the class, two on the helpers. Forcing an index crawl and a two-page accordion onto a page dict
   would have added hooks the base does not need; the helpers are what those two shared.
2. Hash identity on fixtures is the gate, not test-text identity: the tests' stub target moved because the GET moved.
3. The base default is MDOT's table because it was the latest written and the most explicit about order; it is a
   default for the next agency, not a replacement for the four that differ.
