-- funding-atlas schema v1 (SQLite). Dates are ISO 8601 text: 'YYYY-MM-DD' for dates,
-- 'YYYY-MM-DDTHH:MM:SSZ' for timestamps. Amounts are whole US dollars.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS program (
    id                      INTEGER PRIMARY KEY,
    source_connector        TEXT    NOT NULL,                 -- 'grants_gov'
    source_id               TEXT    NOT NULL,                 -- Grants.gov opportunity id
    source_url              TEXT    NOT NULL,
    external_number         TEXT,                             -- e.g. opportunityNumber
    name                    TEXT    NOT NULL,
    slug                    TEXT    NOT NULL UNIQUE,          -- slugify(name) + '-' + source_id
    level                   TEXT    NOT NULL
        CHECK (level IN ('federal','state','county','city','utility')),
    jurisdiction            TEXT    NOT NULL,                 -- 'US', 'MD', 'MD:Baltimore' ...
    administering_agency    TEXT,
    agency_code             TEXT,
    funding_type            TEXT
        CHECK (funding_type IN ('grant','cooperative_agreement','rebate','loan','tax_credit',
                                'forgivable_loan','formula','voucher','other')),
    funding_source          TEXT    NOT NULL
        CHECK (funding_source IN ('direct','pass_through')),
    parent_program_id       INTEGER REFERENCES program(id),
    amount_min              INTEGER,
    amount_max              INTEGER,
    match_required          INTEGER CHECK (match_required IN (0,1)),   -- NULL = unknown
    match_pct               REAL,
    status                  TEXT    NOT NULL
        CHECK (status IN ('open','forecasted','closed','paused','exhausted','unknown')),
    opens_at                TEXT,
    closes_at               TEXT,
    closes_at_text          TEXT,                             -- verbatim deadline note when no date
    rolling                 INTEGER CHECK (rolling IN (0,1)), -- NULL = unknown
    summary                 TEXT,                             -- source description, HTML stripped
    eligibility_text        TEXT,                             -- verbatim
    eligibility_structured  TEXT,                             -- JSON, NULL in v0.1
    record_hash             TEXT    NOT NULL,
    first_seen              TEXT    NOT NULL,
    last_seen               TEXT    NOT NULL,
    last_changed            TEXT    NOT NULL,
    UNIQUE (source_connector, source_id)
);

CREATE INDEX IF NOT EXISTS ix_program_status   ON program(status);
CREATE INDEX IF NOT EXISTS ix_program_level    ON program(level, jurisdiction);
CREATE INDEX IF NOT EXISTS ix_program_closes   ON program(closes_at);

CREATE TABLE IF NOT EXISTS program_applicant_type (
    program_id      INTEGER NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    applicant_type  TEXT    NOT NULL
        CHECK (applicant_type IN ('municipality','county','state','tribe','special_district',
                                  'school','higher_ed','housing_authority','nonprofit',
                                  'business','household','individual','utility')),
    source_code     TEXT    NOT NULL DEFAULT '',             -- Grants.gov eligibility code
    PRIMARY KEY (program_id, applicant_type, source_code)
);

CREATE TABLE IF NOT EXISTS program_category (
    program_id      INTEGER NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    category        TEXT    NOT NULL
        CHECK (category IN ('infrastructure','housing','energy','water','transportation',
                            'broadband','public_safety','parks','health','workforce','other')),
    source_code     TEXT    NOT NULL DEFAULT '',             -- Grants.gov funding activity code
    PRIMARY KEY (program_id, category, source_code)
);

CREATE TABLE IF NOT EXISTS program_aln (                    -- Assistance Listing Numbers (milestone 2 join key)
    program_id      INTEGER NOT NULL REFERENCES program(id) ON DELETE CASCADE,
    aln             TEXT    NOT NULL,                         -- '93.243'
    PRIMARY KEY (program_id, aln)
);

CREATE TABLE IF NOT EXISTS raw_record (                     -- latest raw payload per source record
    source_connector    TEXT NOT NULL,
    source_id           TEXT NOT NULL,
    fetched_at          TEXT NOT NULL,
    payload             TEXT NOT NULL,                       -- JSON as received (hit + detail)
    PRIMARY KEY (source_connector, source_id)
);

CREATE TABLE IF NOT EXISTS run (
    id              INTEGER PRIMARY KEY,
    connector       TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL CHECK (status IN ('running','ok','failed')),
    fetched_count   INTEGER,
    added_count     INTEGER,
    changed_count   INTEGER,
    missing_count   INTEGER,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS program_change (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES run(id),
    program_id      INTEGER NOT NULL REFERENCES program(id),
    change_type     TEXT    NOT NULL CHECK (change_type IN ('added','changed','missing')),
    old_hash        TEXT,
    new_hash        TEXT,
    changed_fields  TEXT,                                     -- JSON {"field": {"old": .., "new": ..}}
    changed_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_change_run ON program_change(run_id);

-- The v0.1 question: "I am a Maryland municipality, what is open right now?"
CREATE VIEW IF NOT EXISTS v_open_for_municipalities AS
SELECT p.id, p.name, p.level, p.jurisdiction, p.administering_agency, p.funding_type,
       p.status, p.opens_at, p.closes_at, p.closes_at_text, p.rolling,
       p.amount_min, p.amount_max, p.match_required, p.source_url, p.last_changed
FROM program p
WHERE p.status IN ('open','forecasted')
  AND p.jurisdiction IN ('US','MD')
  AND EXISTS (SELECT 1 FROM program_applicant_type a
              WHERE a.program_id = p.id AND a.applicant_type = 'municipality')
ORDER BY p.closes_at IS NULL, p.closes_at;

INSERT OR IGNORE INTO schema_version (version) VALUES (1);
