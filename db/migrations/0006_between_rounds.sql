-- 0006: between rounds (milestone 7.1).
--
-- The state page shows what a town can apply to now or soon (v_navigator_program). In October that hides the
-- rows a town needs months ahead: CDBG, the Technical Assistance Grant, L-GEM, Community Parks and Playgrounds,
-- MHT's annual grants. This view is the appendix to that page: state programs for local governments that are
-- closed, exhausted, past their stated deadline, or unknown with a dated past deadline, within 15 months of
-- that deadline (undated closed rows stay while the source still lists the page; a vanished page becomes
-- `unknown` without a date through resolve_missing and drops out).
--
-- Nothing here is a forecast. `closes_at` is the deadline the source last stated, `closes_at_text` is the
-- source's own wording about its cycle, and `last_reopened` is the last time the change log saw this record
-- flip to open or forecasted: an observation, null until it has happened.
--
-- Federal rows are excluded on purpose. Grants.gov closes a notice with a real date when it leaves the search,
-- so a closed-with-date rule would put hundreds of one-off notices on all 51 pages; the recurring thing in the
-- federal world is the Assistance Listing, not the notice.
--
-- v_navigator_coverage is recreated with one more column, n_between_rounds; v_navigator_program is untouched,
-- so the acceptance invariant of 0005 still holds.

DROP VIEW IF EXISTS v_navigator_between;
CREATE VIEW v_navigator_between AS
SELECT p.id, p.slug, p.name, p.external_number, p.level, p.jurisdiction,
       substr(p.jurisdiction, 1, 2) AS state,
       p.administering_agency, p.agency_code, p.source_connector,
       p.funding_type, p.funding_source,
       p.status, p.opens_at, p.closes_at, p.closes_at_text, p.rolling,
       p.amount_min, p.amount_max, p.match_required, p.match_pct,
       p.summary, p.eligibility_text, p.source_url,
       p.first_seen, p.last_changed,
       CAST(julianday('now') - julianday(p.first_seen)   AS INTEGER) AS days_since_first_seen,
       CAST(julianday('now') - julianday(p.last_changed) AS INTEGER) AS days_since_changed,
       CAST(julianday('now') - julianday(p.closes_at)    AS INTEGER) AS days_since_deadline,
       (SELECT MAX(c.changed_at) FROM program_change c
         WHERE c.program_id = p.id AND c.change_type = 'changed'
           AND json_extract(c.changed_fields, '$.status.new') IN ('open', 'forecasted'))
                                                                       AS last_reopened,
       r.municipal_tier,
       (SELECT GROUP_CONCAT(category, ', ')
          FROM (SELECT DISTINCT category FROM program_category WHERE program_id = p.id ORDER BY category))
                                                                       AS categories,
       (SELECT GROUP_CONCAT(applicant_type, ', ')
          FROM (SELECT DISTINCT applicant_type FROM program_applicant_type WHERE program_id = p.id ORDER BY applicant_type))
                                                                       AS applicant_types,
       (SELECT GROUP_CONCAT(aln, ', ')
          FROM (SELECT aln FROM program_aln WHERE program_id = p.id ORDER BY aln))
                                                                       AS alns,
       (SELECT GROUP_CONCAT(aln || ' · ' || listing_name, char(10))
          FROM (SELECT aln, listing_name FROM v_opportunity_listing
                 WHERE opportunity_id = p.id AND listing_id IS NOT NULL ORDER BY aln))
                                                                       AS listings
FROM program p
JOIN v_municipal_relevance r ON r.program_id = p.id
WHERE p.jurisdiction != 'US'
  AND r.municipal_tier IN ('likely', 'possible')
  AND EXISTS (SELECT 1 FROM program_applicant_type a
              WHERE a.program_id = p.id AND a.applicant_type = 'municipality')
  AND NOT (p.status IN ('open', 'forecasted')
           AND (p.closes_at IS NULL OR p.closes_at >= date('now')))      -- not already on the page
  AND (p.status != 'unknown' OR p.closes_at IS NOT NULL)                 -- unknown counts only with a dated deadline
  AND (p.closes_at IS NULL OR p.closes_at >= date('now', '-15 months'))
ORDER BY p.closes_at IS NULL, p.closes_at DESC, p.name;

DROP VIEW IF EXISTS v_navigator_coverage;
CREATE VIEW v_navigator_coverage AS
WITH st AS (
    SELECT p.id, substr(p.jurisdiction, 1, 2) AS state, p.administering_agency, p.source_connector
    FROM program p
    WHERE p.jurisdiction != 'US'
),
last_ok AS (
    SELECT connector, MAX(CASE WHEN status = 'ok' THEN finished_at END) AS last_ok
    FROM run GROUP BY connector
)
SELECT st.state,
       COUNT(DISTINCT st.administering_agency)                      AS n_agencies,
       COUNT(DISTINCT st.source_connector)                          AS n_connectors,
       COUNT(*)                                                     AS n_programs,
       (SELECT COUNT(*) FROM v_navigator_program n WHERE n.state = st.state) AS n_open_municipal,
       (SELECT COUNT(*) FROM v_navigator_between b WHERE b.state = st.state) AS n_between_rounds,
       MAX(l.last_ok)                                               AS last_ok
FROM st
LEFT JOIN last_ok l ON l.connector = st.source_connector
GROUP BY st.state
ORDER BY st.state;
