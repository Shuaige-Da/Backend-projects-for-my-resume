from pathlib import Path

import pytest

from src.aqi.extract import SourceDataError, discover_source_files, iter_csv_chunks


HEADER = "sitename,county,aqi,pollutant,status,so2,so2_avg,co,co_8hr,o3,o3_8hr,pm10,pm10_avg,pm2.5,pm2.5_avg,no2,nox,no,windspeed,winddirec,datacreationdate,longitude,latitude,siteid,unit\n"


def test_discovers_monthly_files_in_order(tmp_path: Path):
    (tmp_path / "aqi_2024_02.csv").write_text(HEADER, encoding="utf-8")
    (tmp_path / "aqi_2024_01.csv").write_text(HEADER, encoding="utf-8")
    (tmp_path / "notes.csv").write_text("ignored", encoding="utf-8")

    files = discover_source_files(tmp_path)

    assert [item.path.name for item in files] == ["aqi_2024_01.csv", "aqi_2024_02.csv"]


def test_rejects_irreversibly_corrupted_text(tmp_path: Path):
    path = tmp_path / "aqi_2024_01.csv"
    path.write_text(HEADER + "��,��,45,,��,,,,,,,,,,,,,,,,2024-01-01 00:00,,,,\n", encoding="utf-8")
    source_file = discover_source_files(tmp_path)[0]

    with pytest.raises(SourceDataError, match="replacement characters"):
        list(iter_csv_chunks(source_file))


def test_streams_rows_with_source_metadata(tmp_path: Path):
    path = tmp_path / "aqi_2024_01.csv"
    row = "麥寮,雲林縣,49,,良好,3.8,,0.31,0.36,56,30,82,53,17,14,9.5,12,2.4,4.5,45,2024-01-01 00:00,120.2,23.7,83,\n"
    path.write_text(HEADER + row, encoding="utf-8-sig")
    source_file = discover_source_files(tmp_path)[0]

    chunk = next(iter_csv_chunks(source_file, chunk_size=1))

    assert chunk.loc[0, "source_file"] == path.name
    assert chunk.loc[0, "source_row_number"] == 2
    assert chunk.loc[0, "sitename"] == "麥寮"
