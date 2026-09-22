from io import StringIO

import pandas as pd

from src.aqi.constants import SOURCE_COLUMNS
from src.aqi.load import STAGE_COLUMNS, _copy_frame
from src.aqi.transform import transform_air_quality_chunk


class RecordingCursor:
    def __init__(self):
        self.sql = None
        self.payload = None
        self.closed = False

    def copy_expert(self, sql: str, buffer: StringIO):
        self.sql = sql
        self.payload = buffer.read()

    def close(self):
        self.closed = True


class FakeRawConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class FakeConnection:
    def __init__(self, cursor):
        self.connection = FakeRawConnection(cursor)


def test_copy_frame_uses_postgres_copy_and_integer_aqi():
    row = {column: None for column in SOURCE_COLUMNS}
    row.update(
        sitename="麥寮",
        county="雲林縣",
        aqi="49.0",
        status="良好",
        datacreationdate="2024-01-01 00:00",
        siteid="83",
    )
    raw = pd.DataFrame([row])
    raw.insert(0, "source_file", "aqi_2024_01.csv")
    raw.insert(1, "source_row_number", [2])
    accepted = transform_air_quality_chunk(raw).accepted
    cursor = RecordingCursor()

    _copy_frame(FakeConnection(cursor), "stage_measurement", STAGE_COLUMNS, accepted)

    assert cursor.sql.startswith("COPY stage_measurement")
    assert ",49," in cursor.payload
    assert ",49.0," not in cursor.payload
    assert "\\N" in cursor.payload
    assert cursor.closed is True
