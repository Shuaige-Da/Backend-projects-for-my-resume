from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db_conn import get_db
from api.routes.validation import validate_period
from api.schemas import CountyRankingResponse, StationRankingResponse, TrendPointResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["数据分析"])


@router.get(
    "/counties",
    response_model=list[CountyRankingResponse],
    summary="县市 AQI 聚合排名",
)
def rank_counties(
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if start is not None and end is not None:
        validate_period(start, end, maximum_days=3660)
    rows = db.execute(
        text(
            """
            SELECT
                station.county,
                COUNT(*) AS measurement_count,
                ROUND(AVG(measurement.aqi)::numeric, 2) AS average_aqi,
                MAX(measurement.aqi) AS maximum_aqi,
                COUNT(*) FILTER (WHERE measurement.aqi > 100) AS unhealthy_hours
            FROM air_quality.measurement AS measurement
            JOIN air_quality.station AS station
              ON station.id_station = measurement.id_station
            WHERE (:start IS NULL OR measurement.observed_at >= :start)
              AND (:end IS NULL OR measurement.observed_at < :end)
            GROUP BY station.county
            ORDER BY average_aqi DESC NULLS LAST, station.county
            LIMIT :limit
            """
        ),
        {"start": start, "end": end, "limit": limit},
    ).mappings()
    return [CountyRankingResponse(**row) for row in rows]


@router.get(
    "/stations",
    response_model=list[StationRankingResponse],
    summary="按县市查询监测站 AQI 排名",
    description="选择县市后，按指定时间范围统计其下属监测站的平均 AQI、最高 AQI 与不健康小时数。",
)
def rank_stations(
    county: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    if start is not None and end is not None:
        validate_period(start, end, maximum_days=3660)
    rows = db.execute(
        text(
            """
            SELECT
                station.id_station,
                station.site_name,
                station.county,
                COUNT(*) AS measurement_count,
                ROUND(AVG(measurement.aqi)::numeric, 2) AS average_aqi,
                MAX(measurement.aqi) AS maximum_aqi,
                COUNT(*) FILTER (WHERE measurement.aqi > 100) AS unhealthy_hours
            FROM air_quality.measurement AS measurement
            JOIN air_quality.station AS station
              ON station.id_station = measurement.id_station
            WHERE station.county = :county
              AND (:start IS NULL OR measurement.observed_at >= :start)
              AND (:end IS NULL OR measurement.observed_at < :end)
            GROUP BY station.id_station, station.site_name, station.county
            ORDER BY average_aqi DESC NULLS LAST, station.site_name
            LIMIT :limit
            """
        ),
        {"county": county, "start": start, "end": end, "limit": limit},
    ).mappings()
    return [StationRankingResponse(**row) for row in rows]


@router.get(
    "/stations/{station_id}/trend",
    response_model=list[TrendPointResponse],
    summary="查询单站趋势",
)
def station_trend(
    station_id: int,
    start: datetime,
    end: datetime,
    interval: Literal["hour", "day", "month"] = "day",
    db: Session = Depends(get_db),
):
    validate_period(start, end, maximum_days=3660)
    rows = db.execute(
        text(
            """
            SELECT
                date_trunc(:interval, observed_at) AS bucket,
                COUNT(*) AS measurement_count,
                ROUND(AVG(aqi)::numeric, 2) AS average_aqi,
                MAX(aqi) AS maximum_aqi,
                ROUND(AVG(pm25)::numeric, 2) AS average_pm25
            FROM air_quality.measurement
            WHERE id_station = :station_id
              AND observed_at >= :start
              AND observed_at < :end
            GROUP BY bucket
            ORDER BY bucket
            """
        ),
        {
            "station_id": station_id,
            "start": start,
            "end": end,
            "interval": interval,
        },
    ).mappings()
    return [TrendPointResponse(**row) for row in rows]
