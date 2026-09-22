CREATE SCHEMA IF NOT EXISTS air_quality;

CREATE TABLE IF NOT EXISTS air_quality.import_file (
    id_import_file BIGSERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    source_month DATE NOT NULL,
    sha256 CHAR(64) NOT NULL UNIQUE,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    total_rows BIGINT NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
    accepted_rows BIGINT NOT NULL DEFAULT 0 CHECK (accepted_rows >= 0),
    rejected_rows BIGINT NOT NULL DEFAULT 0 CHECK (rejected_rows >= 0),
    last_row_number BIGINT NOT NULL DEFAULT 1 CHECK (last_row_number >= 1),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS air_quality.station (
    id_station BIGSERIAL PRIMARY KEY,
    source_site_id INTEGER,
    site_name VARCHAR(120) NOT NULL,
    county VARCHAR(120) NOT NULL,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (site_name, county),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90)
);

-- Source site IDs are not globally stable in the historical exports. For
-- example, ID 310 is associated with different stations in different years.
-- Keep the ID searchable, but use (site_name, county) as the station identity.
ALTER TABLE air_quality.station
    DROP CONSTRAINT IF EXISTS station_source_site_id_key;

CREATE TABLE IF NOT EXISTS air_quality.measurement (
    id_measurement BIGSERIAL PRIMARY KEY,
    id_station BIGINT NOT NULL REFERENCES air_quality.station(id_station),
    observed_at TIMESTAMP NOT NULL,
    aqi SMALLINT CHECK (aqi IS NULL OR aqi BETWEEN 0 AND 500),
    status_code VARCHAR(50),
    primary_pollutant VARCHAR(50),
    so2 REAL,
    so2_avg REAL,
    co REAL,
    co_8hr REAL,
    o3 REAL,
    o3_8hr REAL,
    pm10 REAL,
    pm10_avg REAL,
    pm25 REAL,
    pm25_avg REAL,
    no2 REAL,
    nox REAL,
    no REAL,
    wind_speed REAL,
    wind_direction REAL,
    quality_flags TEXT,
    id_import_file BIGINT NOT NULL REFERENCES air_quality.import_file(id_import_file),
    source_row_number BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_station, observed_at)
);

CREATE TABLE IF NOT EXISTS air_quality.data_quality_issue (
    id_issue BIGSERIAL PRIMARY KEY,
    id_import_file BIGINT NOT NULL REFERENCES air_quality.import_file(id_import_file),
    source_row_number BIGINT NOT NULL,
    rejection_reason VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_import_file, source_row_number, rejection_reason)
);

CREATE INDEX IF NOT EXISTS idx_measurement_observed_at_brin
    ON air_quality.measurement USING BRIN (observed_at);

CREATE INDEX IF NOT EXISTS idx_measurement_station_observed_desc
    ON air_quality.measurement (id_station, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_measurement_aqi
    ON air_quality.measurement (aqi) WHERE aqi IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_station_county
    ON air_quality.station (county);

CREATE INDEX IF NOT EXISTS idx_station_source_site_id
    ON air_quality.station (source_site_id);

CREATE INDEX IF NOT EXISTS idx_quality_issue_import
    ON air_quality.data_quality_issue (id_import_file);
