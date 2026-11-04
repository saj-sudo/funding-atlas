"""The hand-list base: what a connector built on a few hand-listed agency pages shares (milestone 12.1).

Seven connectors grew the same shape one agency at a time (`va_dcr`, `va_vdot`, `de_dnrec`, `de_dema`, `de_deldot`,
`de_dsha`, `md_mdot`): a dict of pages, one GET each with a pause between, a page read into `(kind, text)` blocks, the
lines under an eligibility label plus the sentences that say who may apply, one sentence that states the round, a
status rule over it, and a stored copy as the fallback when a page cannot be read. This module holds the parts that
were byte-identical across them and a class that walks the page dict; the regexes, the status table and the field
mapping stay in each agency's module, because those are what differ from one agency to the next and the gate for
this extraction was that every fixture's `record_hash` stays the same (`docs/connectors/hand_list.md`).

A new agency is a short module: constants, `PAGES`, a `parse_page` (which selector holds the body, which lines to
drop), two regexes (the label that heads the applicant list, the sentence that names an applicant) and `fields`.
The class's own `status_for` and `round_sentence` are the MDOT table (accepting with a date -> open while the date
is ahead; year-round -> open and rolling; awards announced or closed wording -> closed; nothing -> unknown) for an
agency that has not shown a reason to differ.

`va_vdot` (an index crawl) and `de_dema` (two fixed pages, no blocks) are not page dicts and use the helpers only.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup, Comment, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import NEGATION_RE, sentences
from connectors.sam_assistance_listings import clean
from connectors.text import applicant_types_for
from pipeline.models import ApplicantTag, Program, RawRecord

DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

_MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
# "March 1, 2027"; the second also takes "March 1st, 2027" (DelDOT, MDOT). Which one a page gets is the module's call.
DATE_RE = re.compile(rf"\b{_MONTHS}\s+\d{{1,2}},?\s+\d{{4}}\b")
DATE_ORDINAL_RE = re.compile(rf"\b{_MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b")
_ORDINAL_RE = re.compile(r"(\d)(?:st|nd|rd|th)")

Blocks = list[tuple[str, str]]


# ---------- HTTP ----------

def client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def get(client: httpx.Client, url: str) -> str:
    """One page. Tests patch this name (`hand_list.get`); `HandListConnector.fetch` looks it up at call time."""
    r = client.get(url)
    r.raise_for_status()
    return r.text


# ---------- parsing (no I/O) ----------

def soup(page_html: str) -> BeautifulSoup:
    """The page with its HTML comments removed: agencies leave stale banners in them."""
    out = BeautifulSoup(page_html, "html.parser")
    for c in out.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return out


def li_text(el: Tag) -> str:
    """A list item's own text, so a nested list is read as its own items; the whole item when it has no own text."""
    return clean(" ".join(el.find_all(string=True, recursive=False)) or el.get_text(" "))


def is_label(el: Tag, text: str, bold_max: int | None) -> bool:
    """A heading, or (when `bold_max` is set) a short block that is entirely bold: the page's own way of labelling
    a list. `text` is the block's text as the caller read it."""
    if el.name in ("h2", "h3", "h4", "h5", "h6"):
        return True
    if bold_max is None:
        return False
    bold = el.find(["strong", "b"])
    return bool(text) and len(text) <= bold_max and bold is not None and clean(bold.get_text(" ")) == text


def blocks_from(content: Tag, tags: list[str], *, stop_re: re.Pattern[str] | None = None,
                drop_re: re.Pattern[str] | None = None, bold_max: int | None = None) -> Blocks:
    """(kind, text) in document order for the elements named in `tags`: kind `label` for a heading (or a bold-only
    block of at most `bold_max` characters), else the tag name. Empty text is skipped, a line matching `drop_re` is
    dropped (contacts), and a heading matching `stop_re` ends the read (a "Questions?" block)."""
    blocks: Blocks = []
    for el in content.find_all(tags):
        text = li_text(el) if el.name == "li" else clean(el.get_text(" "))
        if stop_re and el.name.startswith("h") and stop_re.match(text):
            break
        if not text or (drop_re and drop_re.search(text)):
            continue
        blocks.append(("label" if is_label(el, text, bold_max) else el.name, text))
    return blocks


def label_lines(blocks: Blocks, label_re: re.Pattern[str], applicant_re: re.Pattern[str], *,
                keep_kinds: tuple[str, ...] | None = None, keep_label: bool = False) -> list[str]:
    """The lines under a label that matches `label_re` (every kind, or only `keep_kinds`; the label itself when
    `keep_label`), and from every other block the sentences that match `applicant_re`, each once."""
    out: list[str] = []
    on = False
    for kind, text in blocks:
        if kind == "label":
            on = bool(label_re.search(text))
            if on and keep_label:
                out.append(text)
            continue
        if on and (keep_kinds is None or kind in keep_kinds):
            out.append(text)
            continue
        on = False
        for s in sentences(text):
            if applicant_re.search(s) and s not in out:
                out.append(s)
    return out


def first_sentence(blocks: Blocks, pattern: re.Pattern[str]) -> str | None:
    """The first sentence in the blocks that matches."""
    for _kind, text in blocks:
        for s in sentences(text):
            if pattern.search(s):
                return s
    return None


def first_p(blocks: Blocks) -> str | None:
    return next((t for k, t in blocks if k == "p"), None)


def last_date(text: str | None, date_re: re.Pattern[str] = DATE_RE) -> date | None:
    """The last full date in the text (a deadline sentence names the deadline last), ordinals folded."""
    dates = [parse_date(_ORDINAL_RE.sub(r"\1", m)) for m in date_re.findall(text or "")]
    dates = [d for d in dates if d]
    return dates[-1] if dates else None


def quote_lines(hand_quotes: dict[str, tuple[str, str, list[str]]], slug: str) -> list[str]:
    """Eligibility sentences quoted by hand from a document the page links, dated and attributed, so the record
    says where the words come from (the Illinois NOFO precedent). `slug -> (date read, source, lines)`."""
    read, source, lines = hand_quotes.get(slug, ("", "", []))
    return [f"{source}, read {read}: {line}" for line in lines]


def resolve_missing(source_id: str) -> dict[str, Any] | None:
    """A hand-listed page that could not be read: unknown, no request."""
    return {"status": "unknown"}


def applicant_tags(lines: list[str]) -> list[ApplicantTag]:
    """The shared tagger over every sentence of the lines, negated sentences dropped."""
    kept = [s for line in lines for s in sentences(line) if not NEGATION_RE.search(s)]
    return applicant_types_for(kept or None)


# ---------- the base ----------

class HandListConnector:
    """A dict of hand-listed pages, each read once a run. Subclasses set the constants and `PAGES`, implement
    `parse_page` and `fields`, and override `urls_for` (a slug with several pages) and `records_for` (a page with
    several programs, or a payload that carries more than the page) where the agency needs it."""

    CONNECTOR: str
    BASE: str
    AGENCY: str
    AGENCY_CODE: str
    JURISDICTION: str
    PAGES: dict[str, Any] = {}

    # The default status table (MDOT's): a round sentence is picked in this order and judged by these.
    OPEN_RE = re.compile(r"\b(?:now )?accepting\b[^.]*\bapplications\b|\bapplications?\b[^.]*\b(?:are|is|will be|now) (?:open|accepted)\b", re.I)
    ROLLING_RE = re.compile(r"year-round|rolling basis", re.I)
    ANNOUNCED_RE = re.compile(r"\bawards?\b[^.]*\b(?:have|has) (?:now )?been announced\b|\bawards? (?:are|were) announced\b", re.I)
    CLOSED_RE = re.compile(r"\bclosed for applications\b|\b(?:is|are) (?:now )?closed\b|\bno longer accepting\b", re.I)
    DATE_RE = DATE_ORDINAL_RE

    # -- hooks --

    def urls_for(self, slug: str, spec: Any) -> list[str]:
        """The URLs a slug is read from; the default takes `spec` as a path under `BASE`."""
        return [self.BASE + spec]

    def parse_page(self, page_html: str) -> dict[str, Any]:
        raise NotImplementedError

    def records_for(self, slug: str, spec: Any, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        """(source_id, payload) for what a slug's pages hold; `count` is how many records the run has so far (a
        program without an id of its own is numbered by it). The default: one record, the page."""
        return [(slug, {"page": pages[0]})]

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        """Every Program field the agency decides (name, source_url, funding_type, funding_source, match_required,
        status, opens_at, closes_at, closes_at_text, rolling, summary, eligibility_text, eligibility_structured,
        applicant_types, categories)."""
        raise NotImplementedError

    # -- the shared shape --

    def fetch(self, limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
        """Every page in `PAGES`, in order, a pause between GETs. A slug whose page cannot be read falls back to
        every stored record of that slug (`slug` or `slug#...`), or is skipped. Stops once `limit` records exist."""
        prior = prior or {}
        records: list[RawRecord] = []
        first = True
        with client() as c:
            for slug, spec in self.PAGES.items():
                if limit and len(records) >= limit:
                    break
                pages: list[dict[str, Any]] = []
                try:
                    for url in self.urls_for(slug, spec):
                        if not first:
                            time.sleep(DELAY_S)
                        first = False
                        pages.append(self.parse_page(get(c, url)))
                except httpx.HTTPError:
                    records += [RawRecord(source_connector=self.CONNECTOR, source_id=sid, payload=p)
                                for sid, p in prior.items() if sid == slug or sid.startswith(slug + "#")]
                    continue
                for sid, payload in self.records_for(slug, spec, pages, len(records)):
                    records.append(RawRecord(source_connector=self.CONNECTOR, source_id=sid, payload=payload))
        return records[:limit] if limit else records

    def resolve_missing(self, source_id: str) -> dict[str, Any] | None:
        return resolve_missing(source_id)

    def normalize(self, raw: RawRecord, today: date | None = None) -> Program:
        return Program(
            source_connector=self.CONNECTOR,
            source_id=raw.source_id,
            external_number=None,
            level="state",
            jurisdiction=self.JURISDICTION,
            administering_agency=self.AGENCY,
            agency_code=self.AGENCY_CODE,
            amount_min=None,
            amount_max=None,
            match_pct=None,
            alns=[],
            **self.fields(raw, today or date.today()),
        )

    # -- the default status table --

    def round_sentence(self, blocks: Blocks) -> str | None:
        """The first sentence that states the round: accepting with a date, then accepting at all (year-round
        included), then awards announced, then closed."""
        sents = [s for _, text in blocks for s in sentences(text)]
        for rule in (lambda s: self.OPEN_RE.search(s) and not NEGATION_RE.search(s) and self.DATE_RE.search(s),
                     lambda s: self.OPEN_RE.search(s) and not NEGATION_RE.search(s),
                     lambda s: self.ANNOUNCED_RE.search(s),
                     lambda s: self.CLOSED_RE.search(s)):
            hit = next((s for s in sents if rule(s)), None)
            if hit:
                return hit
        return None

    def closes_at_for(self, sentence: str | None) -> date | None:
        """The last date in the round sentence, read with the class's date regex."""
        return last_date(sentence, self.DATE_RE)

    def status_for(self, sentence: str | None, closes_at: date | None, today: date) -> tuple[str, bool | None]:
        """(status, rolling) from the round sentence."""
        if not sentence:
            return "unknown", None
        if self.OPEN_RE.search(sentence) and not NEGATION_RE.search(sentence):
            if closes_at:
                return ("open" if closes_at >= today else "unknown"), None
            if self.ROLLING_RE.search(sentence):
                return "open", True
            return "open", None
        if self.ANNOUNCED_RE.search(sentence) or self.CLOSED_RE.search(sentence):
            return "closed", None
        return "unknown", None
