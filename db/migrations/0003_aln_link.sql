-- 0003: link opportunities to the programs underneath them by Assistance Listing Number.
--
-- Grants.gov rows are notices (NOFOs). SAM.gov Assistance Listings are the stable programs they draw on,
-- stored by connectors/sam_assistance_listings.py as program rows with source_id = the listing number
-- ('97.106') and status 'unknown' (a catalog entry has no application window of its own; 'closed' once
-- SAM marks it inactive). The join key is program_aln.aln on the opportunity side against the listing's
-- source_id. parent_program_id is NOT used for this: it is single-valued and reserved for pass-through
-- lineage, while an opportunity can cite up to ~20 listings.

DROP VIEW IF EXISTS v_opportunity_listing;
CREATE VIEW v_opportunity_listing AS
SELECT o.id                    AS opportunity_id,
       o.source_connector      AS opportunity_connector,
       o.name                  AS opportunity_name,
       o.status                AS opportunity_status,
       o.closes_at             AS opportunity_closes_at,
       a.aln,
       l.id                    AS listing_id,
       l.name                  AS listing_name,
       l.administering_agency  AS listing_agency,
       l.funding_type          AS listing_funding_type,
       l.amount_min            AS listing_amount_min,
       l.amount_max            AS listing_amount_max,
       l.match_required        AS listing_match_required,
       l.status                AS listing_status,
       l.source_url            AS listing_url
FROM program_aln a
JOIN program o ON o.id = a.program_id AND o.source_connector != 'sam_assistance_listings'
LEFT JOIN program l ON l.source_connector = 'sam_assistance_listings' AND l.source_id = a.aln;

-- How well the two sources line up, per opportunity connector. The unmatched count is the acceptance test.
DROP VIEW IF EXISTS v_aln_coverage;
CREATE VIEW v_aln_coverage AS
WITH per_opp AS (
    SELECT opportunity_connector,
           opportunity_id,
           COUNT(*)                            AS n_alns,
           SUM(listing_id IS NOT NULL)         AS n_matched
    FROM v_opportunity_listing
    GROUP BY opportunity_connector, opportunity_id
)
SELECT opportunity_connector,
       COUNT(*)                                     AS opportunities_with_alns,
       SUM(n_matched = n_alns)                      AS all_matched,
       SUM(n_matched > 0 AND n_matched < n_alns)    AS some_matched,
       SUM(n_matched = 0)                           AS none_matched,
       SUM(n_alns)                                  AS aln_refs,
       SUM(n_alns - n_matched)                      AS aln_refs_unmatched
FROM per_opp
GROUP BY opportunity_connector;
