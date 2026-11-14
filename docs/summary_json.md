# `summary.json`: a state's page in numbers

One file per state, beside the page: `https://saj-sudo.github.io/funding-atlas/md/summary.json`. Written by
`scripts/build_site.py` (`summary_json`) from the same payload the page embeds, so the two cannot disagree.

## Why it exists

Another site wants to say "12 state programs are open to towns in Maryland, three close this month" and link
to the page. Before this it had to pull the JSON out of the HTML. `changes.json` is the change log, not the
list of what is open. First reader: CivicRadar's state pages (decision 2026-11-14).

## Shape

```json
{
 "generated_at": "2026-11-14T06:00:00Z",
 "state": {"code": "MD", "name": "Maryland"},
 "page": "https://saj-sudo.github.io/funding-atlas/md/",
 "audience": "local governments",
 "license": {"records": "ODbL-1.0", "attribution": "Funding Atlas", "source": "https://github.com/saj-sudo/funding-atlas"},
 "open": {"state": 12, "federal": 310},
 "by_category": [{"category": "housing", "open": 4}, {"category": "water", "open": 3}],
 "closing_soon": [
  {"name": "...", "agency": "...", "closes_at": "2026-12-01", "days_to_close": 17,
   "link": "https://saj-sudo.github.io/funding-atlas/md/#p=..."}
 ]
}
```

## Rules

- **Same rows as the page.** `open.state` counts the state's own rows on the page (open or forecasted, a local
  government can apply, tier likely or possible). Rows the page lists as "Status not confirmed" or "Closed
  recently" are not counted: nothing says they are open. `open.federal` is the federal rows, one number, because
  they are the same on every state page (they ship once in `federal.js`).
- **`by_category`** counts the state's own rows per category, most first. A program with two categories is
  counted in both, so the counts can add up to more than `open.state`.
- **`closing_soon`** is the nearest five deadlines the source states, state rows only. A placeholder date
  (the page's "no deadline stated" rule) and a date already past are never listed. Rolling programs with no
  date are not listed. Fewer than five is normal; an empty list means no state row states a near deadline.
- **Nothing is invented.** Every value is a count or a field of a stored record.
- **Additive only.** A reader may rely on the keys above; new keys can appear, these do not change meaning.
- **Licence.** The records are ODbL 1.0: a reader that shows them credits Funding Atlas and links back.
