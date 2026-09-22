"""Vectorized cleaning, validation, and deduplication for AQI records."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .constants import (
    COUNTY_MAP,
    NUMERIC_COLUMNS,
    OUTPUT_COLUMNS,
    POLLUTANT_MAP,
    SOURCE_COLUMNS,
    STATUS_MAP,
    TEXT_COLUMNS,
)


@dataclass(frozen=True)
class TransformResult:
    accepted: pd.DataFrame
    rejected: pd.DataFrame


def _append_reason(reasons: pd.Series, mask: pd.Series, reason: str) -> pd.Series:
    separator = reasons.ne("").map({True: "|", False: ""})
    reasons.loc[mask] = reasons.loc[mask] + separator.loc[mask] + reason
    return reasons


def _quality_flags(frame: pd.DataFrame) -> pd.Series:
    flags = pd.Series("", index=frame.index, dtype="string")
    checks = (
        (
            frame["aqi"].isna() & ~frame["_negative_aqi_sentinel"],
            "MISSING_AQI",
        ),
        (frame["_negative_aqi_sentinel"], "NEGATIVE_AQI_SENTINEL"),
        (frame[["longitude", "latitude"]].isna().any(axis=1), "MISSING_COORDINATES"),
        (frame["source_site_id"].isna(), "MISSING_SOURCE_SITE_ID"),
    )
    for mask, flag in checks:
        separator = flags.ne("").map({True: "|", False: ""})
        flags.loc[mask] = flags.loc[mask] + separator.loc[mask] + flag
    return flags.mask(flags.eq(""), pd.NA)


def transform_air_quality_chunk(raw: pd.DataFrame) -> TransformResult:
    """Clean one chunk and separate invalid or duplicate rows."""
    required = set(SOURCE_COLUMNS) | {"source_file", "source_row_number"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    frame = raw.copy()
    for column in TEXT_COLUMNS:
        frame[column] = frame[column].astype("string").str.strip()

    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["observed_at"] = pd.to_datetime(
        frame["datacreationdate"], format="mixed", errors="coerce"
    )
    frame["_negative_aqi_sentinel"] = frame["aqi"].lt(0).fillna(False)
    frame.loc[frame["_negative_aqi_sentinel"], "aqi"] = pd.NA
    frame["source_site_id"] = frame["siteid"].astype("Int64")
    frame["site_name"] = frame["sitename"]
    frame["county"] = frame["county"].replace(COUNTY_MAP)
    frame["status_code"] = frame["status"].map(STATUS_MAP).fillna(frame["status"])
    frame["primary_pollutant"] = (
        frame["pollutant"].map(POLLUTANT_MAP).fillna(frame["pollutant"])
    )

    reasons = pd.Series("", index=frame.index, dtype="string")
    corrupted = pd.Series(False, index=frame.index)
    for column in ("sitename", "county", "status", "pollutant"):
        corrupted |= frame[column].str.contains("�", regex=False, na=False)
    reasons = _append_reason(reasons, corrupted, "CORRUPTED_TEXT")
    reasons = _append_reason(
        reasons,
        frame["site_name"].isna() | frame["county"].isna(),
        "MISSING_STATION",
    )
    reasons = _append_reason(reasons, frame["observed_at"].isna(), "INVALID_OBSERVED_AT")
    reasons = _append_reason(
        reasons,
        frame["aqi"].notna() & frame["aqi"].gt(500),
        "AQI_OUT_OF_RANGE",
    )
    reasons = _append_reason(
        reasons,
        frame["latitude"].notna() & ~frame["latitude"].between(-90, 90),
        "LATITUDE_OUT_OF_RANGE",
    )
    reasons = _append_reason(
        reasons,
        frame["longitude"].notna() & ~frame["longitude"].between(-180, 180),
        "LONGITUDE_OUT_OF_RANGE",
    )

    valid = frame.loc[reasons.eq("")].copy()
    # Some 2026 resources contain parallel Chinese and English rows for one
    # source ID and timestamp. Source IDs can also change or be reused across
    # years, so natural station duplicates are checked separately.
    valid["_language_priority"] = valid["site_name"].map(
        lambda value: 0 if isinstance(value, str) and not value.isascii() else 1
    )
    valid.sort_values(
        ["observed_at", "_language_priority", "source_row_number"],
        kind="stable",
        inplace=True,
    )
    duplicate_natural = valid.duplicated(
        ["county", "site_name", "observed_at"], keep="first"
    )
    duplicate_source = valid["source_site_id"].notna() & valid.duplicated(
        ["source_site_id", "observed_at"], keep="first"
    )
    duplicate_index = valid.index[duplicate_natural | duplicate_source]
    if len(duplicate_index):
        reasons.loc[duplicate_index] = "DUPLICATE_STATION_TIMESTAMP"
        valid = valid.drop(index=duplicate_index)

    valid["aqi"] = valid["aqi"].astype("Int64")
    valid["quality_flags"] = _quality_flags(valid)
    valid.rename(
        columns={
            "pm2.5": "pm25",
            "pm2.5_avg": "pm25_avg",
            "windspeed": "wind_speed",
            "winddirec": "wind_direction",
        },
        inplace=True,
    )
    accepted = valid.loc[:, OUTPUT_COLUMNS].sort_values(
        ["observed_at", "source_site_id", "site_name"], kind="stable"
    )

    rejected = raw.loc[reasons.ne("")].copy()
    rejected.insert(2, "rejection_reason", reasons.loc[rejected.index])
    return TransformResult(
        accepted=accepted.reset_index(drop=True),
        rejected=rejected.reset_index(drop=True),
    )
