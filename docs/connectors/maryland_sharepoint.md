# Maryland SharePoint (mdgov theme): platform notes and the shared base

Milestone 7. MEA and DNR run on the same SharePoint theme; MDEM, MDOT and MDE (not yet connected) do too. The base
was extracted at DNR, the second site, the way `maryland_drupal.py` was extracted at Commerce: `md_mea` was written
standalone first, and the extraction commit left every MEA fixture's `record_hash` unchanged.

## What the sites share (verified on 28 MEA and 21 DNR pages, 2026-10-16)

| | energy.maryland.gov (MEA) | dnr.maryland.gov (DNR) |
|---|---|---|
| Sitemap | 404 | 404 |
| robots.txt | allows `/Pages/`; disallows `/_vti_bin/`, `/_layouts/`, `/_catalogs/` | same |
| Page body | `#ctl00_PlaceHolderMain_RichHtmlField1__ControlWrapper_RichHtmlField` inside the first `section.mdgov-section` of `main#mdgovMain` | same |
| Page `<h1>` | `#ctl00_PlaceHolderMain_editmodepanel2 h1` | same; on four Land Acquisition pages it is the unit name, on one MET page it is empty |
| `<meta name="description">` | every page, always the theme's "An official website of the State of Maryland." | same |
| `Last-Modified` | one CDN timestamp on every page | same |
| `ETag` | none | none |
| Cloudflare e-mail obfuscation | every page with a mailto (`data-cfemail` rewritten per response) | the index and about half the pages |
| Path case | indexes link mixed case; served case-insensitively, no redirect | same, plus `http://` links on the index |
| Enumeration | five category index pages | one hand-curated index page + one hand-added page |
| Status | labeled lines, prose on older pages | prose only |

## The base: `connectors/maryland_sharepoint.py`

Pure helpers: `source_id_for(url)` (lowercased path, fragment dropped, percent-escapes kept), `canonical_url(href,
page_url)` (absolute https, no fragment), `fixture_name(source_id)` (`/` → `__`, `.aspx` stripped), `main_section`,
`body_div`, `page_h1`, `page_payload(url, html)` → `{url, title, description, main_html, content_hash}`, `leaf_lines`
(each block's own text, minus nested blocks), `page_sentences`, `text_hash` (sha256 of the cleaned text, never the
markup), `parse_text_date` (first `Month D, YYYY` in a value's first sentence, times and weekdays ignored, "P.M."
not treated as a sentence end), `DATE_RE`, `MONTH`.

Subclass contract:

    class attributes  CONNECTOR, BASE, AGENCY, AGENCY_CODE, PASS_THROUGH
    index_entries(client) -> {source_id: {url, ...facts}}   enumerate; raise if an index does not load
    annotate(payload, entry)                                 stamp the index facts onto the payload (default: every key but url)
    is_record(payload)                                       default: the page has an mdgov body
    name_for(payload)                                        default: the H1, else the <title>
    status_fields(payload, today)                            -> {status, opens_at, closes_at, closes_at_text, rolling}
    applicant_lines(payload)                                 the lines scanned for applicant keywords; also the eligibility_text
    categories_for(payload) / funding_type_for(name, payload)

Shared: `fetch(limit, prior)` (every page every run; `prior` unused; a 404 on an index link is skipped, other errors
raise), `resolve_missing(source_id)` (404 → unknown, network error → None, else what the page says now with no index
facts), `classify_page`, `normalize`.

## Decisions

0. **The meta description is not a summary.** All 48 pages carry the theme's "An official website of the State of
   Maryland."; `summary_for` nulls it. Found on the first rendered page (a card summarised WIF as the state's website);
   the fix changes every SharePoint record's hash once.
1. **Text hash, not markup hash.** Two fetches of the same MEA page differ in `data-cfemail` and agree in text. The
   record hash is the change signal; `content_hash` is for the probe and for audit.
2. **Every page every run.** No usable `Last-Modified` or `ETag`; the sites are small (about 40 and 25 requests).
3. **Index facts are stamped onto each record** (MHT's `listed_open` pattern) instead of storing the index page as a
   record: the pipeline normalizes every RawRecord into a Program. Additions and removals already surface as `added`
   and `missing`; a de-listed page whose text did not change produces no change row and is found in SQL by
   `last_seen` older than the connector's last successful run.
4. **A 404 on an index link is skipped, not fatal.** Dead links are a fact of hand-curated indexes (6 of 34 on MEA,
   2 of 23 on DNR). An index that itself fails to load aborts the run.
5. **`connectors/text.py` did not exist yet (superseded 2026-10-28).** `clean`, `sentences`, `parse_date` and the HTTP
   constants are still imported from where they live (`maryland_drupal.py`, `grants_gov.py`,
   `sam_assistance_listings.py`). `applicant_types_for` and `funding_type_for` moved to `connectors/text.py` when
   Pennsylvania, West Virginia, California and Illinois were importing them from a Maryland module; this module
   imports them back, so nothing here changed.
