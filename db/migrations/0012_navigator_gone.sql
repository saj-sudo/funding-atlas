-- Tombstones (2026-11-28, Saj: T1, the record kept, always). A program a local government could apply to that has
-- had a page but is now on no list keeps a page that says so, so links in emails, feeds and frozen editions never
-- break. Who: the change feed's programs (v_navigator_change's filter: likely or possible, a municipal applicant, any
-- jurisdiction) that are in none of the three listed views. Why it left, from the change log only: when its latest
-- change is 'missing', the source stopped listing it on left_at, with status_before the status it had; otherwise its
-- round closed and aged out of "closed recently" (the deadline is in closes_at). Columns as v_navigator_between, so the
-- same shaping code draws the record. A program listed again leaves this view on the next build.
-- Only programs that can have had a page: pages began with the build of 2026-11-26, so a tombstone needs the program to
-- have left the lists on or after that day, in one of four ways: (a) the source stopped listing it; (b) its status
-- changed from open or announced; (c) it was open with a deadline that has since passed (a federal notice then leaves
-- every list, since only state rounds stay on as "closed recently"); (d) a state round aged out of the 15-month
-- "closed recently" window. Older departures never had a page to link to.

DROP VIEW IF EXISTS v_navigator_gone;
CREATE VIEW v_navigator_gone AS
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
                                                                       AS listings,
       p.last_seen,
       lc.change_type                                                  AS last_change,
       lc.changed_at                                                   AS last_change_at,
       json_extract(lc.changed_fields, '$.status.old')                 AS last_status_old,
       json_extract(lc.changed_fields, '$.status.new')                 AS last_status_new,
       CASE WHEN lc.change_type = 'missing' THEN lc.changed_at END      AS left_at,
       CASE WHEN lc.change_type = 'missing' THEN json_extract(lc.changed_fields, '$.status.old') END
                                                                       AS status_before
FROM program p
JOIN v_municipal_relevance r ON r.program_id = p.id
JOIN program_change lc ON lc.id = (SELECT c.id FROM program_change c WHERE c.program_id = p.id
                                   ORDER BY c.changed_at DESC, c.id DESC LIMIT 1)
WHERE r.municipal_tier IN ('likely', 'possible')
  AND EXISTS (SELECT 1 FROM program_applicant_type a
              WHERE a.program_id = p.id AND a.applicant_type = 'municipality')
  AND p.id NOT IN (SELECT id FROM v_navigator_program)
  AND p.id NOT IN (SELECT id FROM v_navigator_between)
  AND p.id NOT IN (SELECT id FROM v_navigator_unstated)
  AND ((lc.change_type = 'missing' AND lc.changed_at >= '2026-11-26')
       OR (lc.change_type = 'changed' AND lc.changed_at >= '2026-11-26'
           AND json_extract(lc.changed_fields, '$.status.old') IN ('open', 'forecasted'))
       OR (p.status IN ('open', 'forecasted') AND p.closes_at >= '2026-11-26' AND p.closes_at < date('now'))
       OR (p.jurisdiction != 'US' AND p.closes_at >= date('2026-11-26', '-15 months')
           AND p.closes_at < date('now', '-15 months')))
ORDER BY lc.changed_at DESC, p.name;
