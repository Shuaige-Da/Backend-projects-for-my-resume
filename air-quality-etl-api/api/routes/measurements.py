from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db_conn import get_db
from api.schemas import MeasurementPage, MeasurementResponse

router = APIRouter(prefix="/api/v1/measurements", tags=["观测数据"])


@router.get("", response_model=MeasurementPage, summary="分页查询观测记录")
def list_measurements(
    station_id: int | None = Query(None, ge=1),
    county: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    min_aqi: int | None = Query(None, ge=0, le=500),
    after_id: int | None = Query(None, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    rows = list(
        db.execute(
            text(
                """
                SELECT
                    measurement.id_measurement,
                    measurement.id_station,
                    station.site_name,
                    station.county,
                    measurement.observed_at,
                    measurement.aqi,
                    measurement.status_code,
                    measurement.primary_pollutant,
                    measurement.pm25,
                    measurement.pm10,
                    measurement.o3,
                    measurement.no2,
                    measurement.quality_flags
                FROM air_quality.measurement AS measurement
                JOIN air_quality.station AS station
                  ON station.id_station = measurement.id_station
                WHERE (:station_id IS NULL OR measurement.id_station = :station_id)
                  AND (:county IS NULL OR station.county = :county)
                  AND (:start IS NULL OR measurement.observed_at >= :start)
                  AND (:end IS NULL OR measurement.observed_at < :end)
                  AND (:min_aqi IS NULL OR measurement.aqi >= :min_aqi)
                  AND (:after_id IS NULL OR measurement.id_measurement > :after_id)
                ORDER BY measurement.id_measurement
                LIMIT :fetch_limit
                """
            ),
            {
                "station_id": station_id,
                "county": county,
                "start": start,
                "end": end,
                "min_aqi": min_aqi,
                "after_id": after_id,
                "fetch_limit": limit + 1,
            },
        ).mappings()
    )
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    return MeasurementPage(
        items=[MeasurementResponse(**row) for row in page_rows],
        next_cursor=page_rows[-1]["id_measurement"] if has_more and page_rows else None,
    )
