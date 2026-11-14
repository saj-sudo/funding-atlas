-- 0008: status not confirmed (milestone 13.1, decision 2026-11-14).
--
-- A state program a town is eligible for appeared on its state page only when its source said it was open or
-- forecasted (v_navigator_program) or gave a deadline (v_navigator_between). A program page that states no status
-- and no date (`unknown`, closes_at NULL) appeared nowhere: 84 rows on 2026-11-14, 24 of them Virginia's, so
-- Virginia's page listed no state program at all. Saj's call (2026-11-14): show them, labeled for what they are.
--
-- This view is that group. Same columns and the same eligibility predicates as v_navigator_between (tier likely or
-- possible, the `municipality` applicant tag, state rows only), and the one status rule that view leaves out:
-- `unknown` with no stated deadline. Nothing is inferred: the page says the source does not state a status and
-- shows the source's own cycle wording when it has some. Together the three views partition every eligible state
-- row that is current or recent; what is left out is closed rows more than 15 months past their deadline.
--
-- Ordered with the rows that carry cycle wording first (the most useful to a reader), then by name.
-- v_navigator_coverage is recreated with one more column, n_unstated; nothing else changes.

DROP VIEW IF EXISTS v_navigator_unstated;
CREATE VIEW v_navigator_unstated AS
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
  AND p.status = 'unknown'
  AND p.closes_at IS NULL
ORDER BY COALESCE(p.closes_at_text, '') = '', p.name;

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
       (SELECT COUNT(*) FROM v_navigator_unstated u WHERE u.state = st.state) AS n_unstated,
       MAX(l.last_ok)                                               AS last_ok
FROM st
LEFT JOIN last_ok l ON l.connector = st.source_connector
GROUP BY st.state
ORDER BY st.state;
