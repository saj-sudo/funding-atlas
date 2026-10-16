"""Maryland Energy Administration connector: energy grants, rebates, loans and one tax credit.

Source: https://energy.maryland.gov (SharePoint, the state's `mdgov` theme; no sitemap, robots.txt allows
`/Pages/`). There is no single linked index: `/Pages/all-incentives.aspx` lists the FY27 programs in sector tables
whose rows are unlinked. The five category pages (Renewables, Energy Efficiency, Transportation, Resiliency,
Communities) each link their programs as a table of `<a>` title + description under `<h3>` headings ("Grants",
"Rebates", "Tax Credits", "Archived Programs"); the union is 34 paths, 7 of them 404 on 2026-10-16 (every archived
program and one rebate). The union is the enumeration; which indexes list a page, and under which heading, is
stamped onto its payload.

Program pages are prose with labeled lines, bold label then colon then value, in one leaf block or split over two:

    Online Application Portal Status: Open to new applications
    Application Deadline: 3:00 PM ET, November 18, 2026 through the JotForm application portal.
    Program Launch Date: September 9, 2026          (or: Funding Opportunity Announcement Issue Date)
    Target Audience: Maryland counties, cities, towns, and other Authorities Having Jurisdiction (AHJs) ...
    Anticipated Program Budget: MEA anticipates up to $3,800,000 ...   (a pot, never an award size)

Older pages say it in prose instead: "The Local Government Energy Modernization Program (L-GEM) is CLOSED",
"Now Open! FY27 Commercial & Community Buildings Grant Program", "FY26 PROGRAM NOW ACCEPTING APPLICATIONS".
Status is read in that order (first status line; else closed prose, which beats open prose; else open prose), then
a stated launch date in the future turns a closed or undecided page into `forecasted`, and a page that states only
a deadline is `open` while the deadline is ahead and `unknown` once it has passed. Everything else is `unknown`.

Change signal: the CDN stamps every page with the same `Last-Modified` and Cloudflare rewrites the obfuscated
e-mail markup on every response, so the payload carries a sha256 of the cleaned main-content text, and every page
is fetched every run (`prior` is accepted and ignored; about 40 requests). See docs/connectors/md_mea.md.
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import date
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from connectors.grants_gov import parse_date
from connectors.maryland_drupal import (
    NEGATION_RE,
    PAGE_DELAY_S,
    TIMEOUT_S,
    USER_AGENT,
    applicant_types_for,
    clean,
    funding_type_for,
    match_required_for,
    sentences,
)
from pipeline.models import CategoryTag, Program, RawRecord

CONNECTOR = "md_mea"
BASE = "https://energy.maryland.gov"
AGENCY = "Maryland Energy Administration"
AGENCY_CODE = "MD-MEA"

# The hand-curated category indexes, as lowercase paths (SharePoint paths are case-insensitive and the indexes
# link the same pages in mixed case).
INDEX_PATHS: tuple[str, ...] = (
    "pages/renewables.aspx",
    "pages/energyefficiency.aspx",
    "transportation/pages/incentives.aspx",
    "pages/resiliency.aspx",
    "pages/communities.aspx",
)
# Linked from the indexes but not programs: the news page, the EmPOWER fact page, the home page.
SKIP_PATH = re.compile(r"^pages/(?:news|default|all-incentives|facts/)", re.I)
ARCHIVED_RE = re.compile(r"archived", re.I)

# The SolarAPP+ page says the money is U.S. Department of Energy State Energy Program funding; 81.041 verified on
# SAM.gov 2026-10-16. Maryland RISE says "federally-funded" without naming the program: direct until it does.
PASS_THROUGH: dict[str, list[str]] = {
    "govt/pages/solarapp.aspx": ["81.041"],
}

# mdgov theme: the page body is one rich-text div inside the first <section class="mdgov-section">; the <h1>
# sits in an edit-mode panel next to it. Verified on all 27 live program pages and the 5 indexes.
BODY_SELECTOR = "#ctl00_PlaceHolderMain_RichHtmlField1__ControlWrapper_RichHtmlField"
H1_SELECTOR = "#ctl00_PlaceHolderMain_editmodepanel2 h1"
LEAF_BLOCKS = ("p", "div", "li", "td", "th", "h2", "h3", "h4", "h5", "h6")

# Labeled lines: `<strong>Label:</strong> value` in one leaf block, or the value in the next leaf block. Labels
# are lowercased with a leading fiscal-year prefix ("FY27 ") stripped before matching.
LABEL_RE = re.compile(r"^([A-Za-z][^:]{2,70}?)\s*:\s*(.*)$", re.S)
FY_PREFIX_RE = re.compile(r"^fy\s?\d{2,4}\s+", re.I)
LABEL_KINDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("status", re.compile(r"^(?:online )?(?:application |program )?(?:portal )?status$")),
    ("deadline", re.compile(r"^(?:program |anticipated )?(?:program )?application deadline$|^deadline$")),
    ("launch", re.compile(r"^(?:program |estimated |anticipated )?launch date$"
                          r"|^funding opportunity announcement issue date$")),
    ("audience", re.compile(r"^(?:target )?audience$|^eligible (?:entity types|applicants|entities)(?: are| include)?$")),
    ("program_type", re.compile(r"^(?:program type|type of (?:grant )?program)$")),
)

CLOSED_VALUE_RE = re.compile(r"\b(?:closed|inactive)\b", re.I)
OPEN_VALUE_RE = re.compile(r"\bopen\b", re.I)
CLOSED_RE = re.compile(
    r"\bis (?:now )?(?:closed|inactive)\b|\bare (?:now )?closed\b|\bnow closed\b|closed to new applications"
    r"|no longer accepting|program is closed",
    re.I,
)
DEPLETED_RE = re.compile(r"deplet|exhaust|fully (?:reserved|awarded|expended|subscribed)", re.I)
OPEN_RE = re.compile(r"\bnow open\b|\bis (?:currently )?open\b|\bnow accepting\b|accepting applications|remains open", re.I)
ROLLING_RE = re.compile(r"ongoing|remains open|until (?:funding|funds)|first-come|rolling", re.I)
MONTH = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
         r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)")
DATE_RE = re.compile(rf"\b({MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b")
OPENS_RE = re.compile(rf"\b(?:opens|will open|launch(?:es)?)\b[^.]{{0,40}}?({MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})", re.I)
APPLICANT_SENTENCE_RE = re.compile(
    r"\bmay apply\b|\beligible (?:applicants?|entit\w*|to apply)\b|\b(?:is|are) open to\b|\bavailable to\b", re.I
)
BUDGET_RE = re.compile(r"budget", re.I)


# ---------- pure helpers (no I/O) ----------

def source_id_for(url: str) -> str:
    """Lowercased path without the leading slash or fragment; percent-escapes kept as linked."""
    return urlparse(urldefrag(url)[0]).path.strip("/").lower()


def canonical_url(href: str, page_url: str) -> str:
    """Absolute https URL without fragment."""
    url = urldefrag(urljoin(page_url, href))[0]
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url


def fixture_name(source_id: str) -> str:
    """`govt/pages/solarapp.aspx` -> `govt__pages__solarapp`: reversible, unique, filesystem-safe."""
    return re.sub(r"[^a-z0-9_.-]+", "-", source_id.replace("/", "__").removesuffix(".aspx"))


def main_section(html_text: str) -> Tag | None:
    """The first mdgov section (H1 panel + rich-text body), or the body div alone, or None for a non-page."""
    soup = BeautifulSoup(html_text, "html.parser")
    body = soup.select_one(BODY_SELECTOR)
    if body is None:
        return None
    return body.find_parent("section") or body


def body_div(main_html: str) -> Tag | None:
    soup = BeautifulSoup(main_html, "html.parser")
    return soup.select_one(BODY_SELECTOR) or soup


def text_hash(main_html: str) -> str:
    """sha256 of the cleaned text, never of the markup (Cloudflare rewrites `data-cfemail` per response)."""
    text = clean(BeautifulSoup(main_html, "html.parser").get_text(" "))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def page_payload(url: str, html_text: str) -> dict[str, Any] | None:
    """The raw_record payload for one page, or None if the page has no mdgov body."""
    section = main_section(html_text)
    if section is None:
        return None
    soup = BeautifulSoup(html_text, "html.parser")
    desc = soup.find("meta", attrs={"name": "description"})
    main_html = str(section)
    return {
        "url": url,
        "title": clean(soup.title.get_text(" ")) if soup.title else None,
        "description": desc.get("content") if isinstance(desc, Tag) else None,
        "main_html": main_html,
        "content_hash": text_hash(main_html),
    }


def page_h1(main_html: str) -> str:
    soup = BeautifulSoup(main_html, "html.parser")
    h1 = soup.select_one(H1_SELECTOR) or soup.find("h1")
    return clean(h1.get_text(" ")) if h1 else ""


def _own_text(el: Tag) -> str:
    """The text of a block minus its nested blocks (SharePoint's editor nests a <div> per paragraph, so a
    label and its value often sit in the text a <div> has before its first child <div>)."""
    parts: list[str] = []
    for child in el.children:
        if isinstance(child, Tag) and child.name in LEAF_BLOCKS:
            continue
        parts.append(child.get_text(" ") if isinstance(child, Tag) else str(child))
    return clean(" ".join(parts))


def leaf_lines(main_html: str) -> list[str]:
    """Cleaned text of every block of the body in document order, each block contributing only the text that
    is not inside a nested block."""
    body = body_div(main_html)
    out: list[str] = []
    for el in body.find_all(LEAF_BLOCKS) if body else []:
        text = _own_text(el)
        if text:
            out.append(text)
    return out


def page_sentences(main_html: str) -> list[str]:
    """Sentences per block, so a label line and the paragraph after it never fuse into one sentence."""
    return [s for line in leaf_lines(main_html) for s in sentences(line)]


def label_kind(label: str) -> str | None:
    key = FY_PREFIX_RE.sub("", label.strip().lower())
    key = re.sub(r"\s+", " ", key)
    for kind, pattern in LABEL_KINDS:
        if pattern.match(key):
            return kind
    return None


def labeled_lines(main_html: str) -> list[tuple[str, str, str]]:
    """(kind, label, value) for every leaf line of the form `Label: value` whose label is one of LABEL_KINDS,
    in page order. An empty value takes the next leaf line unless that line is itself a known label."""
    lines = leaf_lines(main_html)
    out: list[tuple[str, str, str]] = []
    for i, text in enumerate(lines):
        m = LABEL_RE.match(text)
        if not m:
            continue
        kind = label_kind(m.group(1))
        if kind is None:
            continue
        value = clean(m.group(2))
        if not value and i + 1 < len(lines):
            nxt = LABEL_RE.match(lines[i + 1])
            if not (nxt and label_kind(nxt.group(1))):
                value = lines[i + 1]
        out.append((kind, clean(m.group(1)), value))
    return out


def first_value(lines: list[tuple[str, str, str]], kind: str) -> str | None:
    return next((value for k, _, value in lines if k == kind and value), None)


def parse_text_date(value: str | None) -> date | None:
    """First `Month D, YYYY` anywhere in the first sentence of the value (times, weekdays and ordinals around it
    are ignored); None when the sentence has no full date ("Wednesday, November 19th at 5PM")."""
    if not value:
        return None
    value = re.sub(r"\b([AaPp])\.[Mm]\.", r"\1M", value)        # "3:00 P.M. ET, Monday, ..." is one sentence
    first = sentences(value)[0] if sentences(value) else value
    m = DATE_RE.search(first)
    if not m:
        return None
    return parse_date(f"{m.group(1).rstrip('.')} {int(m.group(2))}, {m.group(3)}")


def status_from_lines(lines: list[tuple[str, str, str]]) -> str | None:
    """The first status line decides: closed/inactive wording -> closed, open wording -> open, else undecided."""
    value = first_value(lines, "status")
    if not value:
        return None
    if CLOSED_VALUE_RE.search(value):
        return "closed"
    if OPEN_VALUE_RE.search(value):
        return "open"
    return None


def status_from_prose(sents: list[str]) -> str | None:
    """Closed wording beats open wording; a closed sentence that blames funding is `exhausted`."""
    for s in sents:
        if CLOSED_RE.search(s):
            return "exhausted" if DEPLETED_RE.search(s) else "closed"
    for s in sents:
        if OPEN_RE.search(s):
            return "open"
    return None


def status_fields_for(main_html: str, index: dict[str, str], today: date) -> dict[str, Any]:
    lines = labeled_lines(main_html)
    sents = page_sentences(main_html)
    archived_only = bool(index) and all(ARCHIVED_RE.search(h or "") for h in index.values())

    status = "closed" if archived_only else None
    if status is None:
        status = status_from_lines(lines)
    if status is None:
        status = status_from_prose(sents)

    deadline = first_value(lines, "deadline")
    closes_at = parse_text_date(deadline)
    launch = first_value(lines, "launch")
    opens_at = parse_text_date(launch)
    if opens_at is None and not launch:
        m = next((m for s in sents for m in [OPENS_RE.search(s)] if m), None)
        opens_at = parse_text_date(m.group(1)) if m else None

    if status in (None, "closed") and opens_at and opens_at > today:
        status = "forecasted"
    if status is None and closes_at:
        status = "open" if closes_at >= today else "unknown"
    if status is None:
        status = "unknown"

    timing = [f"{label}: {value}" for kind, label, value in lines if kind in ("status", "deadline", "launch")]
    return {
        "status": status,
        "opens_at": opens_at,
        "closes_at": closes_at,
        "closes_at_text": "; ".join(timing) or None,
        "rolling": True if status == "open" and deadline and ROLLING_RE.search(deadline) else None,
    }


def applicant_lines_for(main_html: str) -> list[str]:
    """The audience lines plus the body sentences that say who may apply, minus negated ones."""
    lines = labeled_lines(main_html)
    out = [f"{label}: {value}" for kind, label, value in lines if kind == "audience" and value]
    for s in page_sentences(main_html):
        if APPLICANT_SENTENCE_RE.search(s) and not NEGATION_RE.search(s) and s not in out:
            out.append(s)
    return out


def funding_type_for_page(name: str, main_html: str) -> str | None:
    if "rebate" in name.lower():
        return "rebate"
    ft = funding_type_for(name)
    if ft:
        return ft
    lines = labeled_lines(main_html)
    for kind, label, value in lines:
        if kind != "program_type":
            continue
        pt = f"{label} {value}".lower()
        for keyword, kind_ft in (("rebate", "rebate"), ("tax credit", "tax_credit"), ("loan", "loan"),
                                 ("grant", "grant"), ("challenge", "other"), ("prize", "other"), ("auction", "other")):
            if keyword in pt:
                return kind_ft
    return None


def program_name(main_html: str, title: str | None) -> str:
    name = page_h1(main_html) or clean(title)
    return FY_PREFIX_RE.sub("", name).strip() or name


def index_links(index_url: str, html_text: str) -> dict[str, dict[str, Any]]:
    """source_id -> {url, heading} for every on-site .aspx link in the body of one index page, with the text of
    the nearest preceding heading ("Grants", "Archived Programs", or '' before the first heading)."""
    section = main_section(html_text)
    if section is None:
        return {}
    body = section.select_one(BODY_SELECTOR) or section
    host = urlparse(BASE).netloc
    out: dict[str, dict[str, Any]] = {}
    heading = ""
    for el in body.descendants:
        if not isinstance(el, Tag):
            continue
        if el.name in ("h2", "h3", "h4"):
            text = clean(el.get_text(" "))
            if text:
                heading = text
        elif el.name == "a" and el.get("href"):
            url = canonical_url(el["href"], index_url)
            parsed = urlparse(url)
            if parsed.netloc.lower().removeprefix("www.") != host or not parsed.path.lower().endswith(".aspx"):
                continue
            sid = source_id_for(url)
            if not sid or sid in INDEX_PATHS or SKIP_PATH.search(sid):
                continue
            out.setdefault(sid, {"url": url, "heading": heading})
    return out


# ---------- the connector ----------

class Mea:
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE

    def client(self) -> httpx.Client:
        return httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT})

    def index_entries(self, client: httpx.Client) -> dict[str, dict[str, Any]]:
        """source_id -> {url, index: {index_path: heading}} across the five indexes. An index that does not
        load aborts the run: without it every program it lists would be marked missing."""
        entries: dict[str, dict[str, Any]] = {}
        for path in INDEX_PATHS:
            url = f"{BASE}/{path}"
            resp = client.get(url)
            resp.raise_for_status()
            time.sleep(PAGE_DELAY_S)
            for sid, link in index_links(url, resp.text).items():
                entry = entries.setdefault(sid, {"url": link["url"], "index": {}})
                entry["index"][path] = link["heading"]
        return entries

    def fetch(self, limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
        """Every page the indexes link is fetched every run (`prior` is unused: no usable Last-Modified or ETag).
        A 404 on an index link is skipped (dead links are a fact of these indexes); other errors raise."""
        out: list[RawRecord] = []
        with self.client() as client:
            for sid, entry in sorted(self.index_entries(client).items()):
                resp = client.get(entry["url"])
                time.sleep(PAGE_DELAY_S)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                payload = page_payload(entry["url"], resp.text)
                if payload is None:
                    continue
                payload["index"] = entry["index"]
                out.append(RawRecord(source_connector=CONNECTOR, source_id=sid, payload=payload))
                if limit and len(out) >= limit:
                    break
        return out

    def resolve_missing(self, source_id: str) -> dict[str, Any] | None:
        """A page no index links any more. Still there: report what it says (de-listing is enumeration, not a
        status). Gone: unknown. Network error: None (the caller marks unknown)."""
        url = f"{BASE}/{source_id}"
        try:
            with self.client() as client:
                resp = client.get(url)
        except Exception:  # noqa: BLE001
            return None
        if resp.status_code == 404:
            return {"status": "unknown"}
        try:
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        payload = page_payload(url, resp.text)
        return self.classify_page(payload)

    def classify_page(self, payload: dict[str, Any] | None, today: date | None = None) -> dict[str, Any]:
        if not payload or not payload.get("main_html"):
            return {"status": "unknown"}
        fields = status_fields_for(payload["main_html"], payload.get("index") or {}, today or date.today())
        return {"status": fields["status"], "closes_at": fields.get("closes_at")}

    def categories_for(self, index: dict[str, str]) -> list[CategoryTag]:
        tags = [CategoryTag(value="energy", source_code="mea")]
        if any(path.startswith("transportation/") for path in index):
            tags.append(CategoryTag(value="transportation", source_code="transportation/pages/incentives.aspx"))
        return tags

    def normalize(self, raw: RawRecord, today: date | None = None) -> Program:
        payload = raw.payload
        main_html: str = payload.get("main_html") or ""
        index: dict[str, str] = payload.get("index") or {}
        url: str = payload.get("url") or f"{BASE}/{raw.source_id}"
        name = program_name(main_html, payload.get("title"))
        status = status_fields_for(main_html, index, today or date.today())
        applicant_lines = applicant_lines_for(main_html)
        text = " ".join(page_sentences(main_html))
        alns = PASS_THROUGH.get(raw.source_id)

        return Program(
            source_connector=CONNECTOR,
            source_id=raw.source_id,
            source_url=url,
            external_number=None,
            name=name,
            level="state",
            jurisdiction="MD",
            administering_agency=AGENCY,
            agency_code=AGENCY_CODE,
            funding_type=funding_type_for_page(name, main_html),
            funding_source="pass_through" if alns is not None else "direct",
            amount_min=None,
            amount_max=None,
            match_required=match_required_for(text),
            match_pct=None,
            status=status["status"],
            opens_at=status.get("opens_at"),
            closes_at=status.get("closes_at"),
            closes_at_text=status.get("closes_at_text"),
            rolling=status.get("rolling"),
            summary=clean(payload.get("description")) or None,
            eligibility_text="\n\n".join(applicant_lines) or None,
            eligibility_structured=None,
            applicant_types=applicant_types_for(applicant_lines),
            categories=self.categories_for(index),
            alns=alns or [],
        )


SITE = Mea()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
classify_page = SITE.classify_page
