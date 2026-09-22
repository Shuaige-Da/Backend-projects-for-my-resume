from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db_conn import get_db
from api.schemas import (
    CorrelationResponse,
    DashboardDistributionResponse,
    DashboardOverviewResponse,
    DashboardTrendPoint,
)
from api.services.dashboard import (
    calculate_correlation,
    calculate_distribution,
    calculate_trend,
)
from api.routes.validation import validate_period

router = APIRouter(prefix="/api/v1/dashboard", tags=["数据看板"])


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    summary="查询看板核心指标",
)
def overview(
    start: datetime,
    end: datetime,
    county: str | None = None,
    db: Session = Depends(get_db),
):
    validate_period(start, end)
    row = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS total_measurements,
                COUNT(DISTINCT measurement.id_station) AS total_stations,
                ROUND(AVG(measurement.aqi)::numeric, 2) AS average_aqi,
                MAX(measurement.aqi) AS maximum_aqi,
                COUNT(*) FILTER (WHERE measurement.aqi > 100) AS unhealthy_hours,
                COUNT(*) FILTER (WHERE measurement.aqi IS NULL) AS missing_aqi_count,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE measurement.aqi IS NULL)
                    / NULLIF(COUNT(*), 0),
                    2
                ) AS missing_aqi_rate
            FROM air_quality.measurement AS measurement
            JOIN air_quality.station AS station
              ON station.id_station = measurement.id_station
            WHERE measurement.observed_at >= :start
              AND measurement.observed_at < :end
              AND (:county IS NULL OR station.county = :county)
            """
        ),
        {"start": start, "end": end, "county": county},
    ).mappings().one()
    result = dict(row)
    result["average_aqi"] = (
        float(row["average_aqi"]) if row["average_aqi"] is not None else None
    )
    result["missing_aqi_rate"] = float(row["missing_aqi_rate"] or 0)
    return DashboardOverviewResponse(**result)


@router.get(
    "/trend",
    response_model=list[DashboardTrendPoint],
    summary="生成 AQI 趋势和移动平均线",
)
def trend(
    start: datetime,
    end: datetime,
    county: str | None = None,
    station_id: int | None = Query(None, ge=1),
    interval: Literal["day", "month"] = "day",
    db: Session = Depends(get_db),
):
    validate_period(start, end, 366 if interval == "day" else 3660)
    return calculate_trend(db, start, end, county, station_id, interval)


@router.get(
    "/distribution",
    response_model=DashboardDistributionResponse,
    summary="生成 AQI 直方图与等级分布",
)
def distribution(
    start: datetime,
    end: datetime,
    county: str | None = None,
    db: Session = Depends(get_db),
):
    validate_period(start, end)
    return calculate_distribution(db, start, end, county)


@router.get(
    "/correlation",
    response_model=CorrelationResponse,
    summary="使用 Pandas 计算污染物相关性矩阵",
)
def correlation(
    start: datetime,
    end: datetime,
    county: str | None = None,
    db: Session = Depends(get_db),
):
    validate_period(start, end)
    return calculate_correlation(db, start, end, county)
