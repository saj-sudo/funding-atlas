# Kentucky's agency pages (`ky_dlgfed`, `ky_tc`, `ky_eec`, `ky_kia`): source, raw data and field mapping

Milestone 12.6d, the fourth agency state (the 12.6 cost ranking's next, after Vermont, Connecticut and North Dakota).
Written 2026-11-11 from a read-only probe of the four agencies' pages, before the parser. `ky_dlg` (12.5) already reads
the DLG Portal's four state-funded rounds; this adds the programs that live on agency pages.

## Implemented (2026-11-11)

`connectors/kentucky_sharepoint.py` and the four agency modules follow this doc. First live run, on the database
restored from `gh-pages`: 24 added (11 DLG, 2 Transportation, 6 Energy and Environment, 5 KIA), 0 errors, 19 GETs; second
run 0 changed. Open: Housing Program (to 2027-02-01), Economic Development (to 2027-03-01), Community Emergency Relief
Fund (to 2027-01-31) and the ARC Area Development Program (pre-applications rolling from 2026-08-01); Recovery Kentucky
Public Services is open too but names no applicant, so it is not on the page. `unknown`: the rest (Community Projects and
Public Facilities windows ended 2026-09-01, LWCF's and RTP's deadline passed 2026-10-30, TAP's 2026 awards are out and
"the next application cycle ... will be held in 2027", everything on the EEC and KIA pages states no round). The Kentucky
page: 15 new rows (8 DLG, 1 Transportation, 3 EEC, and KIA's Funds B, C and F, decision 8), 4 open municipal beside the
portal's 2. The other 9 new records are off it: Fund A and the Cleaner Water grants, six that name no applicant (RTP,
Recovery Housing, Public Services, TAP, Nonpoint Source, Waste Tire) and Illegal Dump (counties only).

Found while writing the parser:

- Transportation Cabinet pages keep their text in Content Editor web parts, not in the `RichHtmlField` (empty there),
  so the selector is the class `div.ms-rtestate-field`, outermost only.
- RTP's "It is due on Friday, October 30th, 2026. If you have any questions, please contact ...@ky.gov" is one
  paragraph; dropping the block for its contact dropped the deadline. Contact **sentences** are cut, not blocks.
- The EEC's four labelled lines (Administering Agency, Type of Funding, Funding Source, Eligible Entities) are bare
  `div`s; a `div` with no block inside is read as a paragraph. The shared summary skips those lines.
- The EEC's first heading reads "C lean Water ..." (the C is its own span).
- Shared table, measured on all 7,630 stored records (`scripts/measure_tagger.py`): 0 tag moves, 1 hash move
  (Connecticut SLCGP: "applicant must be" now also reads the singular, so a statute's list of eligible entities joins its
  eligibility text; tags unchanged). The Vermont, Connecticut and North Dakota fixtures keep identical `record_hash`
  except that one. The two tagger rules (`may submit an application`; `local and state government agencies`) move no
  stored record and are kept because Kentucky's CERF and CMAQ pages need them (tests pin both).

## The platform

All four hosts run classic SharePoint publishing: the title is the `h1`, the text sits in rich-text fields
(`div.ms-rtestate-field`; the main one's id ends `__ControlWrapper_RichHtmlField`), later fields hold a staff list or a
"Downloads" label. `robots.txt` on every host disallows only `/_Layouts/ /SiteAssets/ /Lists/ /_catalogs/ /WorkflowTasks/`;
no target page needs a login. `dlg.ky.gov/grants/` redirects to `/grants/Pages/default.aspx` (the shared client follows).
The page reader (`connectors/kentucky_sharepoint.py`): blocks `h2, h3, h4, p, li` from every outermost field in page order;
a leaf `div` is a paragraph; contact sentences ("Phone:", "Fax:", "E-mail:", `@ky.gov`, a `###-###-####` number) are cut; a
field stops at "Past Funded Projects" and the usual past-awards headings.

## The pages (2026-11-11)

| Connector | Agency (code) | Category | Records |
|---|---|---|---|
| `ky_dlgfed` | Department for Local Government (`KY-DLG`), `dlg.ky.gov/grants/federal/...` | per record: community development, parks and recreation, housing, economic development, disaster recovery, wastewater, health | ARC, DRA, LWCF, RTP, Recovery Housing, CDBG Community Projects, Community Emergency Relief Fund, Economic Development, Housing, Public Facilities, Public Services (Recovery Kentucky) |
| `ky_tc` | Transportation Cabinet, Office of Local Programs (`KY-KYTC`), `transportation.ky.gov/LocalPrograms/Pages/` | transportation | `TAP.aspx`, `CMAQ.aspx` |
| `ky_eec` | Energy and Environment Cabinet (`KY-EEC`), `eec.ky.gov/Environmental-Protection/resources/Pages/grants-and-loans.aspx` | per record: other (waste), non-point source, drinking water | Illegal Dump Cleanup, Litter Abatement, Nonpoint Source Pollution Control (319(h)), Waste Tire, Recycling and Household Hazardous Waste, Source Water Protection Assistance (SWPAP) |
| `ky_kia` | Infrastructure Authority (`KY-KIA`), `kia.ky.gov/FinancialAssistance/Pages/` | infrastructure; Funds A and F water | Fund A (wastewater), B (infrastructure), C (governmental), F (drinking water): loans; Cleaner Water Grants |

The EEC's index is one page that holds every program: **one GET, six records** (`SPLITS`, below). Its ids: the page key
`illegal-dump` keeps the first program, the others are `illegal-dump#litter-abatement`, `#nonpoint-source`, `#waste-tire`,
`#recycling-hhw`, `#swpap`.

## Raw samples (verbatim, 2026-11-11)

- DLG, Community Projects: "Who can Apply: All cities and counties are eligible to apply for the funds with the exception of
  entitlement communities. Applications Accepted: April 1, 2026 - September 1, 2026." The other CDBG pages read "Dates are
  ..." and, for CERF, "The application submission dates are April 1, 2026 - January 31, 2027." No deadline word anywhere:
  the shared table gained a window rule (below).
- DLG, CERF: "Who can Apply: Only communities that have experienced a disaster and have a Declaration of Emergency from the
  Governor may submit an application for these funds."
- DLG, ARC: "Kentucky ARC Area Development Program — Pre-Applications Open August 1, 2026 ... accepted and reviewed on a rolling
  basis"; "Pre-applications ... are being accepted here"; "Who Can Apply? Local governments, special districts, and
  non-profit entities ...".
- DLG, RTP: "The 2026 application ... is due on Friday, October 30th, 2026"; eligibility is in a guidance PDF.
- Transportation, CMAQ: "Local and state government agencies are eligible to apply for CMAQ funding. Non-profits and
  private sector entities may partner with an eligible applicant to complete a project."
- Transportation, TAP: "The 2026 TAP awards have been announced ... The next application cycle for state TAP funds will be
  held in 2027."; applicants are in the FHWA legislation it links.
- EEC: `<h4>Illegal Dump Cleanup Grant Program</h4><div><strong>Administering Agency:</strong> Kentucky Division of Waste
  Management</div><div><strong>Type of Funding:</strong> Grant</div><div><strong>Funding Source:</strong> Kentucky Pride
  Fund</div><div><strong>Eligible Entities:</strong> County Governments</div>` then a paragraph.
- KIA, Fund B: "Eligibility: Eligible projects are those permitted by KRS224A.011(16). The applicant must be a governmental
  agency and the project must be financially feasible as determined by KIA staff."

## Field mapping

The agency-page table in `connectors/hand_list.py` (`AgencyPageConnector`); per record:

| Program field | From |
|---|---|
| `source_id`, `source_url` | the page key (EEC: `illegal-dump`, `illegal-dump#...`); `BASE` + the page path |
| `name` | the page's `h1` (EEC: the program's own heading, `SPLITS`) |
| `level`, `jurisdiction` | `state`, `KY` |
| `funding_type` | `FUNDING_TYPES` (KIA: A, B, C, F `loan`; Cleaner Water `grant`), else the shared keyword, else `grant` |
| `funding_source` | the page's "Funding Source:" line (EEC: "Kentucky Pride Fund" direct; "U.S. Environmental Protection Agency" pass-through), else `pass_through` when the page names HUD, FHWA, FEMA, NPS, "federally funded" |
| `status`, `opens_at`, `closes_at`, `closes_at_text` | the round rule: a deadline word with a date, else an **application window** ("Applications Accepted: <date> - <date>", only when the sentence is about applications and nothing else on the page is a deadline), then closed wording, then undated open wording (now including "are being accepted") |
| `summary` | the first paragraph that is not a status line or one of the EEC's four labelled lines |
| `eligibility_text`, `applicant_types` | the applicant sentences (now also "Who can Apply: ...", "applicant(s) must be", a bare "Eligibility:" label over a list) through the shared tagger; a "may partner with" sentence stays in the text and is not tagged |
| `categories` | `CATEGORY_LABELS` per record over the portal table, else the agency's `CATEGORY_LABEL`; EEC's waste programs fall to `other` (the table has no waste topic) |
| `amount_*`, `alns`, `external_number`, `rolling` | null or empty: the pages state no amount, and `rolling` is never read from these pages |

## Decisions

1. **A page that holds several programs is one record per program** (Saj's call, 2026-11-11, roadmap decisions log). The
   EEC page makes six; `AgencyPageConnector.SPLITS` cuts it at the `h4` headings, the first program keeps the page's id.
   The same rule was applied to North Dakota's Flex Fund and hazard mitigation page the same day.
2. **CDBG-DR 2021 and 2022 are not read** (Saj's call): subrecipient programs for declared disasters, no opportunity on the
   portal either (`ky_dlg`). Not records: the CDBG overview, Training (a schedule), Build America Buy America, the Area
   Development Districts page (funds the ADDs, not towns) and KORRRA (an authority with no grant call).
3. **No double count with `ky_dlg`.** LMPP, RDAAP, Legislative Line-Items and Coal Severance are on the DLG Portal and stay
   there; the DLG's `/grants/state/` pages are not read.
4. **The EEC's two state revolving funds are KIA's Funds A and F** (the EEC row says "Administering Agency: Kentucky
   Infrastructure Authority and the Kentucky Division of Water") and are read from KIA only. The EEC's Underground Storage
   Tank claims reimburse tank owners, not towns, and are not read.
5. **The EEC rows come from the index alone.** The Illegal Dump and Litter Abatement detail pages announce a round
   ("Applications are now being accepted ... until Nov. 2, 2026"); today that date has passed, so reading them would change
   no status. A later session can add the detail pages when a round is open (one record per program, one more GET each).
6. **Kentucky Emergency Management is blocked**: Akamai answers 403 on its robots.txt and home page through the proxy
   (probed 2026-11-11). Recorded, as VDEM; no workaround.
7. **TAP's and RTP's applicants stay empty**: the pages name them only in an FHWA document and an RTP guidance PDF, and
   TAP and RTP are not open (Saj's PDF rule, 10.6).

8. **KIA's Funds B, C and F quote the statute for their applicants** (Saj's call, 2026-11-11). The three pages say "The
   applicant must be a governmental agency" (Fund F: "Governmental agencies, other than federal agencies") and name no
   type. KRS 224A.011(21) defines the term: "any incorporated city or municipal corporation, or other agency, or unit of
   government within or a department or a cabinet of the Commonwealth ... incorporated cities; counties ...; sanitation
   districts; water districts; water associations; sewer construction districts; metropolitan sewer districts ...".
   `ky_kia.HAND_QUOTES` quotes that definition, dated 2026-11-11 and attributed, for those three pages (the MDOT, Illinois and
   Vermont precedent), with "but not by way of limitation" cut as `[...]` (the tagger drops a sentence that holds a
   negation). They tag `municipality` and `county` and reach the Kentucky page as `unknown` rows. **Not a shared rule:**
   "governmental agenc*" appears in 54 stored records (22 SAM.gov, 17 Texas, 8 California, 1 West Virginia, KIA's 2), loose
   federal wording ("quasi-governmental agencies", "a State governmental agency"), and a global rule would move about fifty
   tags the statute does not govern. **An exception to the 10.6 rule** (PDF eligibility is quoted by hand only where the
   quote would put an open row on a page): the rows are `unknown`, but this is a statute, not a PDF, one quote serves three
   pages, and unknown rows already show on the page (the EEC's). Fund A is not quoted: its page cites nothing.

## Gaps (recorded, not hidden)

- **KIA's Fund A and the Cleaner Water grants tag no applicant**: their pages name none (Fund A is the Clean Water SRF; the
  EEC's index says only "public wastewater systems"). Funds B, C and F are decision 8.
- The sanitation, water and sewer districts in the statute's list stay untagged on Funds B, C and F: the tagger has no
  "water district" word. A rule is a separate, measured change.
- The waste programs' "solid waste management districts" are not in the tagger's special-district words
  (Recycling and HHW tags municipality, county, school and higher_ed from the rest of its line).
- The Waste Tire page's "offers grants for Kentucky schools, city and county governments, businesses ..." is not read as an
  applicant sentence ("offers grants for" also introduces purposes); its record tags nothing, and its own eligibility line
  says "All entities are eligible to apply".
- `rolling` is null everywhere: ARC says "rolling basis" and is open with no close, which is not read as rolling here.
