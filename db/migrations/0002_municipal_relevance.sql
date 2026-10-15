-- 0002: municipal relevance signal.
--
-- Eligibility codes alone are a weak filter: NIH research notices list city and county governments
-- as eligible, so a plain eligibility query returns ~900 federal records of which most are R01-style
-- research calls. This view adds a second, rule-based signal. Every rule is a named boolean column so
-- the reasoning is auditable in SQL. Nothing here is program data: it is our reading of stored fields.
-- Argue with the rules, not the records.
--
-- Tiers:
--   likely    local-government wording in the source text, or a municipal category on a targeted notice
--   possible  municipal category, or a targeted (not everyone-eligible) notice, with no research marker
--   unlikely  research notice, RFI, foreign-facing agency, or an everyone-eligible notice with no municipal signal

DROP VIEW IF EXISTS v_municipal_relevance;
CREATE VIEW v_municipal_relevance AS
WITH breadth AS (
    SELECT program_id,
           COUNT(DISTINCT source_code)       AS n_applicant_codes,
           MAX(source_code = '02')           AS lists_municipality_code,
           MAX(source_code = '99')           AS unrestricted
    FROM program_applicant_type
    GROUP BY program_id
),
cats AS (
    SELECT program_id,
           MAX(category IN ('infrastructure','housing','energy','water','transportation',
                            'broadband','public_safety','parks')) AS municipal_category
    FROM program_category
    GROUP BY program_id
),
flags AS (
    SELECT p.id                                        AS program_id,
           COALESCE(b.n_applicant_codes, 0)            AS n_applicant_codes,
           COALESCE(b.lists_municipality_code, 0)      AS lists_municipality_code,
           COALESCE(b.unrestricted, 0)                 AS unrestricted,
           COALESCE(b.n_applicant_codes, 0) >= 13      AS broad_eligibility,
           COALESCE(c.municipal_category, 0)           AS municipal_category,
           (p.name || ' ' || COALESCE(p.eligibility_text, '') || ' ' || COALESCE(p.summary, ''))
               REGEXP '(?i)\b(local governments?|units? of (general )?local government|municipal\w*|cit(y|ies)|count(y|ies)|towns?|townships?|villages?|boroughs?)\b'
                                                       AS local_gov_wording,
           (   p.name REGEXP '\((?!FY)[A-Z]{1,2}\d\d'          -- NIH activity code: (R01 ..., (U54 ..., (P30 ...
            OR p.name REGEXP '(?i)clinical trial'
            OR p.name REGEXP '(?i)broad agency announcement|\bBAA\b'
            OR p.agency_code LIKE 'HHS-NIH%'
            OR p.agency_code LIKE 'NSF%'
            OR p.agency_code = 'DOD-AMRAA'                       -- CDMRP medical research
            OR p.agency_code LIKE 'DOD-AFRL%'                    -- DOD research labs and basic-research sponsors
            OR p.agency_code LIKE 'DOD-ONR%'
            OR p.agency_code LIKE 'DOD-DTRA%'
            OR p.agency_code LIKE 'DOD-DARPA%'
            OR p.agency_code LIKE 'DOD-USAFA%'
            OR p.agency_code LIKE 'NASA%'
            OR p.agency_code = 'PAMS-SC'                         -- DOE Office of Science
            OR p.agency_code LIKE 'DOE-ARPAE%'
           )                                           AS research_notice,
           (   p.agency_code LIKE 'DOS-%'                        -- State Department: overseas programs
            OR p.agency_code LIKE 'MCC%'                         -- Millennium Challenge Corporation
            OR p.agency_code LIKE 'USAID%'
           )                                           AS foreign_facing,
           p.name REGEXP '(?i)^request for information' AS not_an_opportunity
    FROM program p
    LEFT JOIN breadth b ON b.program_id = p.id
    LEFT JOIN cats    c ON c.program_id = p.id
)
SELECT *,
       CASE
           WHEN not_an_opportunity OR research_notice OR foreign_facing THEN 'unlikely'
           WHEN local_gov_wording                                THEN 'likely'
           WHEN municipal_category AND NOT broad_eligibility     THEN 'likely'
           WHEN municipal_category OR NOT broad_eligibility      THEN 'possible'
           ELSE                                                       'unlikely'
       END AS municipal_tier
FROM flags;

-- Re-point the v0.1 question at the signal.
DROP VIEW IF EXISTS v_open_for_municipalities;
CREATE VIEW v_open_for_municipalities AS
SELECT p.id, p.name, p.level, p.jurisdiction, p.administering_agency, p.agency_code, p.funding_type,
       p.status, p.opens_at, p.closes_at, p.closes_at_text, p.rolling,
       p.amount_min, p.amount_max, p.match_required, p.source_url, p.last_changed,
       r.municipal_tier, r.local_gov_wording, r.municipal_category, r.research_notice, r.foreign_facing, r.broad_eligibility
FROM program p
JOIN v_municipal_relevance r ON r.program_id = p.id
WHERE p.status IN ('open', 'forecasted')
  AND (p.closes_at IS NULL OR p.closes_at >= date('now'))   -- source may still say "posted" years after the deadline
  AND p.jurisdiction IN ('US', 'MD')
  AND EXISTS (SELECT 1 FROM program_applicant_type a
              WHERE a.program_id = p.id AND a.applicant_type = 'municipality')
ORDER BY CASE r.municipal_tier WHEN 'likely' THEN 0 WHEN 'possible' THEN 1 ELSE 2 END,
         p.closes_at IS NULL, p.closes_at;
