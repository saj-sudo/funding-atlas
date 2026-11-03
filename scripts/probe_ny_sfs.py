"""One-off probe for the New York SFS connector: run the portal flow once with the connector's own functions, keep the
rows the tests need, save trimmed answers as fixtures, and print what the connector sees.
  uv run python scripts/probe_ny_sfs.py
Writes tests/fixtures/ny_sfs/: search.html (the GET, four rows kept), return.xml (one Return to Search answer, the
same rows), closed.html (the closed search, three rows kept: one with an abstract link, two without) and
abstract_<n>.html for the kept open rows. Scripts are removed, the session id and state are replaced by placeholders,
and the contact name and email by `Contact Name` / `contact@example.ny.gov`."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors import ny_sfs as ny  # noqa: E402
from pipeline.models import RawRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ny_sfs"

# why -> predicate on a parsed open row; the first row satisfying each is kept (with its abstract).
WANTED_OPEN = (
    ("Available, three labels, an announcement link", lambda r: r["status"] == "Available" and r["eligibility"].count(",") == 2),
    ("Advertised Only, Not-For-Profit alone", lambda r: r["status"].startswith("Advertised") and r["eligibility"] == "Not-For-Profit"),
    ("Governmental Entity alone", lambda r: r["eligibility"] == "Governmental Entity"),
    ("a title cut at 50 characters", lambda r: len(r["name"]) >= 49),
)
WANTED_CLOSED = (
    ("a closed row with an abstract link", lambda r: r["linked"]),
    ("a closed row without", lambda r: not r["linked"]),
    ("a closed row with Individual", lambda r: "Individual" in r["eligibility"] and not r["linked"]),
)
_ROW_BLOCK_RE = re.compile(r"<tr id='trRESP_INQA_HD_VW_GR\$0_row(\d+)'.*?</tr>", re.S)
_SID_RE = re.compile(r"(name='ICSID'[^>]*value=')[^']*(')")
_STATE_INPUT_RE = re.compile(r"(name='ICStateNum'[^>]*value=')\d+(')")
_STATE_SCRIPT_RE = re.compile(r"ICStateNum\.value=\d+")


def keep_rows(text: str, keep: set[int]) -> str:
    """Drop every grid row whose number is not in `keep`; works on a full page and inside CDATA alike."""
    return _ROW_BLOCK_RE.sub(lambda m: m.group(0) if int(m.group(1)) - 1 in keep else "", text)


def scrub(text: str, contact_name: str = "", contact_email: str = "") -> str:
    text = re.sub(r"<script\b.*?</script>", "", text, flags=re.S | re.I)
    text = _SID_RE.sub(r"\1FIXTURE-SID\2", text)
    text = _STATE_INPUT_RE.sub(r"\g<1>1\2", text)
    text = _STATE_SCRIPT_RE.sub("ICStateNum.value=1", text)
    if contact_name:
        text = text.replace(contact_name, "Contact Name")
    if contact_email:
        text = text.replace(contact_email, "contact@example.ny.gov")
    return text


def contact(page: str) -> tuple[str, str]:
    soup = BeautifulSoup(page, "html.parser")
    name = soup.find("span", id="NY_GG_ABSTRT_VW_OPRID")
    mail = soup.find("a", href=lambda h: h and h.lower().startswith("mailto:"))
    return (name.get_text(strip=True) if name else "", mail["href"][7:] if mail else "")


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with ny._client() as client:
        page = ny._get(client)
        rows = ny.parse_rows(page)
        print(f"open grid: {len(rows)} rows")
        keep: dict[int, dict] = {}
        for why, pred in WANTED_OPEN:
            hit = next((r for r in rows if r["n"] not in keep and pred(r)), None)
            print(f"  {why}: {hit['event_id'] if hit else None}")
            if hit:
                keep[hit["n"]] = hit
        (FIXTURES / "search.html").write_text(scrub(keep_rows(page, set(keep))), encoding="utf-8")
        return_saved = False
        for n, row in sorted(keep.items()):
            answer = ny._post(client, page, ny.LINK_ACTION.format(n=n))
            abstract = ny.parse_abstract(answer)
            assert abstract["event_id"] == row["event_id"], (abstract["event_id"], row["event_id"])
            name, mail = contact(answer)
            (FIXTURES / f"abstract_{n}.html").write_text(scrub(answer, name, mail), encoding="utf-8")
            page = ny._post(client, answer, ny.RETURN_ACTION)
            if not return_saved:
                (FIXTURES / "return.xml").write_text(scrub(keep_rows(page, set(keep))), encoding="utf-8")
                return_saved = True
            program = ny.normalize(RawRecord(source_connector=ny.CONNECTOR, source_id=ny.row_key(row),
                                             payload={"grid": "open", "row": row, "abstract": abstract}))
            print(f"  row {n} {program.source_id}: {program.status}, {program.closes_at}, "
                  f"{[t.value for t in program.applicant_types]}, {[c.value for c in program.categories]}, {program.source_url}")
        closed = ny._post(client, page, ny.SEARCH_ACTION, **{ny.STATUS_FIELD: ny.CLOSED})
        closed_rows = ny.parse_rows(closed)
        print(f"closed grid: {len(closed_rows)} rows")
        keep_closed: set[int] = set()
        for why, pred in WANTED_CLOSED:
            hit = next((r for r in closed_rows if r["n"] not in keep_closed and pred(r)), None)
            print(f"  {why}: {hit['event_id'] if hit else None}")
            if hit:
                keep_closed.add(hit["n"])
        (FIXTURES / "closed.html").write_text(scrub(keep_rows(closed, keep_closed)), encoding="utf-8")
    print("fixtures:", sorted(p.name for p in FIXTURES.iterdir()))


if __name__ == "__main__":
    main()
