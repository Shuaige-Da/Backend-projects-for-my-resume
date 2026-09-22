"""使用 Pandas/NumPy 整理数据库聚合结果，生成看板数据。"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


HISTOGRAM_EDGES = np.array([0, 25, 50, 75, 100, 125, 150, 200, 300, 400, 501])
AQI_CATEGORIES = (
    ("良好", 0, 50),
    ("普通", 51, 100),
    ("对敏感族群不健康", 101, 150),
    ("对所有族群不健康", 151, 200),
    ("非常不健康", 201, 300),
    ("危害", 301, 500),
)
CORRELATION_COLUMNS = {
    "aqi": "AQI",
    "pm25": "PM2.5",
    "pm10": "PM10",
    "o3": "O₃",
    "no2": "NO₂",
    "co": "CO",
    "so2": "SO₂",
}


def _filter_params(start: datetime, end: datetime, county: str | None) -> dict:
    return {"start": start, "end": end, "county": county}


def calculate_trend(
    db: Session,
    start: datetime,
    end: datetime,
    county: str | None,
    station_id: int | None,
    interval: str,
) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                date_trunc(:interval, measurement.observed_at) AS bucket,
                COUNT(*) AS measurement_count,
                AVG(measurement.aqi) AS average_aqi,
                AVG(measurement.pm25) AS average_pm25
            FROM air_quality.measurement AS measurement
            JOIN air_quality.station AS station
              ON station.id_station = measurement.id_station
            WHERE measurement.observed_at >= :start
              AND measurement.observed_at < :end
              AND (:county IS NULL OR station.county = :county)
              AND (:station_id IS NULL OR measurement.id_station = :station_id)
            GROUP BY bucket
            ORDER BY bucket
            """
        ),
        {
            "start": start,
            "end": end,
            "county": county,
            "station_id": station_id,
            "interval": interval,
        },
    ).mappings().all()
    if not rows:
        return []

    frame = pd.DataFrame(rows)
    frame["average_aqi"] = pd.to_numeric(frame["average_aqi"], errors="coerce")
    frame["average_pm25"] = pd.to_numeric(frame["average_pm25"], errors="coerce")
    rolling_window = 7 if interval == "day" else 3
    frame["moving_average"] = (
        frame["average_aqi"].rolling(rolling_window, min_periods=1).mean()
    )
    for column in ("average_aqi", "average_pm25", "moving_average"):
        frame[column] = frame[column].round(2)
        frame[column] = frame[column].where(frame[column].notna(), None)
    return frame.to_dict(orient="records")


def calculate_distribution(
    db: Session,
    start: datetime,
    end: datetime,
    county: str | None,
) -> dict:
    rows = db.execute(
        text(
            """
            SELECT measurement.aqi, COUNT(*) AS frequency
            FROM air_quality.measurement AS measurement
            JOIN air_quality.station AS station
              ON station.id_station = measurement.id_station
            WHERE measurement.observed_at >= :start
              AND measurement.observed_at < :end
              AND (:county IS NULL OR station.county = :county)
            GROUP BY measurement.aqi
            ORDER BY measurement.aqi
            """
        ),
        _filter_params(start, end, county),
    ).mappings().all()

    frame = pd.DataFrame(rows, columns=["aqi", "frequency"])
    missing_count = 0
    if not frame.empty:
        missing_count = int(frame.loc[frame["aqi"].isna(), "frequency"].sum())
    valid = frame.dropna(subset=["aqi"]).copy()
    values = valid["aqi"].to_numpy(dtype=float)
    weights = valid["frequency"].to_numpy(dtype=np.int64)
    counts, _ = np.histogram(values, bins=HISTOGRAM_EDGES, weights=weights)

    histogram = []
    for index, count in enumerate(counts):
        lower = int(HISTOGRAM_EDGES[index])
        upper = int(HISTOGRAM_EDGES[index + 1] - 1)
        histogram.append(
            {
                "label": f"{lower}-{upper}",
                "lower_bound": lower,
                "upper_bound": upper,
                "count": int(count),
            }
        )

    categories = []
    for name, lower, upper in AQI_CATEGORIES:
        mask = valid["aqi"].between(lower, upper)
        categories.append(
            {"name": name, "count": int(valid.loc[mask, "frequency"].sum())}
        )
    return {
        "histogram": histogram,
        "categories": categories,
        "missing_count": missing_count,
    }


def calculate_correlation(
    db: Session,
    start: datetime,
    end: datetime,
    county: str | None,
) -> dict:
    rows = db.execute(
        text(
            """
            SELECT
                date_trunc('day', measurement.observed_at) AS bucket,
                measurement.id_station,
                AVG(measurement.aqi) AS aqi,
                AVG(measurement.pm25) AS pm25,
                AVG(measurement.pm10) AS pm10,
                AVG(measurement.o3) AS o3,
                AVG(measurement.no2) AS no2,
                AVG(measurement.co) AS co,
                AVG(measurement.so2) AS so2
            FROM air_quality.measurement AS measurement
            JOIN air_quality.station AS station
              ON station.id_station = measurement.id_station
            WHERE measurement.observed_at >= :start
              AND measurement.observed_at < :end
              AND (:county IS NULL OR station.county = :county)
            GROUP BY bucket, measurement.id_station
            ORDER BY bucket, measurement.id_station
            """
        ),
        _filter_params(start, end, county),
    ).mappings().all()
    labels = list(CORRELATION_COLUMNS.values())
    if not rows:
        return {"labels": labels, "matrix": [], "sample_size": 0}

    frame = pd.DataFrame(rows)
    numeric = frame.loc[:, list(CORRELATION_COLUMNS)].apply(
        pd.to_numeric, errors="coerce"
    )
    correlation = numeric.corr(min_periods=7).round(3)
    matrix = []
    for row_name in CORRELATION_COLUMNS:
        matrix.append(
            [
                None if pd.isna(correlation.loc[row_name, column])
                else float(correlation.loc[row_name, column])
                for column in CORRELATION_COLUMNS
            ]
        )
    return {
        "labels": labels,
        "matrix": matrix,
        "sample_size": len(frame),
    }
