"""Oklahoma Department of Commerce connector: the state CDBG programs and the Disaster Mitigation and Recovery Matching
Fund (milestone 12.9).

Source: https://www.okcommerce.gov, WordPress with Elementor; one GET per page in `PAGES`. No other Oklahoma agency is
read, so the reader is this module's own. The page's text is the Elementor `single` location (`h1` and content; header,
footer and pop-ups are other locations). The CDBG hub holds seven programs under "Programs", one record each (CIP keeps the
page's `source_id`); its DUNs how-to, meeting dates and State Plan hearing notice are not read, the Coronavirus Relief and
Disaster Recovery entries belong to no record, and the read stops at "Resources". No page states a round: applications
are filed in the Oklahoma Grant Exchange (a login, `Disallow: /`, never fetched). Status table and field mapping are the
agency-page table in `connectors/hand_list.py`. Left out: Main Street (no applicant stated), SITES (2023 and 2024 rounds),
Community Incentives, CSBG/ESG/Weatherization, CDBG-DR.
12.12: the rounds the pages do not state are in each program's guidance PDF, linked from its section of the hub. The PDF
is read every run (`pypdf`) and only its application-deadline sentences are kept in the payload; the first one dates the
round when the page states none. See docs/connectors/oklahoma.md.
"""

from __future__ import annotations

import io
import re
import time
from datetime import date
from typing import Any
from urllib.parse import urljoin

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from connectors.hand_list import (
    AgencyPageConnector,
    applicant_tags,
    blocks_from,
    clause_cut,
    client,
    first_date,
    soup,
)
from connectors.maryland_drupal import sentences
from connectors.sam_assistance_listings import clean
from pipeline.models import RawRecord

CONNECTOR = "ok_commerce"
BASE = "https://www.okcommerce.gov"
AGENCY = "Oklahoma Department of Commerce"
AGENCY_CODE = "OK-COMMERCE"
CATEGORY_LABEL = "community development"
LABEL_MAX_CHARS = 90
BODY_SELECTOR = "div.elementor-location-single"

PAGES: dict[str, str] = {
    "cdbg": "/community-development/local-governments-edos/community-development-block-grant-programs/",
    "odmrmf": "/reporting-compliance/oklahoma-disaster-mitigation-and-recovery-matching-fund-program/",
}
SPLITS = {"cdbg": [
    ("cip", "CDBG Capital Improvement Planning (CIP)", re.compile(r"^Capital Improvement Planning\b", re.I)),
    ("small-cities", "CDBG Small Cities", re.compile(r"^CDBG Small Cities$", re.I)),
    ("community-revitalization", "CDBG Community Revitalization", re.compile(r"^CDBG Community Revitalization$", re.I)),
    ("water-wastewater-construction", "CDBG Water-Wastewater Construction", re.compile(r"^CDBG Water-Wastewater Construction$", re.I)),
    ("edif", "CDBG Economic Development Infrastructure Financing (EDIF)", re.compile(r"^CDBG Economic Development Infrastructure\b", re.I)),
    ("water-wastewater-engineering", "CDBG Water + Wastewater Engineering", re.compile(r"^CDBG Water \+ Wastewater Engineering$", re.I)),
    ("reap", "CDBG Rural Economic Action Plan (REAP)", re.compile(r"^CDBG Rural Economic Action Plan\b", re.I)),
    # a closed one-time appropriation, then the three Disaster Recovery entries (no heading of theirs matches): no record
    ("cv", None, re.compile(r"^CDBG Coronavirus Relief\b", re.I)),
]}
CATEGORY_LABELS = {
    "cdbg#water-wastewater-construction": "environment and water",
    "cdbg#water-wastewater-engineering": "environment and water",
    "odmrmf": "emergency mitigation",
}
INLINE = ["strong", "b", "em", "i", "a", "span", "u"]
# Sections of the hub that are not a program's text: a how-to for SAM.gov, trainings and meetings, and the State Plan
# hearing notice ("Written comments ... will be accepted until December 18, 2026" is a comment period, not a round).
SKIP_SECTION_RE = re.compile(r"^(?:DUNs Number\b|Save the Dates$|Notice:)", re.I)
DROP_RE = re.compile(r"@okcommerce\.gov|\[email\s*protected\]|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|^return to top$", re.I)
# ODMRMF's purpose ("dedicated state funding to help local governments and related entities secure ... federal ...
# funds") names who benefits; its applicants are the planning districts listed under "Eligible Applicants".
NOT_APPLICANT_RE = re.compile(r"\bfunding to help local governments\b", re.I)
STOP_RE = re.compile(r"(?:resources|policies (?:&|and) procedures|annual reporting|your .* team)$", re.I)
# 12.12: a program's guidance PDF ("2026-CDBG-CIP-Application-Guidelines.pdf", "2026-WW-Engineering-Application-Guidance.pdf")
GUIDANCE_RE = re.compile(r"guidelines|guidance", re.I)
# "CIP applications must be submitted to ODOC by 5:00 PM, July 10, 2026."; "... applications must be completed online no
# later than March 27, 2026"; "Applications will be accepted through May 1, 2026"; "... Application Submission Due Date is
# June 19, 2026". A Letter of Intent, a closeout or an audit date names no application and is not read.
DEADLINE_RE = re.compile(r"\bapplications?\b[^.]*?\b(?:no later than|submitted (?:to \S+ )?by|accepted (?:until|through)"
                         r"|due date is|received by)\b", re.I)
PDF_MAX_BYTES = 8_000_000


def parse_page(page_html: str) -> dict[str, Any]:
    """title (the `h1`) and the blocks of the Elementor page body, without the skipped sections, up to "Resources"."""
    doc = soup(page_html)
    body = doc.select_one(BODY_SELECTOR)
    if body is None:
        return {"title": "", "blocks": []}
    h1 = body.find("h1")
    title = clean(h1.get_text(" ")) if h1 else ""
    guidance = guidance_links(body)   # the links sit in the icon lists, which are not read as text
    for junk in body.select("ul.elementor-icon-list-items, form, nav"):
        junk.decompose()
    skipping = False
    skipped = []
    for el in body.find_all(["h2", "h3", "h4", "p", "li"]):
        if el.name == "h2":
            skipping = bool(SKIP_SECTION_RE.match(clean(el.get_text(" "))))
        if skipping:
            skipped.append(el)
    for el in skipped:
        el.extract()
    for li in body.find_all("li"):
        if not li.find(["ul", "ol"]):
            for tag in li.find_all(INLINE):
                tag.unwrap()
    blocks = blocks_from(body, ["h2", "h3", "h4", "p", "li"], stop_re=STOP_RE, drop_re=DROP_RE, bold_max=LABEL_MAX_CHARS)
    return {"title": title, "blocks": blocks, "guidance": guidance}


def guidance_links(body: Any) -> dict[str, str]:
    """heading -> the guidance PDF linked in that heading's section, in page order (12.12): a `.pdf` link whose file name
    or text says Guidelines or Guidance, under the nearest `h2`-`h4` before it."""
    out: dict[str, str] = {}
    heading = ""
    for el in body.find_all(["h2", "h3", "h4", "a"]):
        if el.name != "a":
            heading = clean(el.get_text(" "))
            continue
        href = el.get("href", "")
        if heading and href.lower().endswith(".pdf") and (GUIDANCE_RE.search(href) or GUIDANCE_RE.search(el.get_text(" "))):
            out.setdefault(heading, urljoin(BASE + "/", href))
    return out


def get_pdf(c: httpx.Client, url: str) -> bytes:
    """One PDF's bytes; tests patch this name. A transport error (the 3 MB Engineering file once failed mid-run,
    2026-11-25) is tried once more after 3 s; an HTTP status is not. A file over `PDF_MAX_BYTES` is not read."""
    try:
        r = c.get(url)
    except httpx.TransportError:
        time.sleep(3.0)
        r = c.get(url)
    r.raise_for_status()
    if len(r.content) > PDF_MAX_BYTES:
        raise httpx.HTTPError(f"{url}: {len(r.content)} bytes, over the {PDF_MAX_BYTES} cap")
    return r.content


def pdf_sentences(data: bytes) -> list[str]:
    """The PDF's application-deadline sentences with a full date, in order, each once."""
    text = " ".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(data)).pages)
    out: list[str] = []
    for s in sentences(re.sub(r"\s+", " ", text)):
        if DEADLINE_RE.search(s) and first_date(s) and s not in out:
            out.append(s)
    return out


def pdf_name(url: str) -> str:
    """"2026-CDBG-CIP-Application-Guidelines.pdf" -> "2026 CDBG CIP Application Guidelines"."""
    return url.rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("-", " ")


class OkCommerce(AgencyPageConnector):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    JURISDICTION = "OK"
    CATEGORY_LABEL = CATEGORY_LABEL
    CATEGORY_LABELS = CATEGORY_LABELS
    PAGES = PAGES
    SPLITS = SPLITS
    DELAY_S = 3.0

    def parse_page(self, page_html: str) -> dict[str, Any]:
        return parse_page(page_html)

    def records_for(self, slug: str, spec: str, pages: list[dict[str, Any]], count: int) -> list[tuple[str, dict[str, Any]]]:
        """The split records, each with the guidance PDF its own section links (`guidance_url`), and no link map in the
        stored page."""
        links = pages[0].get("guidance", {})
        pages = [{k: v for k, v in pages[0].items() if k != "guidance"}, *pages[1:]]
        out = super().records_for(slug, spec, pages, count)
        patterns = {(slug if sub == self.SPLITS[slug][0][0] else f"{slug}#{sub}"): pattern
                    for sub, _, pattern in self.SPLITS.get(slug, [])}
        for sid, payload in out:
            pattern = patterns.get(sid)
            url = next((u for head, u in links.items() if pattern is not None and pattern.search(head)), None)
            if url:
                payload["guidance_url"] = url
        return out

    def fetch(self, limit: int | None = None, prior: dict[str, dict[str, Any]] | None = None) -> list[RawRecord]:
        """The pages, then each record's guidance PDF (the same pace). A PDF that cannot be read keeps the stored
        copy's sentences, or none."""
        prior = prior or {}
        records = super().fetch(limit, prior)
        with client() as c:
            for r in records:
                url = r.payload.get("guidance_url")
                if not url:
                    continue
                time.sleep(self.DELAY_S)
                try:
                    r.payload["guidance"] = {"url": url, "sentences": pdf_sentences(get_pdf(c, url))}
                except (httpx.HTTPError, PdfReadError):
                    kept = prior.get(r.source_id, {}).get("guidance")
                    if kept and kept.get("url") == url:
                        r.payload["guidance"] = kept
        return records

    def fields(self, raw: RawRecord, today: date) -> dict[str, Any]:
        out = super().fields(raw, today)
        guide = raw.payload.get("guidance") or {}
        said = (guide.get("sentences") or [None])[0]
        closes = said and first_date(said)
        if closes and out["status"] == "unknown" and out["closes_at"] is None and not out["rolling"]:
            out.update(status="open" if today <= closes else "unknown", closes_at=closes,
                       closes_at_text=f"{pdf_name(guide['url'])} (PDF): {said}")
        lines = (out["eligibility_text"] or "").split("\n")
        kept = [line for line in lines if not NOT_APPLICANT_RE.search(line)]
        if kept != lines:
            out["eligibility_text"] = "\n".join(kept) or None
            out["applicant_types"] = applicant_tags([clause_cut(line) for line in kept])
        return out


SITE = OkCommerce()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
