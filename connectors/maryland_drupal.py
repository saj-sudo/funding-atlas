"""Shared base for Maryland agencies on the maryland.gov Drupal platform (DHCD, Commerce, MHT).

Every one of these sites has the same skeleton, verified page by page on 2026-10-15 (see
docs/connectors/maryland_drupal.md): a sitemap.xml with per-page <lastmod>, a <main> element, an <h1>
program name, <meta name="description">, <meta property="og:updated_time">, and a body in
<div class="usa-prose maryland-toc-target"> organized by <h2> sections. What differs per agency is small
and lives in a subclass: which pages are records, how the status and dates are read, and which section
headings name the applicants. Everything else (enumeration, the refetch gate, the raw payload, resolving
a vanished page, eligibility text, applicant tagging, funding type, categories) is here and not repeated.

Subclass contract:
  class attributes  CONNECTOR, BASE, AGENCY, AGENCY_CODE, and optionally SKIP_PATH / KEEP_PATH,
                    SECTION_CATEGORIES, PASS_THROUGH, APPLICANT_HEADING_RE, THING_HEADING_RE
  is_record(payload)                        does this page carry a status-type field?
  status_fields(payload, sections, today)   -> {status, opens_at, closes_at, closes_at_text, rolling}
  amounts(sections)                         -> (amount_min, amount_max), default (None, None)
  before_fetch(client) / annotate(payload, context)   for a site-level signal stamped onto every payload

Each connector module binds one instance to module-level fetch / normalize / resolve_missing, so the
pipeline contract (`connectors/<name>.py` exposing those three) is unchanged.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from connectors.sam_assistance_listings import clean
from pipeline.models import ApplicantTag, CategoryTag, Program, RawRecord

PAGE_DELAY_S = 0.3
TIMEOUT_S = 30.0
USER_AGENT = "funding-atlas/0.1 (+https://github.com/saj-sudo/funding-atlas)"

# Phrase regex -> applicant types, scanned over the who-may-apply sections only, never the whole page.
# The matched phrase is stored as source_code so the inference is auditable in SQL. Shared by all three
# agencies; a phrase that is wrong for one of them is wrong for all and gets fixed here.
APPLICANT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"units? of (?:general )?local government", ("municipality", "county")),
    (r"local governments?", ("municipality", "county")),
    (r"municipalit\w*", ("municipality",)),
    (r"\bmunicipal\b", ("municipality",)),           # "municipal governments", "municipal corporations" (MEA, DNR)
    (r"\bcities\b", ("municipality",)),
    (r"\btowns?\b", ("municipality",)),
    (r"\bcount(?:y|ies)\b", ("county",)),
    (r"\bnon-?profits?\b", ("nonprofit",)),
    (r"\bnot-for-profits?\b", ("nonprofit",)),
    (r"501\s?\(c\)\s?\(3\)", ("nonprofit",)),
    (r"(?<!not-)\bfor-profits?\b", ("business",)),
    (r"\bbusiness(?:es)?\b", ("business",)),
    (r"\bretailers?\b", ("business",)),
    (r"\bdevelopers?\b", ("business",)),
    (r"\bhomeowners?\b", ("household",)),
    (r"\bhouseholds?\b", ("household",)),
    (r"\bresidents?\b", ("household",)),
    (r"\brenters?\b", ("household",)),
    (r"\bindividuals?\b", ("individual",)),
    (r"housing authorit\w*", ("housing_authority",)),
    (r"\bschools?\b", ("school",)),
    (r"local education agenc\w*", ("school",)),
    (r"\btrib(?:al|es?)\b", ("tribe",)),
    (r"\bstate (?:government )?agenc\w*", ("state",)),
    (r"\bcolleges?\b|\buniversit\w*|institutions? of higher education", ("higher_ed",)),
)

# Name keyword -> funding_type, first match wins.
FUNDING_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("tax credit", "tax_credit"), ("loan", "loan"), ("voucher", "voucher"), ("grant", "grant"),
)

# Applicant tags are read from lines that talk about who applies or qualifies. A line that names a
# place ("in 4+ cities outside Maryland", "within a Tier 1 County") or a condition is not an applicant
# line; a negated line ("For-profit businesses are not eligible to apply") never is. A paragraph that
# ends with a colon introduces a list of applicants ("an applicant must be either:") unless it ends with
# a condition word ("This credit is for businesses that:"), and list items at the top of a section are
# introduced by the heading itself ("Eligible applicants").
APPLICANT_MARKER_RE = re.compile(
    r"appl(?:y|ies|icant|ication)|eligib|qualif(?:y|ies|ied|ying)|\bis for\b|\bare for\b|\bassists?\b"
    r"|\bopen to\b|\bawarded to\b|\bgo(?:es)? to\b|\bserves?\b|\bbenefit",
    re.I,
)
NEGATION_RE = re.compile(r"\b(?:not|cannot|ineligible|except|excluding|unless)\b", re.I)
CONDITION_LEAD_IN_RE = re.compile(
    r"\b(?:that|must|if|which|who|whose|company|business|businesses|you|categories|tracks|following"
    r"|criteria|requirements)\s*:$",
    re.I,
)
# A place word right after a spatial preposition is a place, not an applicant: "in 4+ cities outside
# Maryland", "within a Tier 1 County", "located in a designated rural county".
LOCATION_CONTEXT_RE = re.compile(
    r"\b(?:in|within|outside|inside|into|across|throughout|near|serving|serve)\s+(?:[\w$%+,'’/()-]+\s+){0,3}$", re.I
)

MATCH_NOT_REQUIRED_RE = re.compile(r"match(?:ing)?(?: funds?)? (?:is|are) not required", re.I)
MATCH_REQUIRED_RE = re.compile(r"match(?:ing)?(?: funds?)? (?:is|are) required", re.I)
ELIGIBILITY_HEADING_RE = re.compile(r"eligib", re.I)
MONTH_YEAR_RE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})$")
MONTH_NAME_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"
)


# ---------- pure helpers (no I/O) ----------

def source_id_for(url: str) -> str:
    return urlparse(url).path.strip("/")


def needs_fetch(lastmod: str | None, prior_payload: dict[str, Any] | None) -> bool:
    """Refetch unless the stored payload has the same sitemap lastmod AND usable page HTML."""
    if not prior_payload or not prior_payload.get("main_html"):
        return True
    return not lastmod or lastmod != prior_payload.get("lastmod")


def page_payload(url: str, lastmod: str | None, html_text: str) -> dict[str, Any] | None:
    """The raw_record payload for one page, or None if the page has no <main>."""
    soup = BeautifulSoup(html_text, "html.parser")
    main = soup.find("main")
    if main is None:
        return None
    updated = soup.find("meta", property="og:updated_time")
    desc = soup.find("meta", attrs={"name": "description"})
    return {
        "url": url,
        "lastmod": lastmod,
        "updated_time": updated.get("content") if isinstance(updated, Tag) else None,
        "description": desc.get("content") if isinstance(desc, Tag) else None,
        "main_html": str(main),
    }


def page_name(main_html: str) -> str:
    soup = BeautifulSoup(main_html, "html.parser")
    h1 = soup.find("h1")
    return clean(h1.get_text(" ")) if h1 else ""


def _prose(main_html: str) -> Tag:
    soup = BeautifulSoup(main_html, "html.parser")
    return soup.select_one(".usa-prose.maryland-toc-target") or soup


def body_sections(main_html: str) -> list[tuple[str, str]]:
    """(heading, text) for each <h2> section of the page body, in order."""
    prose = _prose(main_html)
    out: list[tuple[str, str]] = []
    heading: str | None = None
    parts: list[str] = []

    def flush() -> None:
        if heading is not None:
            out.append((heading, clean(" ".join(parts))))

    for el in prose.children:
        if isinstance(el, Tag) and el.name == "h2":
            flush()
            heading, parts = clean(el.get_text(" ")), []
        elif heading is not None:
            text = el.get_text(" ") if isinstance(el, Tag) else str(el)
            if text.strip():
                parts.append(text)
    flush()
    return out


def section_lines(main_html: str, heading_re: re.Pattern[str]) -> list[tuple[str, str]]:
    """(tag, text) per <li> and <p> of the first <h2> section whose heading matches, in order. Lets a
    connector keep bullet lines separate where body_sections() would join them."""
    prose = _prose(main_html)
    out: list[tuple[str, str]] = []
    inside = False
    for el in prose.children:
        if isinstance(el, Tag) and el.name == "h2":
            if inside:
                break
            inside = bool(heading_re.search(clean(el.get_text(" "))))
        elif inside and isinstance(el, Tag):
            for item in el.find_all(["li", "p"]) if el.name != "p" else [el]:
                text = clean(item.get_text(" "))
                if text:
                    out.append((item.name, text))
    return out


def section_lines_by_heading(main_html: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """(heading, [(tag, text), ...]) for every <h2> section, lines being its <li> and <p> elements."""
    prose = _prose(main_html)
    out: list[tuple[str, list[tuple[str, str]]]] = []
    for el in prose.children:
        if isinstance(el, Tag) and el.name == "h2":
            out.append((clean(el.get_text(" ")), []))
        elif out and isinstance(el, Tag):
            for item in el.find_all(["li", "p"]) if el.name != "p" else [el]:
                text = clean(item.get_text(" "))
                if text:
                    out[-1][1].append((item.name, text))
    return out


def applicant_lines(lines: list[tuple[str, str]]) -> list[str]:
    """The lines of one who-may-apply section that name applicants (see APPLICANT_MARKER_RE). The first
    line is the applicant statement whatever it says ("Maryland homeowners, builders, developers, or
    investors who meet the following criteria:"); list items at the top are introduced by the heading.
    These sections state the applicant, then list conditions, then define terms, so the scan stops at
    the first condition lead-in ("businesses that:"): what follows is about the conditions, not the
    applicant ("AND local government approval (municipality or county resolution/letter)")."""
    out: list[str] = []
    listing = True
    for i, (tag, text) in enumerate(lines):
        negated = bool(NEGATION_RE.search(text))
        marked = i == 0 or bool(APPLICANT_MARKER_RE.search(text))
        if tag == "p":
            if marked and not negated:
                out.append(text)
            if text.endswith(":") and CONDITION_LEAD_IN_RE.search(text):
                break
            listing = marked and not negated and text.endswith(":")
        elif listing and not negated:
            out.append(text)
    return out


def parse_box(main_html: str) -> list[tuple[str, str]]:
    """(label, value) per bullet of the platform summary box, labels lowercased without the colon.
    Unlabeled bullets get label ''. No box -> []."""
    soup = BeautifulSoup(main_html, "html.parser")
    box = soup.select_one(".maryland-summary-box")
    if box is None:
        return []
    lines: list[tuple[str, str]] = []
    for li in box.select("li"):
        strong = li.find("strong")
        if strong is not None:
            label = clean(strong.get_text(" ")).rstrip(":").strip().lower()
            strong.extract()
        else:
            label = ""
        value = clean(li.get_text(" ")).lstrip(":").strip()
        if label or value:
            lines.append((label, value))
    return lines


def box_heading(main_html: str) -> str | None:
    soup = BeautifulSoup(main_html, "html.parser")
    h = soup.select_one(".maryland-summary-box__heading")
    return clean(h.get_text(" ")) or None if h else None


_sentence_re = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“(])")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _sentence_re.split(clean(text)) if s.strip()]


def applicant_types_for(applicant_text: str | list[str] | None) -> list[ApplicantTag]:
    """Keyword tags over applicant lines. The first match of each phrase that is not in a location
    context wins; the matched phrase is the tag's source_code."""
    lines = [applicant_text] if isinstance(applicant_text, str) else list(applicant_text or [])
    tags: list[ApplicantTag] = []
    for pattern, values in APPLICANT_KEYWORDS:
        phrase = next(
            (m.group(0).lower() for line in lines for m in re.finditer(pattern, line, re.I)
             if not LOCATION_CONTEXT_RE.search(line[max(0, m.start() - 60):m.start()])),
            None,
        )
        if phrase:
            tags += [ApplicantTag(value=v, source_code=phrase) for v in values]
    return tags


def match_required_for(text: str) -> bool | None:
    if MATCH_NOT_REQUIRED_RE.search(text):
        return False
    if MATCH_REQUIRED_RE.search(text):
        return True
    return None


def funding_type_for(name: str) -> str | None:
    n = name.lower()
    for keyword, ft in FUNDING_TYPE_KEYWORDS:
        if keyword in n:
            return ft
    return None


# ---------- the base ----------

class MarylandDrupalConnector:
    CONNECTOR: str
    BASE: str
    AGENCY: str
    AGENCY_CODE: str
    SKIP_PATH: re.Pattern[str] | None = None       # sitemap paths never fetched
    KEEP_PATH: re.Pattern[str] | None = None       # if set, only these sitemap paths are fetched
    SECTION_CATEGORIES: dict[str, tuple[str, ...]] = {}   # first URL segment -> categories; else ("other",)
    CATEGORY_CODE: str | None = None               # source_code for categories; default: the URL segment
    PASS_THROUGH: dict[str, list[str]] = {}        # source_id -> ALNs for federal pass-throughs
    ELIGIBILITY_HEADING_RE: re.Pattern[str] = ELIGIBILITY_HEADING_RE # sections kept verbatim as eligibility_text
    APPLICANT_HEADING_RE: re.Pattern[str] = ELIGIBILITY_HEADING_RE   # sections scanned for applicant keywords
    THING_HEADING_RE: re.Pattern[str] | None = None                 # ... minus these (things, not people)

    # -- HTTP --

    @property
    def sitemap_url(self) -> str:
        return self.BASE + "/sitemap.xml"

    def client(self) -> httpx.Client:
        return httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT})

    def iter_sitemap(self, xml_text: str) -> list[tuple[str, str | None]]:
        """(url, lastmod) for every sitemap entry that could be a program page. Pure; tested on a fixture."""
        root = ET.fromstring(xml_text)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        out: list[tuple[str, str | None]] = []
        for url in root.findall("s:url", ns):
            loc = (url.findtext("s:loc", default="", namespaces=ns) or "").strip()
            if not loc.startswith(self.BASE):
                continue
            path = urlparse(loc).path
            if path in ("", "/"):
                continue
            if self.SKIP_PATH is not None and self.SKIP_PATH.search(path):
                continue
            if self.KEEP_PATH is not None and not self.KEEP_PATH.search(path):
                continue
            lastmod = (url.findtext("s:lastmod", default="", namespaces=ns) or "").strip() or None
            out.append((loc, lastmod))
        return out

    def before_fetch(self, client: httpx.Client) -> dict[str, Any]:
        """Site-level context fetched once per run (e.g. an index of open programs). Default: nothing."""
        return {}

    def annotate(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Stamp site-level context onto a page payload, fresh or reused. Default: unchanged."""
        return payload

    def fetch(self, limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
        """`prior` maps source_id -> the payload stored in raw_record on the previous run. Only record pages
        are returned; `limit` caps records, not pages walked."""
        prior = prior or {}
        out: list[RawRecord] = []
        with self.client() as client:
            context = self.before_fetch(client)
            r = client.get(self.sitemap_url)
            r.raise_for_status()
            for url, lastmod in self.iter_sitemap(r.text):
                sid = source_id_for(url)
                previous = prior.get(sid)
                if needs_fetch(lastmod, previous):
                    resp = client.get(url)
                    time.sleep(PAGE_DELAY_S)
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    payload = page_payload(url, lastmod, resp.text)
                else:
                    payload = previous
                if payload is None:
                    continue
                payload = self.annotate(payload, context)
                if not self.is_record(payload):
                    continue
                out.append(RawRecord(source_connector=self.CONNECTOR, source_id=sid, payload=payload))
                if limit and len(out) >= limit:
                    break
        return out

    def resolve_missing(self, source_id: str) -> dict[str, Any] | None:
        """A page that dropped out of the sitemap. Still there as a record: report what it says. Gone, or
        no longer a record: 'unknown' (a vanished page is not evidence that a program closed). Network
        error: None (caller marks unknown)."""
        url = f"{self.BASE}/{source_id}"
        try:
            with self.client() as client:
                context = self.before_fetch(client)
                resp = client.get(url)
        except Exception:  # noqa: BLE001
            return None
        if resp.status_code == 404:
            return {"status": "unknown"}
        try:
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        payload = page_payload(url, None, resp.text)
        return self.classify_page(self.annotate(payload, context) if payload else None)

    def classify_page(self, payload: dict[str, Any] | None, today: date | None = None) -> dict[str, Any]:
        if not payload or not self.is_record(payload):
            return {"status": "unknown"}
        fields = self.status_fields(payload, body_sections(payload.get("main_html") or ""), today or date.today())
        return {"status": fields["status"], "closes_at": fields.get("closes_at")}

    # -- hooks --

    def is_record(self, payload: dict[str, Any]) -> bool:
        raise NotImplementedError

    def status_fields(self, payload: dict[str, Any], sections: list[tuple[str, str]], today: date) -> dict[str, Any]:
        """status, opens_at, closes_at, closes_at_text, rolling. Missing keys mean null."""
        raise NotImplementedError

    def amounts(self, sections: list[tuple[str, str]]) -> tuple[int | None, int | None]:
        return None, None

    def match_text(self, sections: list[tuple[str, str]]) -> str:
        """Where the match wording is looked for. Default: the whole body."""
        return " ".join(text for _, text in sections)

    def match_required_for(self, text: str) -> bool | None:
        return match_required_for(text)

    # -- shared mapping --

    def eligibility_text_for(self, sections: list[tuple[str, str]]) -> str | None:
        texts = [text for heading, text in sections if self.ELIGIBILITY_HEADING_RE.search(heading) and text]
        return "\n\n".join(texts) or None

    def is_applicant_heading(self, heading: str) -> bool:
        """A who-may-apply heading: matches APPLICANT_HEADING_RE, is not about things, is not negated
        ("Who is not eligible to apply?", "Ineligible projects")."""
        return (bool(self.APPLICANT_HEADING_RE.search(heading))
                and not (self.THING_HEADING_RE is not None and self.THING_HEADING_RE.search(heading))
                and not NEGATION_RE.search(heading) and "ineligible" not in heading.lower())

    def applicant_text(self, main_html: str) -> list[str]:
        """The applicant-naming lines of the who-may-apply sections, each preceded by its heading
        ("Household eligibility requirements" names the applicant by itself). Never the whole page."""
        return [
            line
            for heading, lines in section_lines_by_heading(main_html)
            if self.is_applicant_heading(heading)
            for line in [heading, *applicant_lines(lines)]
        ]

    def categories_for(self, source_id: str) -> list[CategoryTag]:
        section = source_id.split("/", 1)[0]
        code = self.CATEGORY_CODE if self.CATEGORY_CODE is not None else section
        return [CategoryTag(value=c, source_code=code) for c in self.SECTION_CATEGORIES.get(section, ("other",))]

    def funding_type_for(self, name: str, source_id: str) -> str | None:
        return funding_type_for(name)

    def normalize(self, raw: RawRecord, today: date | None = None) -> Program:
        payload = raw.payload
        main_html: str = payload.get("main_html") or ""
        url: str = payload.get("url") or f"{self.BASE}/{raw.source_id}"
        sections = body_sections(main_html)
        name = page_name(main_html)
        alns = self.PASS_THROUGH.get(raw.source_id)
        status = self.status_fields(payload, sections, today or date.today())
        amount_min, amount_max = self.amounts(sections)

        return Program(
            source_connector=self.CONNECTOR,
            source_id=raw.source_id,
            source_url=url,
            external_number=None,
            name=name,
            level="state",
            jurisdiction="MD",
            administering_agency=self.AGENCY,
            agency_code=self.AGENCY_CODE,
            funding_type=self.funding_type_for(name, raw.source_id),
            funding_source="pass_through" if alns is not None else "direct",
            amount_min=amount_min,
            amount_max=amount_max,
            match_required=self.match_required_for(self.match_text(sections)),
            match_pct=None,
            status=status["status"],
            opens_at=status.get("opens_at"),
            closes_at=status.get("closes_at"),
            closes_at_text=status.get("closes_at_text"),
            rolling=status.get("rolling"),
            summary=clean(payload.get("description")) or None,
            eligibility_text=self.eligibility_text_for(sections),
            eligibility_structured=None,
            applicant_types=applicant_types_for(self.applicant_text(main_html)),
            categories=self.categories_for(raw.source_id),
            alns=alns or [],
        )
