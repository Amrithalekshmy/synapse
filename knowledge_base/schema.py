"""
PostgreSQL + pgvector schema for the SYNAPSE Knowledge Base.
Adithyagopan's module — strong version database layer.

Run this file directly to print DDL or create schema with psycopg2:

    python -m knowledge_base.schema
    python -m knowledge_base.schema --dsn "postgresql://user:pass@host/dbname"

Tables
------
  historical_records   — main store (one row per completed activity)
  kb_embeddings        — pgvector embedding per record for semantic search
  delay_cause_log      — denormalised delay-cause log for fast aggregation

Analytical views
----------------
  v_delay_by_discipline     — delay frequency per discipline
  v_top_delay_causes        — ranked delay causes per discipline
  v_activities_over_baseline — activity types that exceed planned duration
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# DDL statements
# ---------------------------------------------------------------------------

HISTORICAL_RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS historical_records (
    record_id               VARCHAR(64)  PRIMARY KEY,
    project_id              VARCHAR(64)  NOT NULL,
    activity_id             VARCHAR(64),
    activity_description    TEXT         NOT NULL,

    discipline              VARCHAR(64)  NOT NULL DEFAULT 'unknown',
    activity_type           VARCHAR(128),
    location_type           VARCHAR(64),

    planned_start           DATE,
    planned_finish          DATE,
    actual_start            DATE,
    actual_finish           DATE,

    planned_duration_days   INTEGER      DEFAULT 0,
    actual_duration_days    INTEGER      DEFAULT 0,
    variance_days           INTEGER      DEFAULT 0,

    delayed                 BOOLEAN      DEFAULT FALSE,
    delay_cause             TEXT,

    productivity_rate       NUMERIC(10,4),
    productivity_unit       VARCHAR(64),

    source_reference        TEXT,
    match_confidence        NUMERIC(5,4),
    reviewer_status         VARCHAR(32),
    record_quality          VARCHAR(32)  NOT NULL DEFAULT 'provisional'
                            CHECK (record_quality IN ('verified','provisional','rejected')),

    created_at              TIMESTAMPTZ  DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hr_discipline_quality
    ON historical_records (discipline, record_quality);
CREATE INDEX IF NOT EXISTS idx_hr_project
    ON historical_records (project_id);
CREATE INDEX IF NOT EXISTS idx_hr_activity_type
    ON historical_records (activity_type);
CREATE INDEX IF NOT EXISTS idx_hr_delayed
    ON historical_records (delayed) WHERE delayed = TRUE;
"""

KB_EMBEDDINGS_DDL = """
-- Requires: CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS kb_embeddings (
    record_id   VARCHAR(64) PRIMARY KEY
                REFERENCES historical_records(record_id) ON DELETE CASCADE,
    embedding   VECTOR(384),          -- 384-dim for all-MiniLM-L6-v2
    model_name  VARCHAR(128) DEFAULT 'all-MiniLM-L6-v2',
    indexed_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- HNSW index for fast approximate nearest-neighbour search
CREATE INDEX IF NOT EXISTS idx_kb_emb_hnsw
    ON kb_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
"""

DELAY_CAUSE_LOG_DDL = """
CREATE TABLE IF NOT EXISTS delay_cause_log (
    id          BIGSERIAL   PRIMARY KEY,
    record_id   VARCHAR(64) NOT NULL
                REFERENCES historical_records(record_id) ON DELETE CASCADE,
    discipline  VARCHAR(64),
    cause       TEXT        NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dcl_discipline ON delay_cause_log (discipline);
CREATE INDEX IF NOT EXISTS idx_dcl_cause      ON delay_cause_log (cause);
"""

VIEWS_DDL = """
CREATE OR REPLACE VIEW v_delay_by_discipline AS
SELECT
    discipline,
    COUNT(*)                                                AS total,
    SUM(CASE WHEN delayed THEN 1 ELSE 0 END)               AS n_delayed,
    ROUND(
        SUM(CASE WHEN delayed THEN 1 ELSE 0 END)::NUMERIC
        / NULLIF(COUNT(*), 0), 3
    )                                                       AS delay_frequency,
    ROUND(AVG(variance_days), 2)                           AS avg_variance_days,
    ROUND(AVG(planned_duration_days), 2)                   AS avg_planned_days,
    ROUND(AVG(actual_duration_days), 2)                    AS avg_actual_days
FROM  historical_records
WHERE record_quality = 'verified'
GROUP BY discipline
ORDER BY delay_frequency DESC;


CREATE OR REPLACE VIEW v_top_delay_causes AS
SELECT
    discipline,
    delay_cause,
    COUNT(*)                                AS cause_count,
    ROUND(
        COUNT(*)::NUMERIC
        / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY discipline), 0), 3
    )                                       AS frequency
FROM  historical_records
WHERE delayed = TRUE
  AND delay_cause IS NOT NULL
  AND record_quality = 'verified'
GROUP BY discipline, delay_cause
ORDER BY discipline, cause_count DESC;


CREATE OR REPLACE VIEW v_activities_over_baseline AS
SELECT
    discipline,
    activity_type,
    COUNT(*)                         AS sample_count,
    ROUND(AVG(variance_days), 2)     AS avg_variance_days,
    MAX(variance_days)               AS worst_variance,
    ROUND(
        SUM(CASE WHEN delayed THEN 1 ELSE 0 END)::NUMERIC
        / NULLIF(COUNT(*), 0), 3
    )                                AS delay_frequency
FROM  historical_records
WHERE record_quality = 'verified'
GROUP BY discipline, activity_type
HAVING AVG(variance_days) >= 2
ORDER BY avg_variance_days DESC;
"""

# pgvector semantic search template
SEMANTIC_SEARCH_SQL = """
SELECT
    hr.record_id,
    hr.activity_description,
    hr.discipline,
    hr.activity_type,
    hr.variance_days,
    hr.delayed,
    hr.delay_cause,
    1 - (ke.embedding <=> $1::vector) AS cosine_similarity
FROM  kb_embeddings ke
JOIN  historical_records hr USING (record_id)
WHERE hr.record_quality = 'verified'
  AND ($2::text IS NULL OR hr.discipline = $2)
ORDER BY cosine_similarity DESC
LIMIT $3;
"""

# ---------------------------------------------------------------------------
# Helper: create all tables
# ---------------------------------------------------------------------------

def create_schema(conn) -> None:
    """
    Create all tables using a psycopg2 connection.

    Parameters
    ----------
    conn : psycopg2 connection
    """
    cur = conn.cursor()
    for ddl in [HISTORICAL_RECORDS_DDL, KB_EMBEDDINGS_DDL, DELAY_CAUSE_LOG_DDL, VIEWS_DDL]:
        cur.execute(ddl)
    conn.commit()
    print("Knowledge Base schema created successfully.")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create SYNAPSE Knowledge Base PostgreSQL schema"
    )
    parser.add_argument(
        "--dsn", default=None,
        help="PostgreSQL DSN e.g. postgresql://user:pass@host/db. "
             "Omit to print DDL only."
    )
    args = parser.parse_args()

    if args.dsn:
        try:
            import psycopg2
            conn = psycopg2.connect(args.dsn)
            create_schema(conn)
            conn.close()
        except ImportError:
            print("psycopg2 not installed. Printing DDL instead.\n")
            for ddl in [HISTORICAL_RECORDS_DDL, KB_EMBEDDINGS_DDL, DELAY_CAUSE_LOG_DDL, VIEWS_DDL]:
                print(ddl)
    else:
        print("# SYNAPSE Knowledge Base — PostgreSQL DDL\n")
        for ddl in [HISTORICAL_RECORDS_DDL, KB_EMBEDDINGS_DDL, DELAY_CAUSE_LOG_DDL, VIEWS_DDL]:
            print(ddl)
