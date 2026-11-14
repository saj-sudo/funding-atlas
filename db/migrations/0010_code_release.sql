-- 0010: was a change the source's, or ours? (milestone 13.15, 2026-11-14)
--
-- The change log records that a record changed, not why. Most changes are the agency editing its page; some are this
-- repository changing how a source is read (a new date rule, a tagger phrase, a split). Both are real changes to the
-- record, and the log has to keep both, but a reader asking "did the agency change this?" deserves to know which
-- runs followed a code change.
--
-- code_release holds, per connector, every commit on main that touched a file deciding how that connector reads
-- (its module, the shared readers it imports, and the pipeline's upsert and model code). `cli.py code-releases`
-- refills it from git on every daily run; it is facts from git history, not inference.
--
-- v_change_cause labels each logged change:
--   first_read  the connector's first successful run (everything is new to the registry)
--   code        a code release for this connector landed between the previous successful run and this one, so the
--               change may come from how the source is read; it may also be the agency's: the log cannot tell
--   source      no code release in between: the change came from the source
--   unknown     code_release is empty (a database built without git history)

CREATE TABLE IF NOT EXISTS code_release (
    connector   TEXT NOT NULL,
    sha         TEXT NOT NULL,
    released_at TEXT NOT NULL,
    PRIMARY KEY (connector, sha)
);

DROP VIEW IF EXISTS v_change_cause;
CREATE VIEW v_change_cause AS
WITH runs AS (
    SELECT r.id, r.connector, r.started_at,
           (SELECT MAX(p.started_at) FROM run p
             WHERE p.connector = r.connector AND p.status = 'ok' AND p.started_at < r.started_at) AS prev_started
    FROM run r
)
SELECT c.id AS change_id,
       CASE
         WHEN NOT EXISTS (SELECT 1 FROM code_release) THEN 'unknown'
         WHEN runs.prev_started IS NULL THEN 'first_read'
         WHEN EXISTS (SELECT 1 FROM code_release k
                       WHERE k.connector = runs.connector
                         AND k.released_at > runs.prev_started AND k.released_at <= runs.started_at) THEN 'code'
         ELSE 'source'
       END AS cause
FROM program_change c
JOIN runs ON runs.id = c.run_id;

-- The status-changes chart, split by cause (replaces 0009's view; same columns plus `cause`).
DROP VIEW IF EXISTS v_stats_status_flips;
CREATE VIEW v_stats_status_flips AS
SELECT json_extract(n.changed_fields, '$.status.old') AS old_status,
       json_extract(n.changed_fields, '$.status.new') AS new_status,
       v.cause                                         AS cause,
       COUNT(*)                                        AS n,
       MIN(n.changed_at)                               AS first_at,
       MAX(n.changed_at)                               AS last_at
FROM v_navigator_change n
JOIN v_change_cause v ON v.change_id = n.change_id
WHERE n.change_type = 'changed' AND json_extract(n.changed_fields, '$.status') IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY n DESC;
