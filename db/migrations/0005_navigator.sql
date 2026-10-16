-- 0005: the navigator site, as data (milestone 6).
--
-- scripts/build_site.py renders one page per state from these three views and nothing else. They are
-- v_municipal_page generalised to every jurisdiction: the same predicates (open or forecasted, deadline not
-- past, local governments eligible, tier likely or possible), minus the hard-wired `US or MD`. A program's
-- `state` is the first two characters of its jurisdiction ('MD' for 'MD' and 'MD:Baltimore'); federal rows
-- have state NULL and appear on every state's page. The acceptance invariant, checked in
-- tests/test_build_site.py: `WHERE state IS NULL OR state = 'MD'` returns exactly v_municipal_page.
--
-- v_municipal_relevance is untouched. v_municipal_page stays as the Maryland comparison row.

DROP VIEW IF EXISTS v_navigator_program;
CREATE VIEW v_navigator_program AS
SELECT p.id, p.slug, p.name, p.external_number, p.level, p.jurisdiction,
       CASE WHEN p.jurisdiction = 'US' THEN NULL ELSE substr(p.jurisdiction, 1, 2) END AS state,
       p.administering_agency, p.agency_code, p.source_connector,
       p.funding_type, p.funding_source,
       p.status, p.opens_at, p.closes_at, p.closes_at_text, p.rolling,
       p.amount_min, p.amount_max, p.match_required, p.match_pct,
       p.summary, p.eligibility_text, p.source_url,
       p.first_seen, p.last_changed,
       CAST(julianday('now') - julianday(p.first_seen)   AS INTEGER) AS days_since_first_seen,
       CAST(julianday('now') - julianday(p.last_changed) AS INTEGER) AS days_since_changed,
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
WHERE p.status IN ('open', 'forecasted')
  AND (p.closes_at IS NULL OR p.closes_at >= date('now'))
  AND r.municipal_tier IN ('likely', 'possible')
  AND EXISTS (SELECT 1 FROM program_applicant_type a
              WHERE a.program_id = p.id AND a.applicant_type = 'municipality')
ORDER BY CASE r.municipal_tier WHEN 'likely' THEN 0 ELSE 1 END,
         p.closes_at IS NULL, p.closes_at, p.name;

-- The change feed: every logged add / change / vanish on a record a municipality could care about, newest
-- first. No status filter on purpose: a round that just closed is the change a reader most wants to see,
-- and it has left v_navigator_program by definition.
DROP VIEW IF EXISTS v_navigator_change;
CREATE VIEW v_navigator_change AS
SELECT c.id            AS change_id,
       c.run_id,
       c.changed_at,
       c.change_type,
       c.changed_fields,
       p.id            AS program_id,
       p.slug, p.name, p.level, p.jurisdiction,
       CASE WHEN p.jurisdiction = 'US' THEN NULL ELSE substr(p.jurisdiction, 1, 2) END AS state,
       p.administering_agency, p.agency_code, p.source_connector,
       p.status, p.closes_at, p.closes_at_text, p.source_url,
       r.municipal_tier
FROM program_change c
JOIN program p ON p.id = c.program_id
JOIN v_municipal_relevance r ON r.program_id = p.id
WHERE r.municipal_tier IN ('likely', 'possible')
  AND EXISTS (SELECT 1 FROM program_applicant_type a
              WHERE a.program_id = p.id AND a.applicant_type = 'municipality')
ORDER BY c.changed_at DESC, c.id DESC;

-- Coverage per state, stated plainly on the page: how many agencies and records the connectors read for
-- that state (any status), how many of them a town can apply to today, and when the state's sources were
-- last read successfully. A state with no row here has no state sources yet and gets federal rows only.
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
       MAX(l.last_ok)                                               AS last_ok
FROM st
LEFT JOIN last_ok l ON l.connector = st.source_connector
GROUP BY st.state
ORDER BY st.state;
