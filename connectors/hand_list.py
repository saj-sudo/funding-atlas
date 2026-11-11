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
from connectors.text import applicant_types_for, funding_type_for, portal_categories
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

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


BLOCK_TAGS = {"p", "div", "ul", "ol", "li", "table", "section", "nav", "h1", "h2", "h3", "h4", "h5", "h6"}


def own_text(el: Tag) -> str:
    """A block's text minus its nested blocks: SharePoint nests <p> inside <p>, <h2> inside <p> and <div class="row">
    inside <p>, so the outer element's full text would repeat every child and fuse a banner with the paragraphs after
    it."""
    parts = [str(c) if not isinstance(c, Tag) else ("" if c.name in BLOCK_TAGS else c.get_text(" ")) for c in el.children]
    return clean(" ".join(parts))


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



# ---------- the agency-page table (Vermont 12.6a, moved here when Connecticut 12.6b reused it) ----------
#
# A state whose agencies share one CMS gets a base of its own (a page reader and constants: `vermont_drupal.py`,
# `connecticut_portal.py`); the status table, the applicant reader and the field mapping below are what two such
# states share. docs/connectors/vermont.md and docs/connectors/connecticut.md give the reasons for each rule.

AGENCY_DATE_RE = re.compile(rf"\b{_MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b|\b\d{{1,2}}/\d{{1,2}}/\d{{4}}\b")
# The words a deadline sits next to: "due", "deadline", "submitted by" (Connecticut DEEP: "Applications must be
# submitted by November 6, 2026"), and "through" only in a sentence that says applications are being accepted
# ("Through December 4, 2026, the Department is currently accepting applications"), never a grant term's "through".
DUE_RE = re.compile(r"\b(?:due|deadline|submitted by)\b|\bthrough\b(?=[^.]*\baccepting\b)", re.I)
NOT_DEADLINE_RE = re.compile(r"\b(?:closeout|close-out|report(?:s|ing)?|grant term|implementation period|reimbursement)\b", re.I)
OPENS_RE = re.compile(r"\bapplications?\s+opens?\b|\bpre-applications?\s+open\b|\bopen(?:s)?\s+(?:on|by)\b", re.I)
AGENCY_OPEN_RE = re.compile(r"\b(?:is|are)\s+now\s+open\b|\bnow\s+accepting\b|\baccepting\s+applications\b"
                            r"|\b(?:is|are)\s+(?:now\s+)?being\s+accepted\b"   # Kentucky ARC: "Pre-applications ... are being accepted"
                            r"|\b(?:is|are)\s+currently\s+open\b"   # Missouri DED (12.6e): "The Emergency Cycle is currently open."
                            r"|\bapplication period is open\b", re.I)   # Missouri DNR's banner heading on every program page
AGENCY_CLOSED_RE = re.compile(r"\b(?:is|are)\s+(?:now\s+)?closed\b|\bclosed\s+for\s+applications\b|\bno\s+longer\s+accepting\b", re.I)
# "submitted by" is a deadline only in a sentence about applications: NDDOT's TA page has "final plans, permits,
# certifications, etc., need to be completed and submitted by January 1, 2028" (a construction milestone, 12.6c).
APPLICATION_RE = re.compile(r"\bapplications?\b", re.I)
# A deadline's date sits next to its word; a date further off in the sentence is another fact.
NEAR_CHARS = 40

ELIGIBILITY_LABEL_RE = re.compile(r"\bapplicant eligibility\b|\bwho (?:is|are|may be) eligible\b|\bwho (?:can|may) apply\b"
                                  r"|\beligible applicants\b"
                                  # North Dakota (12.6c): NDDOT's "Eligible Project Applicants"; Parks' "The following
                                  # entities are eligible to apply:" over a list.
                                  r"|\beligible project applicants\b|\bentities are eligible\b"
                                  # Kentucky (12.6d): KIA's bare "Eligibility:" label over the loan fund's conditions.
                                  r"|^eligibility:?$"
                                  # Missouri (12.6e): DED's "Do I Qualify?" tab is its eligibility section.
                                  r"|^do i qualify\??$", re.I)
APPLICANT_SENTENCE_RE = re.compile(
    r"\beligible applicants?\b|\beligibility\b[^.]*\blimited to\b|\b(?:funds?|funding|grants?)\b[^.]*\bavailable to\b"
    r"|\b(?:grant|grants|grant funding|funding)\s+to\s+municipalit|\bmay apply\b|\beligible to (?:apply|submit)\b"
    r"|\b(?:is|are) eligible for funding\b|\bfor local municipalities\b"
    # Connecticut (12.6b): "accepting applications from municipalities", "Applicants must be a municipality",
    # "only available to Connecticut towns and cities", "State funds to urbanized area municipal governments",
    # "grants-in-aid to towns", "enables municipalities ... to apply", "sub-entities able to apply".
    r"|\baccept(?:s|ing) applications from\b|\bapplicants? must be\b|\b(?:is|are) (?:only )?available to\b"
    r"|\b(?:funds?|funding|grants?(?:-in-aid)?)\s+to\s+(?:[\w-]+\s+){0,3}"
    r"(?:municipal\w*|towns?|cities|count(?:y|ies)|local governments?)\b"
    r"|\benables?\b[^.]*\bto apply\b|\bable to apply\b|\bserves? as the sub-?applicant\b"   # FEMA: a town is the sub-applicant
    # North Dakota (12.6c): Commerce's "Eligible Entities – City, County, ..." (a line that starts with it: SLCGP quotes a
    # statute's "award grants to eligible entities"), NDDOT's "This program is open to non-oil
    # townships", "projects identified by political subdivisions" and "an opportunity for cities with a population of
    # over 5,000", DES's "FEMA provides supplemental aid to state, local, tribal ...".
    r"|^eligible entities\b|\bprogram is open to\b|\bprojects identified by\b"
    r"|\bopportunity for (?:[\w-]+\s+){0,2}(?:cities|counties|towns|townships|municipal\w*)\b"
    r"|\bprovides?\s+(?:\w+\s+)?aid to\b"
    r"|\beligible jurisdictions\b[^.]*\bmay submit\b"   # ND HMGP: "All eligible jurisdictions ... may submit" (10.6)
    # Kentucky (12.6d): DLG's "Who can Apply: ..." line on every CDBG, DRA and ARC page.
    r"|^who (?:can|may) apply\b"
    # Missouri (12.6e): DNR's "Eligible recipients include the following:" over the list of who may apply (EECBG, Energy Loans).
    r"|\beligible recipients\b", re.I)
SHORT_ITEM = 160
FEDERAL_RE = re.compile(
    r"\bFederal Highway Administration\b|\bFHWA\b|\bFEMA\b|\bFederal Emergency Management Agency\b|\bHUD\b"
    r"|\bHousing and Urban Development\b|\bNational Park Service\b|\bfederally funded\b"
    r"|\bfunded with federal aid\b", re.I)   # NDDOT's Urban Grant Program (12.6c)
FUNDING_SOURCE_RE = re.compile(r"^funding source:", re.I)
FEDERAL_LINE_RE = re.compile(r"\bfederal\b|\bFHWA\b|\bFEMA\b|\bHUD\b|\bNational Park Service\b|\bEnvironmental Protection Agency\b|\bEPA\b", re.I)
# "serve as the sub-applicant on behalf of homeowners or businesses" (Connecticut HMGP): whoever an applicant applies on
# behalf of benefits, and does not apply; the clause is cut before tagging (the stored text keeps it).
ON_BEHALF_RE = re.compile(r"\bon behalf of\b[^.;]*", re.I)
# Missouri DNR (12.6e): "Counties, incorporated cities and towns, ... and political subdivisions that are not owned by the
# federal government" defines the applicants, and its "not" would drop the whole line; and "...a plan to provide safe
# drinking water to a group of households" names who the project serves, not who applies. Both clauses are cut before
# tagging (the stored text keeps them).
NOT_FEDERAL_RE = re.compile(r"\b(?:that|which) are not owned by (?:the )?federal government\b", re.I)
BENEFICIARY_RE = re.compile(r"\bprovide\b[^.;]*?\bto (?:a group of )?(?:households|homeowners|residents)\b[^.;]*", re.I)
# "governmental organizations other than state agencies are eligible" (Missouri scrap tire grants) excludes the state; it
# does not name it.
OTHER_THAN_STATE_RE = re.compile(r"\bother than (?:the )?state\b[^.;,]*", re.I)
# "Non-profits and private sector entities may partner with an eligible applicant" (Kentucky CMAQ): a partner, not an
# applicant; the sentence stays in the stored text and is not tagged.
PARTNER_LINE_RE = re.compile(r"\bmay partner with\b", re.I)
MATCH_RE = re.compile(r"\bmatch(?:ing)?\b[^.]*\brequired\b|\brequire[sd]?\b[^.]*\bmatch\b", re.I)
MATCH_NOT_RE = re.compile(r"\bno match\b|\bmatch (?:is )?not required\b", re.I)


def clause_cut(line: str) -> str:
    """The line with the clauses that name a beneficiary, or define an applicant by what it is not, cut before tagging."""
    return OTHER_THAN_STATE_RE.sub("", BENEFICIARY_RE.sub("", NOT_FEDERAL_RE.sub("", ON_BEHALF_RE.sub("", line))))


def all_sentences(blocks: Blocks) -> list[str]:
    return [s for _, text in blocks for s in sentences(text)]


def _date(text: str) -> date | None:
    return parse_date(_ORDINAL_RE.sub(r"\1", text))


def first_date(text: str) -> date | None:
    for m in AGENCY_DATE_RE.finditer(text):
        d = _date(m.group(0))
        if d:
            return d
    return None


_FULL_DATE = rf"{_MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}"
# "Applications Accepted: Dates are April 1, 2026 - September 1, 2026" (Kentucky DLG, every CDBG page): a window with no
# deadline word, read only when the sentence is about applications and no deadline word was found anywhere.
RANGE_RE = re.compile(rf"({_FULL_DATE})\s*(?:-|\u2013|\u2014|to|through)\s*({_FULL_DATE})", re.I)


def application_range(sents: list[str]) -> tuple[str, date, date] | None:
    for s in sents:
        m = RANGE_RE.search(s)
        if m and APPLICATION_RE.search(s) and not NOT_DEADLINE_RE.search(s):
            start, end = _date(m.group(1)), _date(m.group(2))
            if start and end:
                return s, start, end
    return None


def deadline(sents: list[str]) -> tuple[str | None, date | None]:
    """The first sentence with a deadline word and a date next to it (not a closeout, report or grant-term date)."""
    for s in sents:
        if NOT_DEADLINE_RE.search(s):
            continue
        for due in DUE_RE.finditer(s):
            if due.group(0).lower() == "submitted by" and not APPLICATION_RE.search(s):
                continue
            for m in AGENCY_DATE_RE.finditer(s):
                gap = m.start() - due.end() if m.start() >= due.end() else due.start() - m.end()
                d = _date(m.group(0)) if gap <= NEAR_CHARS else None
                if d:
                    return s, d
    window = application_range(sents)
    return (window[0], window[2]) if window else (None, None)


def opening(sents: list[str]) -> date | None:
    for s in sents:
        if OPENS_RE.search(s) and not DUE_RE.search(s):
            d = first_date(s)
            if d:
                return d
    window = application_range(sents)
    return window[1] if window else None


def round_for(blocks: Blocks, today: date) -> dict[str, Any]:
    """status, opens_at, closes_at, closes_at_text: a deadline still ahead (forecasted while the opening is ahead),
    then closed wording, then a past deadline (unknown: it outranks a stale "now open"), then undated open wording."""
    sents = all_sentences(blocks)
    due_s, due = deadline(sents)
    opens = opening(sents)
    closed_s = next((s for s in sents if AGENCY_CLOSED_RE.search(s)), None)
    open_s = next((s for s in sents if AGENCY_OPEN_RE.search(s) and not NEGATION_RE.search(s)), None)
    if due and due >= today:
        status, text = ("forecasted" if opens and opens > today else "open"), due_s
    elif closed_s:
        status, text = "closed", closed_s
    elif due:
        status, text = "unknown", due_s
    elif open_s:
        status, text = "open", open_s
    else:
        status, text = "unknown", None
    return {"status": status, "opens_at": opens, "closes_at": due, "closes_at_text": text}


# The labelled lines a page prints under a program's heading (Kentucky's Energy and Environment Cabinet).
META_LINE_RE = re.compile(r"^(?:administering agency|type of funding|funding source|eligible entities)\s*:", re.I)


def summary_for(blocks: Blocks) -> str | None:
    """The first paragraph that is not a status line or a labelled metadata line."""
    for kind, text in blocks:
        if kind == "p" and not (AGENCY_OPEN_RE.search(text) or AGENCY_CLOSED_RE.search(text) or DUE_RE.search(text)
                                or META_LINE_RE.search(text)):
            return text
    return None


def applicant_lines(blocks: Blocks, short_item: int = SHORT_ITEM) -> list[str]:
    """List items under an applicant label (up to `short_item` characters), kept whole; from every block (bold labels
    included) the sentences that say who may apply. A paragraph that says neither ends the label's list."""
    out: list[str] = []
    on = False
    for kind, text in blocks:
        if kind == "label":
            on = bool(ELIGIBILITY_LABEL_RE.search(text))
        elif on and kind == "li" and len(text) <= short_item:
            if text not in out:
                out.append(text)
            continue
        hits = [s for s in sentences(text) if APPLICANT_SENTENCE_RE.search(s)]
        if kind == "p" and not hits:
            on = False
        out += [s for s in hits if s not in out]
    return out


def funding_source_for(blocks: Blocks, text: str) -> str:
    """A page's own "Funding source:" line decides; else the page must name the federal source."""
    line = next((t for _, t in blocks if FUNDING_SOURCE_RE.search(t)), None)
    if line is not None:
        return "pass_through" if FEDERAL_LINE_RE.search(line) else "direct"
    return "pass_through" if FEDERAL_RE.search(text) else "direct"


Split = tuple[str, str | None, re.Pattern[str] | None]


def split_sections(blocks: Blocks, splits: list[Split], kinds: tuple[str, ...] = ("label",)) -> list[tuple[str, str, Blocks]]:
    """A page that holds several programs, cut into one `(sub_slug, name, blocks)` per program (Saj's rule,
    2026-11-11: a page with three programs is three records). A section starts at the first block of a kind in `kinds`
    (headings; a page that names its programs only in paragraphs adds `p`) that matches a split's pattern and runs to
    the next such block that matches any split's pattern; a split whose name is `None` is a tail (a funding note, a "for
    more information" link): its blocks belong to no program. What sits above the first section is shared and follows
    every section, so a page-wide deadline or applicant sentence is never lost, and the section's own first paragraph
    stays the summary. **A first split with no pattern is the page's head**: the blocks above the first match are its
    program (HMGP is the body of Vermont's page, the others are paragraphs at the end) and nothing is shared. A split that
    matches no block yields no section."""
    head = bool(splits) and splits[0][2] is None
    starts = [(i, idx) for i, (kind, text) in enumerate(blocks) if kind in kinds
              for idx, (_, _, pattern) in enumerate(splits) if pattern is not None and pattern.search(text)]
    if not starts:
        return []
    shared: Blocks = [] if head else blocks[: starts[0][0]]
    out: list[tuple[str, str, Blocks]] = []
    if head and splits[0][1] is not None:
        out.append((splits[0][0], splits[0][1], blocks[: starts[0][0]]))
    for n, (begin, idx) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(blocks)
        sub_slug, name, _ = splits[idx]
        if name is not None:
            out.append((sub_slug, name, blocks[begin:end] + shared))
    return out


class AgencyPageConnector(HandListConnector):
    """An agency on a state CMS: set CONNECTOR, BASE, AGENCY, AGENCY_CODE, JURISDICTION, CATEGORY_LABEL and PAGES
    (slug -> path); the state's base supplies `parse_page` (title and blocks)."""

    CATEGORY_LABEL: str = ""
    # The longest list item kept whole under an eligibility label (Missouri DNR lists whole sentences of applicants).
    APPLICANT_ITEM_MAX: int = SHORT_ITEM
    # slug -> (date read, source, lines): who may apply, quoted by hand from a document the page links when the page
    # itself names no applicant (the MDOT and Illinois precedent).
    HAND_QUOTES: dict[str, tuple[str, str, list[str]]] = {}
    # slug -> [(sub_slug, name, heading pattern)] for a page with several programs, in page order (see
    # `split_sections`). The first declared program keeps the page's own `source_id`, so a record that was one before
    # the split keeps its history; the others are `slug#sub_slug`.
    SPLITS: dict[str, list[Split]] = {}
    # slug -> the block kinds a split heading may be (default: labels only; a page that names its programs in paragraphs
    # says ("label", "p")).
    SPLIT_KINDS: dict[str, tuple[str, ...]] = {}
    # source_id -> value, for an agency whose pages mix kinds: the funding type when the name carries no keyword
    # ("Fund A - Wastewater" is a loan fund), and the portal-style category label when one agency covers several topics.
    FUNDING_TYPES: dict[str, str] = {}
    # source_id -> "direct" | "pass_through" where the page mentions a federal agency without being federally funded.
    FUNDING_SOURCES: dict[str, str] = {}
    CATEGORY_LABELS: dict[str, str] = {}

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        page = pages[0]
        splits = self.SPLITS.get(slug)
        sections = split_sections([tuple(b) for b in page.get("blocks", [])], splits, self.SPLIT_KINDS.get(slug, ("label",))) if splits else []
        if not sections:
            return [(slug, {"path": spec, "page": page})]
        first = splits[0][0]
        return [(slug if sub == first else f"{slug}#{sub}",
                 {"path": spec, "name": name, "page": {"title": page.get("title", ""), "blocks": blocks}})
                for sub, name, blocks in sections]

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        page = raw.payload["page"]
        path = raw.payload.get("path") or self.PAGES.get(raw.source_id, "/" + raw.source_id)
        blocks = [tuple(b) for b in page.get("blocks", [])]
        text = " ".join(t for _, t in blocks)
        name = raw.payload.get("name") or clean(page.get("title", "")) or raw.source_id
        label = self.CATEGORY_LABELS.get(raw.source_id, self.CATEGORY_LABEL)
        lines = applicant_lines(blocks, self.APPLICANT_ITEM_MAX) + quote_lines(self.HAND_QUOTES, raw.source_id)
        match = None if MATCH_NOT_RE.search(text) else (True if MATCH_RE.search(text) else None)
        return dict(
            source_url=self.BASE + path,
            name=name,
            funding_type=self.FUNDING_TYPES.get(raw.source_id) or funding_type_for(name) or "grant",
            funding_source=self.FUNDING_SOURCES.get(raw.source_id) or funding_source_for(blocks, text),
            match_required=match,
            rolling=None,
            summary=summary_for(blocks),
            eligibility_text="\n".join(lines) or None,
            eligibility_structured=None,
            applicant_types=applicant_tags([clause_cut(line) for line in lines if not PARTNER_LINE_RE.search(line)]),
            categories=[CategoryTag(value=v, source_code=label) for v in portal_categories(label)],
            **round_for(blocks, today),
        )
