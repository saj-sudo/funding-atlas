"""Shared base for Maryland agencies on SharePoint with the state's `mdgov` theme (MEA, DNR; MDEM, MDOT and MDE
run on it too and are not connected yet).

Every one of these sites has the same skeleton, verified page by page on 2026-10-16 (see
docs/connectors/maryland_sharepoint.md): no sitemap; a hand-curated index page (or several) linking the programs;
a `<main id="mdgovMain">` whose first `<section class="mdgov-section">` holds the `<h1>` in an edit-mode panel and
the page body in one rich-text div; `<meta name="description">` on every page. What they do not have is a usable
change signal: the CDN stamps one `Last-Modified` on every page and Cloudflare rewrites the obfuscated e-mail
markup per response, so the payload carries a sha256 of the cleaned text and every page is fetched every run.

What differs per agency lives in a subclass: how the index is read, how status and dates are read from the
page (MEA: labeled lines; DNR: prose), which sentences name the applicants, and the categories.

Subclass contract:
  class attributes  CONNECTOR, BASE, AGENCY, AGENCY_CODE, and optionally PASS_THROUGH
  index_entries(client) -> {source_id: {url, ...facts}}   enumerate; raise if an index page does not load
  annotate(payload, entry)                                 default: every entry key but url is stamped on the payload
  is_record(payload)                                       default: the page has an mdgov body
  name_for(payload)                                        default: the H1, else the <title>
  status_fields(payload, today)                            -> {status, opens_at, closes_at, closes_at_text, rolling}
  applicant_lines(payload)                                 lines scanned for applicant keywords; also the eligibility_text
  categories_for(payload) / funding_type_for(name, payload)

Each connector module binds one instance to module-level fetch / normalize / resolve_missing, so the pipeline
contract (`connectors/<name>.py` exposing those three) is unchanged.
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

# mdgov theme: the page body is one rich-text div inside the first <section class="mdgov-section">; the <h1> sits
# in an edit-mode panel next to it.
BODY_SELECTOR = "#ctl00_PlaceHolderMain_RichHtmlField1__ControlWrapper_RichHtmlField"
H1_SELECTOR = "#ctl00_PlaceHolderMain_editmodepanel2 h1"
LEAF_BLOCKS = ("p", "div", "li", "td", "th", "h2", "h3", "h4", "h5", "h6")

MONTH = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
         r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)")
DATE_RE = re.compile(rf"\b({MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b")


# ---------- pure helpers (no I/O) ----------

def source_id_for(url: str) -> str:
    """Lowercased path without the leading slash or fragment; percent-escapes kept as linked. SharePoint paths
    are case-insensitive and the indexes link the same page in mixed case."""
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


# ---------- the base ----------

class MarylandSharePointConnector:
    CONNECTOR: str
    BASE: str
    AGENCY: str
    AGENCY_CODE: str
    PASS_THROUGH: dict[str, list[str]] = {}        # source_id -> ALNs for federal pass-throughs

    # -- HTTP --

    def client(self) -> httpx.Client:
        return httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT})

    def index_entries(self, client: httpx.Client) -> dict[str, dict[str, Any]]:
        """source_id -> {url, ...facts} for every program page the agency's index links. An index that does not
        load raises and aborts the run: without it every program it lists would be marked missing."""
        raise NotImplementedError

    def annotate(self, payload: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
        """Stamp the index facts onto the page payload, so a change in the index changes the record."""
        return {**payload, **{k: v for k, v in entry.items() if k != "url"}}

    def fetch(self, limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
        """Every page the index links is fetched every run (`prior` is unused: no usable Last-Modified or ETag).
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
                payload = self.annotate(payload, entry)
                if not self.is_record(payload):
                    continue
                out.append(RawRecord(source_connector=self.CONNECTOR, source_id=sid, payload=payload))
                if limit and len(out) >= limit:
                    break
        return out

    def resolve_missing(self, source_id: str) -> dict[str, Any] | None:
        """A page the index no longer links. Still there: report what it says (de-listing is enumeration, not a
        status). Gone: unknown. Network error: None (the caller marks unknown)."""
        url = f"{self.BASE}/{source_id}"
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
        return self.classify_page(page_payload(url, resp.text))

    def classify_page(self, payload: dict[str, Any] | None, today: date | None = None) -> dict[str, Any]:
        if not payload or not self.is_record(payload):
            return {"status": "unknown"}
        fields = self.status_fields(payload, today or date.today())
        return {"status": fields["status"], "closes_at": fields.get("closes_at")}

    # -- hooks --

    def is_record(self, payload: dict[str, Any]) -> bool:
        return bool(payload.get("main_html"))

    def name_for(self, payload: dict[str, Any]) -> str:
        return page_h1(payload.get("main_html") or "") or clean(payload.get("title"))

    def status_fields(self, payload: dict[str, Any], today: date) -> dict[str, Any]:
        """status, opens_at, closes_at, closes_at_text, rolling. Missing keys mean null."""
        raise NotImplementedError

    def applicant_lines(self, payload: dict[str, Any]) -> list[str]:
        """The lines that name who may apply: scanned for applicant keywords and kept as eligibility_text."""
        return []

    def categories_for(self, payload: dict[str, Any]) -> list[CategoryTag]:
        return [CategoryTag(value="other", source_code=self.CONNECTOR)]

    def funding_type_for(self, name: str, payload: dict[str, Any]) -> str | None:
        return funding_type_for(name)

    # -- shared mapping --

    def normalize(self, raw: RawRecord, today: date | None = None) -> Program:
        payload = raw.payload
        main_html: str = payload.get("main_html") or ""
        url: str = payload.get("url") or f"{self.BASE}/{raw.source_id}"
        name = self.name_for(payload)
        status = self.status_fields(payload, today or date.today())
        lines = self.applicant_lines(payload)
        alns = self.PASS_THROUGH.get(raw.source_id)

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
            funding_type=self.funding_type_for(name, payload),
            funding_source="pass_through" if alns is not None else "direct",
            amount_min=None,
            amount_max=None,
            match_required=match_required_for(" ".join(page_sentences(main_html))),
            match_pct=None,
            status=status["status"],
            opens_at=status.get("opens_at"),
            closes_at=status.get("closes_at"),
            closes_at_text=status.get("closes_at_text"),
            rolling=status.get("rolling"),
            summary=clean(payload.get("description")) or None,
            eligibility_text="\n\n".join(lines) or None,
            eligibility_structured=None,
            applicant_types=applicant_types_for(lines),
            categories=self.categories_for(payload),
            alns=alns or [],
        )
