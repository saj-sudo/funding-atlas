-- 0011: an unrestricted notice is not a targeted one (2026-11-26, design review phase B).
--
-- Grants.gov's code 99 ("Unrestricted") is stored as one source code expanded to every applicant type. The view
-- counts codes to decide breadth, so a 99-only notice counts as 1 and read as targeted: with a municipal category it
-- was tiered 'likely' (DOE notices of intent, FWS grants meant for state or tribal natural resource agencies). 0002's
-- rule is "a municipal category on a targeted notice"; open to anyone is not targeted. `unrestricted` was already a
-- named column; it now keeps such a notice out of 'likely' by category alone. It stays 'possible', as an unrestricted
-- notice with no category always was, and local-government wording still makes any notice 'likely'.
-- The view is 0007's, unchanged except for that one condition.

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
               REGEXP '(?i)\b(local governments?|units? of (general )?local government|municipal\w*|cit(y|ies)|count(y|ies)|towns?|townships?|villages?|boroughs?|political subdivisions?)\b'
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
           WHEN municipal_category AND NOT broad_eligibility
                AND NOT unrestricted                             THEN 'likely'
           WHEN municipal_category OR NOT broad_eligibility      THEN 'possible'
           ELSE                                                       'unlikely'
       END AS municipal_tier
FROM flags;

