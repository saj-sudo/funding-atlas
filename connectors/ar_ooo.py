"""Arkansas Office of Outdoor Recreation connector: the Outdoor Recreation Grants Program's three grants (milestone 12.6h).

Source: https://adpht.arkansas.gov (Parks, Heritage and Tourism), the state's WordPress; one GET per page in `PAGES`, ten
seconds apart (the robots file's `Crawl-delay: 10`). Each program page opens with its window ("Opens: May 1, 2026 Due:
August 28, 2026") and a list whose first item is "Eligible applicants: ...". Page reader in
`connectors/arkansas_wordpress.py`; status table and field mapping are the agency-page table in
`connectors/hand_list.py`. Not read: the program index (it repeats the three lists) and the FAQ page.
See docs/connectors/arkansas.md.
"""

from __future__ import annotations

from connectors.arkansas_wordpress import ArAgency

CONNECTOR = "ar_ooo"
BASE = "https://adpht.arkansas.gov"
AGENCY = "Arkansas Office of Outdoor Recreation"
AGENCY_CODE = "AR-OOR"
CATEGORY_LABEL = "outdoor recreation"
_G = "/office-of-outdoor-recreation/arkansas-outdoor-grants"
PAGES: dict[str, str] = {
    "matching": f"{_G}/matching-grants/",
    "fun-park": f"{_G}/fun-park-grants/",
    "trails": f"{_G}/trails-grants/",
}
NAMES = {
    "matching": "Outdoor Recreation Matching Grants",
    "fun-park": "Outdoor Recreation FUN Park Grants",
    "trails": "Trails for Life Grants (Great Strides)",
}


class ArOoo(ArAgency):
    CONNECTOR = CONNECTOR
    BASE = BASE
    AGENCY = AGENCY
    AGENCY_CODE = AGENCY_CODE
    CATEGORY_LABEL = CATEGORY_LABEL
    PAGES = PAGES
    NAMES = NAMES
    DELAY_S = 10.0


SITE = ArOoo()
fetch = SITE.fetch
normalize = SITE.normalize
resolve_missing = SITE.resolve_missing
