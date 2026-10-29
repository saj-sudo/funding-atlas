"""One-off probe for the New Jersey DCA SAGE connector: read the public RFP list once, keep the RFPs the tests need,
save the trimmed page (and an empty-list page built from the same chrome) as fixtures, and print what the connector sees.
  uv run python scripts/probe_nj_dca_sage.py
Writes tests/fixtures/nj_dca_sage/: list.html (four RFPs across both divisions) and empty.html (no RFP). Scripts, hidden
inputs and the program contact (names, phones, e-mail links) are removed from both."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import nj_dca_sage as nj  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "nj_dca_sage"

KEEP = {
    "Affordable Housing Trust Fund 2027": "municipal; award minimum, maximum and total; a Housing division RFP",
    "Lead-Safe Home Remediation 2026": "units of local government; maximum and total",
    "Neighborhood Revitalization Tax Credit Planning 24": "a tax credit in the title; a grant period that ended in 2024",
    "Volunteer Emergency Service Organization Loan 2027": "the Fire Safety division; a loan; no grant-period dates",
}


LABEL = '<label class="RFPCategoryName">'
SPACER = '<tr><td colspan="4">&nbsp;</td></tr>'    # the row that closes the last RFP; the page tail follows it


def blocks(page: str) -> tuple[str, list[tuple[str, bool, str]], str]:
    """(head, [(label, is_division, text), ...], tail) by slicing the raw text: the page's HTML is not well formed
    (a tree parser nests later RFPs inside earlier ones), but every block starts at the row before its label."""
    starts = [page.rfind("<tr", 0, m.start()) for m in re.finditer(re.escape(LABEL), page)]
    last_field = page.rfind("rfpOtherInformation_")
    tail_at = page.index(SPACER, last_field)
    ends = [*starts[1:], tail_at]
    out = []
    for start, end in zip(starts, ends, strict=True):
        text = page[start:end]
        label = " ".join(re.sub(r"<[^>]+>", "", re.search(r"<label class=\"RFPCategoryName\">(.*?)</label>", text, re.S).group(1)).split())
        out.append((label, 'bgcolor="#C3D3D3"' in text.split(LABEL)[0], text))
    return page[: starts[0]], out, page[tail_at:]


def scrub(page: str) -> str:
    """Scripts, hidden inputs (their values hold the contact), e-mail links and the contact spans."""
    page = re.sub(r"<script\b.*?</script>", "", page, flags=re.S | re.I)
    page = re.sub(r"<input\b[^>]*type=\"hidden\"[^>]*>", "", page, flags=re.I)
    page = re.sub(r"<a\b[^>]*href=[\"']mailto:[^\"']*[\"'][^>]*>.*?</a>", "", page, flags=re.S | re.I)
    page = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "", page)      # any e-mail address left in running text
    return re.sub(r"<span\b[^>]*id=\"ProgramContact\w*\"[^>]*>.*?</span>", "", page, flags=re.S | re.I)


def trim(page: str, keep: set[str]) -> str:
    head, parts, tail = blocks(page)
    kept: list[str] = []
    for i, (label, division, text) in enumerate(parts):
        if division:
            following = []
            for later, later_division, _ in parts[i + 1:]:
                if later_division:
                    break
                following.append(later)
            if any(t in keep for t in following):
                kept.append(text)
        elif label in keep:
            kept.append(text)
    return scrub(head + "".join(kept) + tail)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with nj._client() as client:
        page = nj._get(client, nj.LIST_URL)
    rfps, expected = nj.parse_page(page)
    print(f"page: {len(rfps)} RFPs, {expected} deadline labels")
    for title, why in KEEP.items():
        print(f"  {title}: {'found' if any(r['title'] == title for r in rfps) else 'MISSING'}  ({why})")
    listed, empty = trim(page, set(KEEP)), trim(page, set())
    (FIXTURES / "list.html").write_text(listed, encoding="utf-8")
    (FIXTURES / "empty.html").write_text(empty, encoding="utf-8")
    kept, kept_expected = nj.parse_page(listed)
    none, none_expected = nj.parse_page(empty)
    print(f"list.html: {len(kept)} RFPs ({kept_expected} labels); empty.html: {len(none)} RFPs ({none_expected} labels), "
          f"instruction text present: {nj.INSTRUCTION_TEXT in empty}")
    for slug, rfp in zip(nj.unique_slugs([r["title"] for r in kept]), kept, strict=True):
        p = nj.normalize(RawRecord(source_connector=nj.CONNECTOR, source_id=slug, payload=rfp), date.today())
        print(f"  {slug[:40]:40} | {p.administering_agency} | {p.status} {p.closes_at} | {p.funding_type} {p.amount_min}-{p.amount_max}"
              f" | {sorted({t.value for t in p.applicant_types})} | {p.eligibility_structured}")


if __name__ == "__main__":
    main()
