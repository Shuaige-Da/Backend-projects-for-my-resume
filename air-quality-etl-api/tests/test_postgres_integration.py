import os
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from src.aqi.constants import SOURCE_COLUMNS
from src.aqi.extract import SourceFile
from src.aqi.load import complete_import, load_chunk, register_import
from src.aqi.transform import transform_air_quality_chunk


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


@pytest.fixture()
def engine():
    db_engine = create_engine(TEST_DATABASE_URL)
    schema_sql = (Path(__file__).parents[1] / "sql" / "schema.sql").read_text(
        encoding="utf-8"
    )
    with db_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS air_quality CASCADE"))
        conn.execute(text(schema_sql))
    yield db_engine
    with db_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS air_quality CASCADE"))
    db_engine.dispose()


def _raw_frame():
    def row(**overrides):
        value = {column: None for column in SOURCE_COLUMNS}
        value.update(
            sitename="麥寮",
            county="雲林縣",
            aqi="49",
            status="良好",
            datacreationdate="2024-01-01 00:00",
            longitude="120.251825",
            latitude="23.753506",
            siteid="83",
        )
        value.update(overrides)
        return value

    frame = pd.DataFrame(
        [
            row(),
            row(sitename="Mailiao", county="Yunlin County", status="Good"),
            row(sitename=None, datacreationdate="bad"),
        ]
    )
    frame.insert(0, "source_file", "aqi_2024_01.csv")
    frame.insert(1, "source_row_number", [2, 3, 4])
    return frame


def test_register_copy_upsert_and_complete(engine, tmp_path: Path):
    source_path = tmp_path / "aqi_2024_01.csv"
    source_path.write_text("fixture", encoding="utf-8")
    source = SourceFile(source_path, date(2024, 1, 1), source_path.stat().st_size)
    transformed = transform_air_quality_chunk(_raw_frame())

    with engine.begin() as conn:
        registration = register_import(conn, source)
        load_chunk(
            conn,
            registration.id_import_file,
            transformed.accepted,
            transformed.rejected,
        )
        complete_import(conn, registration.id_import_file)

    with engine.connect() as conn:
        station_count = conn.execute(
            text("SELECT COUNT(*) FROM air_quality.station")
        ).scalar_one()
        measurement_count = conn.execute(
            text("SELECT COUNT(*) FROM air_quality.measurement")
        ).scalar_one()
        issue_count = conn.execute(
            text("SELECT COUNT(*) FROM air_quality.data_quality_issue")
        ).scalar_one()
        imported = conn.execute(
            text(
                "SELECT status, total_rows, accepted_rows, rejected_rows "
                "FROM air_quality.import_file"
            )
        ).one()

    assert station_count == 1
    assert measurement_count == 1
    assert issue_count == 2
    assert tuple(imported) == ("COMPLETED", 3, 1, 2)


def test_reused_source_id_does_not_merge_distinct_stations(engine, tmp_path: Path):
    source_path = tmp_path / "aqi_2020_04.csv"
    source_path.write_text("fixture", encoding="utf-8")
    source = SourceFile(source_path, date(2020, 4, 1), source_path.stat().st_size)

    rows = []
    for row_number, site_name, county, observed_at in (
        (2, "高雄(楠梓)", "高雄市", "2019-01-01 00:00"),
        (3, "臺南(北門)", "臺南市", "2020-04-01 00:00"),
    ):
        row = {column: None for column in SOURCE_COLUMNS}
        row.update(
            sitename=site_name,
            county=county,
            aqi="50",
            status="良好",
            datacreationdate=observed_at,
            siteid="310",
        )
        row["source_file"] = source_path.name
        row["source_row_number"] = row_number
        rows.append(row)
    transformed = transform_air_quality_chunk(pd.DataFrame(rows))

    with engine.begin() as conn:
        registration = register_import(conn, source)
        load_chunk(
            conn,
            registration.id_import_file,
            transformed.accepted,
            transformed.rejected,
        )
        complete_import(conn, registration.id_import_file)

    with engine.connect() as conn:
        stations = conn.execute(
            text(
                "SELECT site_name, county, source_site_id "
                "FROM air_quality.station ORDER BY site_name"
            )
        ).all()
        measurement_count = conn.execute(
            text("SELECT COUNT(*) FROM air_quality.measurement")
        ).scalar_one()

    assert len(stations) == 2
    assert {row.source_site_id for row in stations} == {310}
    assert measurement_count == 2
