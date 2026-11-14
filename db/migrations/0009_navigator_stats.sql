-- 0009: the numbers behind the site's charts (milestone 13.14, 2026-11-14).
--
-- Three views, each a plain count over records the navigator already lists or could list (tier likely or possible,
-- the `municipality` applicant tag). The charts draw them as they are; nothing here estimates or forecasts.
--
-- v_stats_deadline_month: the month of year of every stated deadline of an eligible state program, any status,
--   within two years either side of today, placeholders (five years out or more) left out. Read as "when this
--   state's deadlines have fallen", never as "when the next one will".
-- v_stats_stated: per state, how many eligible state programs state a status, a deadline (or rolling), an amount;
--   plus one row 'US' for the federal notices open or announced now. It measures the sources, not the programs.
-- v_stats_status_flips: every logged status change on a listed-eligible record, old to new, all time.

DROP VIEW IF EXISTS v_stats_deadline_month;
CREATE VIEW v_stats_deadline_month AS
SELECT substr(p.jurisdiction, 1, 2)          AS state,
       CAST(substr(p.closes_at, 6, 2) AS INTEGER) AS month,
       COUNT(*)                              AS n
FROM program p
JOIN v_municipal_relevance r ON r.program_id = p.id
WHERE p.jurisdiction != 'US'
  AND r.municipal_tier IN ('likely', 'possible')
  AND EXISTS (SELECT 1 FROM program_applicant_type a WHERE a.program_id = p.id AND a.applicant_type = 'municipality')
  AND p.closes_at >= date('now', '-2 years')
  AND p.closes_at <= date('now', '+2 years')
GROUP BY 1, 2
ORDER BY 1, 2;

DROP VIEW IF EXISTS v_stats_stated;
CREATE VIEW v_stats_stated AS
SELECT substr(p.jurisdiction, 1, 2)                                   AS state,
       COUNT(*)                                                       AS n,
       SUM(p.status != 'unknown')                                     AS status_stated,
       SUM(p.closes_at IS NOT NULL OR p.rolling = 1)                  AS date_stated,
       SUM(p.amount_max IS NOT NULL OR p.amount_min IS NOT NULL)      AS amount_stated
FROM program p
JOIN v_municipal_relevance r ON r.program_id = p.id
WHERE p.jurisdiction != 'US'
  AND r.municipal_tier IN ('likely', 'possible')
  AND EXISTS (SELECT 1 FROM program_applicant_type a WHERE a.program_id = p.id AND a.applicant_type = 'municipality')
GROUP BY 1
UNION ALL
SELECT 'US', COUNT(*), SUM(status != 'unknown'), SUM(closes_at IS NOT NULL OR rolling = 1),
       SUM(amount_max IS NOT NULL OR amount_min IS NOT NULL)
FROM v_navigator_program
WHERE state IS NULL;

DROP VIEW IF EXISTS v_stats_status_flips;
CREATE VIEW v_stats_status_flips AS
SELECT json_extract(changed_fields, '$.status.old') AS old_status,
       json_extract(changed_fields, '$.status.new') AS new_status,
       COUNT(*)                                     AS n,
       MIN(changed_at)                              AS first_at,
       MAX(changed_at)                              AS last_at
FROM v_navigator_change
WHERE change_type = 'changed' AND json_extract(changed_fields, '$.status') IS NOT NULL
GROUP BY 1, 2
ORDER BY n DESC;
