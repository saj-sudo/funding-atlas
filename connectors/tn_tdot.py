"""Tennessee DOT connector: the Transportation Alternatives Program page (milestone 12.9).

Source: https://www.tn.gov, the same Adobe Experience Manager site and reader as `tn_ecd` (one GET, the same pace).
TDOT's Local Programs pages are short: TAP's is one paragraph on what the program funds and who has received it, with
no round, so the record is `unknown` until the page dates one. The Funding Options page (formula STBG allocations, no
application) and the Active Transportation Office page (no program) are left out; the State Infrastructure Fund,
Multimodal Access Grant and TDEC's and TEMA's pages are follow-ups in docs/connectors/tennessee.md.
"""

from __future__ import annotations

from connectors.tn_ecd import TnAgency

CONNECTOR = "tn_tdot"
BASE = "https://www.tn.gov"
AGENCY = "Tennessee Department of Transportation"
AGENCY_CODE = "TN-TDOT"
CATEGORY_LABEL = "transportation"

PAGES: dict[str, str] = {
    "tap": "/tdot/local-programs-community-investments/local-programs/tap.html",
}
# "the former Federal Transportation Enhancement (TE) Program, now known as the Transportation Alternatives Program"
FUNDING_SOURCES = {"tap": "pass_through"}


class TnTdot(TnAgency):
    CONNECTOR = CONNECTOR
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    FUNDING_SOURCES = FUNDING_SOURCES


SITE = TnTdot()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
