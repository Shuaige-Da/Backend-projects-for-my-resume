import pandas as pd

from src.aqi.constants import SOURCE_COLUMNS
from src.aqi.transform import transform_air_quality_chunk


def make_row(**overrides):
    row = {column: None for column in SOURCE_COLUMNS}
    row.update(
        {
            "sitename": "麥寮",
            "county": "雲林縣",
            "aqi": "49",
            "status": "良好",
            "datacreationdate": "2024-01-01 00:00",
            "longitude": "120.251825",
            "latitude": "23.753506",
            "siteid": "83",
        }
    )
    row.update(overrides)
    return row


def make_frame(*rows):
    frame = pd.DataFrame(rows or [make_row()])
    frame.insert(0, "source_file", "aqi_2024_01.csv")
    frame.insert(1, "source_row_number", range(2, len(frame) + 2))
    return frame


def test_cleans_types_and_maps_domain_values():
    result = transform_air_quality_chunk(
        make_frame(make_row(pollutant="細懸浮微粒", **{"pm2.5": "17.5"}))
    )

    assert result.rejected.empty
    record = result.accepted.iloc[0]
    assert record["source_site_id"] == 83
    assert record["status_code"] == "GOOD"
    assert record["primary_pollutant"] == "PM2.5"
    assert record["pm25"] == 17.5
    assert record["observed_at"] == pd.Timestamp("2024-01-01 00:00")


def test_normalizes_english_county_dimension():
    result = transform_air_quality_chunk(
        make_frame(make_row(county="Yunlin County", sitename="Mailiao"))
    )

    assert result.rejected.empty
    assert result.accepted.loc[0, "county"] == "雲林縣"


def test_missing_optional_measurements_are_flagged_not_rejected():
    result = transform_air_quality_chunk(
        make_frame(make_row(aqi=None, longitude=None, latitude=None, siteid=None))
    )

    assert result.rejected.empty
    assert result.accepted.loc[0, "quality_flags"] == (
        "MISSING_AQI|MISSING_COORDINATES|MISSING_SOURCE_SITE_ID"
    )


def test_rejects_invalid_identity_timestamp_and_aqi():
    result = transform_air_quality_chunk(
        make_frame(make_row(sitename=None, datacreationdate="bad", aqi="999"))
    )

    assert result.accepted.empty
    reasons = result.rejected.loc[0, "rejection_reason"]
    assert "MISSING_STATION" in reasons
    assert "INVALID_OBSERVED_AT" in reasons
    assert "AQI_OUT_OF_RANGE" in reasons


def test_negative_aqi_sentinel_is_preserved_as_a_quality_flag():
    result = transform_air_quality_chunk(make_frame(make_row(aqi="-1")))

    assert result.rejected.empty
    assert pd.isna(result.accepted.loc[0, "aqi"])
    assert result.accepted.loc[0, "quality_flags"] == "NEGATIVE_AQI_SENTINEL"


def test_accepts_slash_timestamp_used_by_source_history():
    result = transform_air_quality_chunk(
        make_frame(make_row(datacreationdate="2023/11/13 10:00:00"))
    )

    assert result.rejected.empty
    assert result.accepted.loc[0, "observed_at"] == pd.Timestamp("2023-11-13 10:00")


def test_prefers_chinese_row_when_bilingual_rows_share_site_and_time():
    english = make_row(sitename="Mailiao", county="Yunlin County", status="Good")
    chinese = make_row(sitename="麥寮", county="雲林縣", status="良好")

    result = transform_air_quality_chunk(make_frame(english, chinese))

    assert len(result.accepted) == 1
    assert result.accepted.loc[0, "site_name"] == "麥寮"
    assert result.rejected.loc[0, "rejection_reason"] == "DUPLICATE_STATION_TIMESTAMP"


def test_deduplicates_same_natural_station_when_source_id_changes():
    old_id = make_row(siteid="53")
    new_id = make_row(siteid="60")

    result = transform_air_quality_chunk(make_frame(old_id, new_id))

    assert len(result.accepted) == 1
    assert len(result.rejected) == 1
    assert result.rejected.loc[0, "rejection_reason"] == "DUPLICATE_STATION_TIMESTAMP"


def test_rejects_replacement_characters_in_dimensions():
    result = transform_air_quality_chunk(make_frame(make_row(sitename="���")))

    assert result.accepted.empty
    assert result.rejected.loc[0, "rejection_reason"] == "CORRUPTED_TEXT"
