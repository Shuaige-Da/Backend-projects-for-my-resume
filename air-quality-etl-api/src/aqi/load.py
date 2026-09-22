"""PostgreSQL bulk loading with file-level checkpoints and idempotency."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

import pandas as pd
from sqlalchemy import Connection, text

from .extract import SourceFile

STAGE_COLUMNS = (
    "source_row_number",
    "source_site_id",
    "site_name",
    "county",
    "observed_at",
    "aqi",
    "status_code",
    "primary_pollutant",
    "so2",
    "so2_avg",
    "co",
    "co_8hr",
    "o3",
    "o3_8hr",
    "pm10",
    "pm10_avg",
    "pm25",
    "pm25_avg",
    "no2",
    "nox",
    "no",
    "wind_speed",
    "wind_direction",
    "longitude",
    "latitude",
    "quality_flags",
)


@dataclass(frozen=True)
class ImportRegistration:
    id_import_file: int
    status: str
    last_row_number: int


def register_import(conn: Connection, source_file: SourceFile) -> ImportRegistration:
    row = conn.execute(
        text(
            """
            INSERT INTO air_quality.import_file (
                filename, source_month, sha256, size_bytes, status, started_at
            ) VALUES (
                :filename, :source_month, :sha256, :size_bytes, 'RUNNING', NOW()
            )
            ON CONFLICT (sha256) DO UPDATE SET
                filename = EXCLUDED.filename,
                size_bytes = EXCLUDED.size_bytes,
                status = CASE
                    WHEN air_quality.import_file.status = 'COMPLETED' THEN 'COMPLETED'
                    ELSE 'RUNNING'
                END,
                error_message = NULL,
                started_at = CASE
                    WHEN air_quality.import_file.status = 'COMPLETED'
                    THEN air_quality.import_file.started_at
                    ELSE NOW()
                END
            RETURNING id_import_file, status, last_row_number
            """
        ),
        {
            "filename": source_file.path.name,
            "source_month": source_file.month,
            "sha256": source_file.sha256(),
            "size_bytes": source_file.size_bytes,
        },
    ).mappings().one()
    return ImportRegistration(
        id_import_file=row["id_import_file"],
        status=row["status"],
        last_row_number=row["last_row_number"],
    )


def _copy_frame(conn: Connection, table: str, columns: tuple[str, ...], frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    buffer = StringIO()
    frame.loc[:, columns].to_csv(buffer, index=False, header=False, na_rep="\\N")
    buffer.seek(0)
    cursor = conn.connection.cursor()
    try:
        cursor.copy_expert(
            f"COPY {table} ({', '.join(columns)}) FROM STDIN "
            "WITH (FORMAT CSV, NULL '\\N')",
            buffer,
        )
    finally:
        cursor.close()


def _create_temp_tables(conn: Connection) -> None:
    conn.execute(
        text(
            """
            CREATE TEMP TABLE IF NOT EXISTS stage_measurement (
                source_row_number BIGINT,
                source_site_id INTEGER,
                site_name VARCHAR(120),
                county VARCHAR(120),
                observed_at TIMESTAMP,
                aqi SMALLINT,
                status_code VARCHAR(50),
                primary_pollutant VARCHAR(50),
                so2 REAL, so2_avg REAL, co REAL, co_8hr REAL,
                o3 REAL, o3_8hr REAL, pm10 REAL, pm10_avg REAL,
                pm25 REAL, pm25_avg REAL, no2 REAL, nox REAL, no REAL,
                wind_speed REAL, wind_direction REAL,
                longitude DOUBLE PRECISION, latitude DOUBLE PRECISION,
                quality_flags TEXT
            ) ON COMMIT DELETE ROWS;

            CREATE TEMP TABLE IF NOT EXISTS stage_quality_issue (
                source_row_number BIGINT,
                rejection_reason VARCHAR(255)
            ) ON COMMIT DELETE ROWS;

            TRUNCATE stage_measurement, stage_quality_issue;
            """
        )
    )


def load_chunk(
    conn: Connection,
    id_import_file: int,
    accepted: pd.DataFrame,
    rejected: pd.DataFrame,
) -> None:
    """Bulk load one transformed chunk inside the caller's transaction."""
    _create_temp_tables(conn)
    _copy_frame(conn, "stage_measurement", STAGE_COLUMNS, accepted)
    if not rejected.empty:
        _copy_frame(
            conn,
            "stage_quality_issue",
            ("source_row_number", "rejection_reason"),
            rejected,
        )

    conn.execute(
        text(
            """
            INSERT INTO air_quality.station (
                source_site_id, site_name, county, longitude, latitude
            )
            SELECT DISTINCT ON (site_name, county)
                source_site_id, site_name, county, longitude, latitude
            FROM stage_measurement
            ORDER BY site_name, county, observed_at DESC
            ON CONFLICT (site_name, county) DO UPDATE SET
                source_site_id = COALESCE(
                    EXCLUDED.source_site_id,
                    air_quality.station.source_site_id
                ),
                longitude = COALESCE(EXCLUDED.longitude, air_quality.station.longitude),
                latitude = COALESCE(EXCLUDED.latitude, air_quality.station.latitude),
                updated_at = NOW();

            INSERT INTO air_quality.measurement (
                id_station, observed_at, aqi, status_code, primary_pollutant,
                so2, so2_avg, co, co_8hr, o3, o3_8hr,
                pm10, pm10_avg, pm25, pm25_avg, no2, nox, no,
                wind_speed, wind_direction, quality_flags,
                id_import_file, source_row_number
            )
            SELECT
                station.id_station, stage.observed_at, stage.aqi,
                stage.status_code, stage.primary_pollutant,
                stage.so2, stage.so2_avg, stage.co, stage.co_8hr,
                stage.o3, stage.o3_8hr, stage.pm10, stage.pm10_avg,
                stage.pm25, stage.pm25_avg, stage.no2, stage.nox, stage.no,
                stage.wind_speed, stage.wind_direction, stage.quality_flags,
                :id_import_file, stage.source_row_number
            FROM stage_measurement AS stage
            JOIN air_quality.station AS station
              ON station.site_name = stage.site_name
             AND station.county = stage.county
            ON CONFLICT (id_station, observed_at) DO UPDATE SET
                aqi = EXCLUDED.aqi,
                status_code = EXCLUDED.status_code,
                primary_pollutant = EXCLUDED.primary_pollutant,
                so2 = EXCLUDED.so2,
                so2_avg = EXCLUDED.so2_avg,
                co = EXCLUDED.co,
                co_8hr = EXCLUDED.co_8hr,
                o3 = EXCLUDED.o3,
                o3_8hr = EXCLUDED.o3_8hr,
                pm10 = EXCLUDED.pm10,
                pm10_avg = EXCLUDED.pm10_avg,
                pm25 = EXCLUDED.pm25,
                pm25_avg = EXCLUDED.pm25_avg,
                no2 = EXCLUDED.no2,
                nox = EXCLUDED.nox,
                no = EXCLUDED.no,
                wind_speed = EXCLUDED.wind_speed,
                wind_direction = EXCLUDED.wind_direction,
                quality_flags = EXCLUDED.quality_flags,
                id_import_file = EXCLUDED.id_import_file,
                source_row_number = EXCLUDED.source_row_number,
                updated_at = NOW();

            INSERT INTO air_quality.data_quality_issue (
                id_import_file, source_row_number, rejection_reason
            )
            SELECT :id_import_file, source_row_number, rejection_reason
            FROM stage_quality_issue
            ON CONFLICT DO NOTHING;
            """
        ),
        {"id_import_file": id_import_file},
    )

    last_row = 1
    if not accepted.empty:
        last_row = max(last_row, int(accepted["source_row_number"].max()))
    if not rejected.empty:
        last_row = max(last_row, int(rejected["source_row_number"].max()))
    conn.execute(
        text(
            """
            UPDATE air_quality.import_file
            SET total_rows = total_rows + :total_rows,
                accepted_rows = accepted_rows + :accepted_rows,
                rejected_rows = rejected_rows + :rejected_rows,
                last_row_number = GREATEST(last_row_number, :last_row_number)
            WHERE id_import_file = :id_import_file
            """
        ),
        {
            "id_import_file": id_import_file,
            "total_rows": len(accepted) + len(rejected),
            "accepted_rows": len(accepted),
            "rejected_rows": len(rejected),
            "last_row_number": last_row,
        },
    )


def complete_import(conn: Connection, id_import_file: int) -> None:
    conn.execute(
        text(
            """
            UPDATE air_quality.import_file
            SET status = 'COMPLETED', completed_at = NOW(), error_message = NULL
            WHERE id_import_file = :id_import_file
            """
        ),
        {"id_import_file": id_import_file},
    )


def fail_import(conn: Connection, id_import_file: int, message: str) -> None:
    conn.execute(
        text(
            """
            UPDATE air_quality.import_file
            SET status = 'FAILED', error_message = :message
            WHERE id_import_file = :id_import_file
            """
        ),
        {"id_import_file": id_import_file, "message": message[:4000]},
    )
