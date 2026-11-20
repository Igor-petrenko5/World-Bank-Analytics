
BEGIN;

-- 1. Schemas

CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE SCHEMA IF NOT EXISTS marts;


-- 2. Countries

CREATE TABLE IF NOT EXISTS warehouse.dim_countries (
    country_id VARCHAR(10) PRIMARY KEY,
    iso2_code VARCHAR(5),
    country_name TEXT NOT NULL,
    region_id VARCHAR(10),
    region_name TEXT,
    income_level TEXT,
    capital_city TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    is_aggregate BOOLEAN NOT NULL DEFAULT FALSE
);


-- 3. Indicators

CREATE TABLE IF NOT EXISTS warehouse.dim_indicators (
    indicator_code VARCHAR(50) PRIMARY KEY,
    indicator_name TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    unit TEXT NOT NULL,
    description TEXT
);


-- 4. Years

CREATE TABLE IF NOT EXISTS warehouse.dim_years (
    year SMALLINT PRIMARY KEY,
    CHECK (year BETWEEN 1960 AND 2100)
);


-- 5. ETL monitoring

CREATE TABLE IF NOT EXISTS monitoring.etl_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL,
    total_rows INTEGER,
    error_message TEXT,
    CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);


-- 6. Main fact table

CREATE TABLE IF NOT EXISTS warehouse.fact_indicators (
    country_id VARCHAR(10) NOT NULL,
    indicator_code VARCHAR(50) NOT NULL,
    year SMALLINT NOT NULL,
    source_id INTEGER NOT NULL DEFAULT 2,
    value NUMERIC,
    obs_status TEXT,
    source_updated_at DATE,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_id VARCHAR(100) NOT NULL,

    PRIMARY KEY (
        country_id,
        indicator_code,
        year,
        source_id
    ),

    FOREIGN KEY (country_id)
        REFERENCES warehouse.dim_countries(country_id),

    FOREIGN KEY (indicator_code)
        REFERENCES warehouse.dim_indicators(indicator_code),

    FOREIGN KEY (year)
        REFERENCES warehouse.dim_years(year),

    FOREIGN KEY (run_id)
        REFERENCES monitoring.etl_runs(run_id)
);


-- 7. History

CREATE TABLE IF NOT EXISTS warehouse.fact_indicator_history (
    history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country_id VARCHAR(10) NOT NULL,
    indicator_code VARCHAR(50) NOT NULL,
    year SMALLINT NOT NULL,
    source_id INTEGER NOT NULL,
    old_value NUMERIC,
    new_value NUMERIC,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_updated_at DATE,
    run_id VARCHAR(100) NOT NULL
        REFERENCES monitoring.etl_runs(run_id)
);


-- 8. Quality monitoring

CREATE TABLE IF NOT EXISTS monitoring.quality_checks (
    check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL
        REFERENCES monitoring.etl_runs(run_id),
    check_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    actual_value NUMERIC,
    expected_value NUMERIC,
    details TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (status IN ('PASS', 'FAIL', 'WARNING'))
);


-- 9. Indexes

CREATE INDEX IF NOT EXISTS idx_fact_indicator_year
ON warehouse.fact_indicators(indicator_code, year);

CREATE INDEX IF NOT EXISTS idx_fact_country_year
ON warehouse.fact_indicators(country_id, year);


-- 10. Fill years

INSERT INTO warehouse.dim_years(year)
SELECT generate_series(2000, 2025)
ON CONFLICT (year) DO NOTHING;


-- Commit transaction

COMMIT;
