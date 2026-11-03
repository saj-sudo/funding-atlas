# Delaware DEMA connector (`de_dema`): source, raw data and field mapping

Milestone 11, Delaware's emergency management agency (the municipal five, decision 2026-11-03). Written 2026-11-03,
before the parser. The FEMA pass-throughs a town applies for through the state: homeland security, emergency
management performance, cybersecurity, hazard mitigation, public assistance.

## Implemented (2026-11-03, same day)

`connectors/de_dema.py` follows this doc. First live run: 10 records added, 0 errors; second run 0 changed. All
`unknown`. Three tag a municipality and county (SLCGP, HSGP, EMPG, from their "Eligible Subrecipient" paragraphs:
"State and local government agencies, tribal entities ..."), NSGP a nonprofit; HSGP and EMPG are `invitation_only`
on the page's own words. The six recovery entries carry no applicant. Found while writing the parser: the anchor id
sits on the accordion's button and the text in its sibling, and EMPG's Apply paragraph is "This program is by
invitation only."

## The source

`https://dema.delaware.gov/about/grants/` (the state CLF template; `robots.txt` is a 404, no restrictions). One page
in two views: the grants page itself, whose "Preparedness Grants" and "Recovery Assistance" accordions list each
program as a bold link with a one-sentence blurb, and the preparedness tab, `index.shtml?dc=preparednessgrants`,
which adds for the four preparedness programs an "Eligible Subrecipient" paragraph, "Eligible Projects" and an
"Apply" paragraph. Two GETs a run.

```html
<p><strong><a href="/about/grants/index.shtml?dc=preparednessgrants#HSGP">Homeland Security Grant Program (HSGP)</a></strong><br>
Supports state, local, tribal, and territorial governments in preparing for and preventing acts of terrorism.</p>
...
<h3>Hazard Mitigation</h3>
<p><strong><a href="https://www.fema.gov/grants/mitigation/learn/hazard-mitigation" target="_blank">Hazard Mitigation Grant Program (HMGP)</a></strong><br>Provides funds after a disaster to reduce future risks ...</p>
```

On the preparedness tab each program is a block with `id="NSGP"` and so on: "Eligible Subrecipient: Nonprofit
organizations that (1) meet the description under 501[C3] ... (2) are located within the State ...", "Apply: FEMA
typically releases a Notice of Funding Opportunity annually in the spring. Once the NOFO is released, applications
must be submitted by eligible Subrecipients to DEMA through the Grant Management Suite (GMS) prior to the state's
application deadline."

The page says of itself: "DEMA serves as the State Administrative Agency (SAA) for state-administered grants ...
These grant funds often come from the Federal Emergency Management Agency (FEMA) and the Department of Homeland
Security (DHS)". Ten programs on 2026-11-03: NSGP, SLCGP, HSGP, EMPG (preparedness); Public Assistance, Individual
Assistance, HMGP, BRIC, FMA, Pre-Disaster Mitigation (recovery).

## Field mapping (Program model in `pipeline/models.py`)

| Program field | Source | Rule |
|---|---|---|
| source_connector | constant | `de_dema` |
| source_id | the link | the anchor (`HSGP`) for preparedness programs; the slug of the link's last path segment for the rest (`hazard-mitigation`, `publicAssistance`) |
| source_url | the link | the DEMA page (`/about/grants/index.shtml?dc=preparednessgrants#HSGP`, `/recovery/publicAssistance/`) or the FEMA page the accordion links |
| external_number | none | null |
| name | the bold link text | as written (`Homeland Security Grant Program (HSGP)`) |
| level / jurisdiction | constant | `state` / `DE` |
| administering_agency | constant | `Delaware Emergency Management Agency` |
| agency_code | constant | `DE-DEMA` |
| funding_type | name, then constant | the shared keyword; else `grant` (the page is titled Grants and every entry is a grant program) |
| funding_source | the page | `pass_through`: the page says the funds come from FEMA and DHS and DEMA is the administrative agency |
| amount / match | none | null |
| status | the Apply paragraph | `unknown`: "annually in the spring", no date |
| closes_at_text | the Apply paragraph | verbatim for the four preparedness programs; null for the rest |
| summary | the blurb | the sentence after the bold link |
| eligibility_text | the preparedness block | the `Eligible Subrecipient` paragraph; null for the recovery entries (a blurb describes what the money does, not who applies) |
| applicant_types | eligibility_text | the shared tagger, sentence by sentence |
| categories | the accordion heading | `Preparedness Grants` and `Recovery Assistance` → public_safety (added to the shared table), the heading as source_code |
| alns | none | empty |

### Status rules

`unknown` throughout: the page states no dates. A record whose link leaves the page is `unknown` (`resolve_missing`
makes no request).

## Decisions

1. **The accordion entries are the records**, not the "Available Grants" sidebar list (which omits Public and
   Individual Assistance). Ten entries, two pages.
2. **`pass_through` for all ten** on the page's own sentence about FEMA and DHS.
3. **Eligibility from the "Eligible Subrecipient" paragraphs only**; HSGP's "[Invitation Only] State and local
   government agencies, tribal entities ..." is recorded with `invitation_only` as Texas does. The recovery entries'
   blurbs describe what the money does and tag nothing.

## Known gaps

- No dates anywhere; every record is `unknown`.
- Recovery programs link to FEMA's pages, which are not read.

## Verification

`tests/test_de_dema.py` against the two saved pages (written by `scripts/probe_de_dema.py`); two live runs.
