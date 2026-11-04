"""Business Oregon connector: every program the agency lists on its Programs page, about a hundred.

Source: https://www.oregon.gov/biz/programs/ (SharePoint). The page carries two views of one list, alphabetical
(`#programAlpha`) and by topic (`#programTopic`, eight `h2`s); the union is the index, the topic view gives the
category. Each program is a SharePoint page of the same shape: a short intro field, a sidebar field ("Additional
Resources", never read) and a body field with the agency's own headings ("Who is Eligible?", "How Does Funding
Work?", "What is the Application Process?"). Status from the body's round sentence by the hand-list default table
(accepting -> open, year-round -> rolling, not accepting or closed -> closed, else unknown with the cycle sentence
kept); applicants from the "Who is Eligible?" passage and the applicant sentences. One GET per program a run. See
docs/connectors/or_biz.md.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import Tag

from connectors.hand_list import (
    DELAY_S,
    Blocks,
    HandListConnector,
    applicant_tags,
    first_p,
    first_sentence,
    label_lines,
    own_text,
    resolve_missing,  # noqa: F401  (the pipeline reads it from this module)
)
from connectors.hand_list import client as _client
from connectors.hand_list import get as _get
from connectors.hand_list import soup as _soup
from connectors.sam_assistance_listings import clean
from connectors.text import funding_type_for, portal_categories
from pipeline.models import CategoryTag, RawRecord

CONNECTOR = "or_biz"
BASE = "https://www.oregon.gov"
INDEX_URL = BASE + "/biz/programs/"
AGENCY = "Business Oregon (Oregon Business Development Department)"
AGENCY_CODE = "OR-BIZ"
JURISDICTION = "OR"
BODY_SUFFIX = "RichHtmlField1__ControlWrapper_OregonRichHtmlField"    # the body field; 11 is the intro, 12 the sidebar
INTRO_SUFFIX = "RichHtmlField11__ControlWrapper_OregonRichHtmlField"

LABEL_RE = re.compile(r"who is eligible|eligible applicants|^eligibility", re.I)
APPLICANT_RE = re.compile(r"\b(?:eligible applicants?|may apply|are eligible|eligible to apply|is available to|open to)\b", re.I)
# A sentence that states a cycle without saying open or closed (CDBG's two windows a year, a dated deadline).
CYCLE_RE = re.compile(r"\b(?:applications? (?:are |will be )?accepted|application (?:period|round|window|cycle)|deadline|are due|is due)\b", re.I)
FEDERAL_RE = re.compile(r"\bfederal(?:ly)? (?:funds|funding|grant|program|dollars)\b|\bHUD\b|\bU\.S\. Department\b|\bARPA\b|\bAmerican Rescue Plan\b", re.I)
MATCH_RE = re.compile(r"\bmatch(?:ing)? (?:requirement|funds?|is required)\b|\b\d{1,3}% (?:local )?match\b", re.I)
CONTACT_RE = re.compile(r"@|\b\d{3}[.-]\d{3}[.-]\d{4}\b")   # an address or a number; "contact your officer" is prose
ZWSP_RE = re.compile(r"[​﻿]")


# ---------- parsing (no I/O) ----------

def _text(el: Tag) -> str:
    return clean(ZWSP_RE.sub("", el.get_text(" ")))


def source_id_for(url: str) -> str:
    """The page path under `/biz/`, lowercased, without `/pages/default.aspx`: `programs/cdbg`,
    `aboutus/artscommission/grants/for-organizations/arts-build-communities`."""
    path = urlparse(url).path.lower()
    path = re.sub(r"/pages/[^/]+\.aspx$", "", path).strip("/")
    return path[len("biz/"):] if path.startswith("biz/") else path


def parse_index(index_html: str) -> list[dict[str, Any]]:
    """One dict per program on the agency's own host: source_id, title, url, topic (from the by-topic view, else
    None), in alphabetical-view order then the by-topic extras. Links to other hosts are left out."""
    doc = _soup(index_html)
    topics: dict[str, str] = {}
    topic = None
    for el in (doc.find(id="programTopic") or doc).find_all(["h2", "a"]):
        if el.name == "h2":
            topic = _text(el)
        elif topic and el.get("href"):
            topics.setdefault(source_id_for(urljoin(INDEX_URL, el["href"])), topic)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for view in ("programAlpha", "programTopic"):
        for a in (doc.find(id=view) or doc).find_all("a", href=True):
            url, title = urljoin(INDEX_URL, a["href"]), _text(a)
            if not title or urlparse(url).netloc != urlparse(BASE).netloc or not urlparse(url).path.lower().startswith("/biz/"):
                continue
            sid = source_id_for(url)
            if sid in seen or not sid:
                continue
            seen.add(sid)
            out.append({"source_id": sid, "title": title, "url": url, "topic": topics.get(sid)})
    return out


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the program's h1, the last one on the page), blocks [(kind, text)] from the intro and body fields:
    label for a heading, else p or li, each block's own text (SharePoint nests headings and paragraphs inside
    paragraphs), consecutive repeats dropped, lines with an e-mail or a phone number dropped."""
    doc = _soup(page_html)
    main = doc.find("main") or doc
    h1s = main.find_all("h1")
    blocks: Blocks = []
    for suffix in (INTRO_SUFFIX, BODY_SUFFIX):
        field = next((f for f in main.select(".ms-rtestate-field") if (f.get("id") or "").endswith(suffix)), None)
        for el in field.find_all(["h2", "h3", "h4", "p", "li"]) if field is not None else []:
            kind = "label" if el.name.startswith("h") else el.name
            text = clean(ZWSP_RE.sub("", own_text(el)))
            # a heading is often repeated as a bold paragraph right after it; one copy, as the label
            if not text or CONTACT_RE.search(text) or (blocks and blocks[-1][1] == text):
                continue
            blocks.append((kind, text))
    return {"title": _text(h1s[-1]) if h1s else "", "blocks": blocks}


def applicant_lines(blocks: Blocks) -> list[str]:
    return label_lines(blocks, LABEL_RE, APPLICANT_RE)


# ---------- the connector ----------

class Biz(HandListConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = JURISDICTION
    # Accepting with applications named, or applications open or being accepted; not "accepted for further review"
    # (Arts Build Communities), not "open to public comments" (the Broadband Deployment Program's challenge window), and
    # not "No Longer Accepting Applications" (Aquifer Recharge), which the default table would read open-first.
    OPEN_RE = re.compile(
        r"\b(?<!no longer )(?<!not )(?<!stopped )(?:now )?accepting\b[^.]*\bapplications\b"
        r"|\bapplications?\b[^.]*\b(?:are|is|will be|now) (?:(?:now )?open(?!\s+to public)|being accepted"
        r"|accepted (?:year-round|on a rolling|through|until|from|beginning|starting))\b", re.I)
    CLOSED_RE = re.compile(
        r"\bclosed for applications\b|\b(?:is|are) (?:now |currently )?closed\b|\bno longer accepting\b"
        r"|\b(?:currently )?not (?:currently )?accepting\b", re.I)

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def round_sentence(self, blocks: Blocks) -> str | None:
        """The default table's pick, else the first sentence that states a cycle (kept as text, status unknown)."""
        return super().round_sentence(blocks) or first_sentence([b for b in blocks if b[0] != "label"], CYCLE_RE)

    def fetch(self, limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
        """The index (a failure raises), then one GET per program. A page that fails keeps its stored page."""
        prior = prior or {}
        records: list[RawRecord] = []
        with _client() as client:
            programs = parse_index(_get(client, INDEX_URL))
            for program in programs[:limit] if limit else programs:
                sid = program["source_id"]
                payload: dict[str, Any] = {"program": program, "page": None}
                try:
                    time.sleep(DELAY_S)
                    payload["page"] = parse_page(_get(client, program["url"]))
                except httpx.HTTPError:
                    payload["page"] = (prior.get(sid) or {}).get("page")
                records.append(RawRecord(source_connector=CONNECTOR, source_id=sid, payload=payload))
        return records

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        program, page = raw.payload["program"], raw.payload.get("page") or {}
        blocks = [tuple(b) for b in page.get("blocks", [])]
        text = " ".join(t for _, t in blocks)
        name = clean(program["title"]) or clean(page.get("title", "")) or raw.source_id
        sentence = self.round_sentence(blocks)
        closes_at = self.closes_at_for(sentence)
        status, rolling = self.status_for(sentence, closes_at, today)
        lines = applicant_lines(blocks)
        topic = program.get("topic")
        categories = [CategoryTag(value=v, source_code=topic) for v in portal_categories(topic) if v != "other"] if topic else []
        return dict(
            source_url=program["url"],
            name=name,
            funding_type=funding_type_for(name),
            funding_source="pass_through" if FEDERAL_RE.search(text) else "direct",
            match_required=True if MATCH_RE.search(text) else None,
            status=status,
            opens_at=None,
            closes_at=closes_at,
            closes_at_text=sentence,
            rolling=rolling,
            summary=first_p(blocks),
            eligibility_text="\n".join(lines) or None,
            eligibility_structured={"topic": topic} if topic else None,
            applicant_types=applicant_tags(lines),
            categories=categories,
        )


SITE = Biz()
fetch = SITE.fetch
normalize = SITE.normalize
round_sentence = SITE.round_sentence
status_for = SITE.status_for
closes_at_for = SITE.closes_at_for
