-- 0004: the municipal page, as data.
--
-- scripts/export_html.py renders one static HTML page from this view and nothing else, so
-- `sqlite3 atlas.db "SELECT * FROM v_municipal_page"` is the page before styling. It is
-- v_open_for_municipalities (open or forecasted, local governments eligible, US or MD) plus the
-- columns that view leaves out and the junction tables flattened to text.
--
-- The 'unlikely' tier is excluded here on purpose: it is research notices, RFIs and foreign-facing
-- calls, and a reader who sees R01s on a municipal page stops trusting the rest. The export script
-- counts the excluded rows for the footer so the exclusion is visible, not silent.
--
-- days_since_* are integers relative to now; the page decides what counts as "new" or "updated".

DROP VIEW IF EXISTS v_municipal_page;
CREATE VIEW v_municipal_page AS
SELECT o.*,
       p.source_connector,
       p.summary,
       p.eligibility_text,
       p.first_seen,
       CAST(julianday('now') - julianday(p.first_seen)   AS INTEGER) AS days_since_first_seen,
       CAST(julianday('now') - julianday(p.last_changed) AS INTEGER) AS days_since_changed,
       (SELECT GROUP_CONCAT(category, ', ')
          FROM (SELECT DISTINCT category FROM program_category WHERE program_id = p.id ORDER BY category))
                                                                       AS categories,
       (SELECT GROUP_CONCAT(applicant_type, ', ')
          FROM (SELECT DISTINCT applicant_type FROM program_applicant_type WHERE program_id = p.id ORDER BY applicant_type))
                                                                       AS applicant_types,
       (SELECT GROUP_CONCAT(aln || ' · ' || listing_name, char(10))
          FROM (SELECT aln, listing_name FROM v_opportunity_listing
                 WHERE opportunity_id = p.id AND listing_id IS NOT NULL ORDER BY aln))
                                                                       AS listings
FROM v_open_for_municipalities o
JOIN program p ON p.id = o.id
WHERE o.municipal_tier IN ('likely', 'possible')
ORDER BY CASE o.municipal_tier WHEN 'likely' THEN 0 ELSE 1 END,
         o.closes_at IS NULL, o.closes_at, o.name;
