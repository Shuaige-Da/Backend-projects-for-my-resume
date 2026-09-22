from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db_conn import get_db
from api.schemas import StationListResponse, StationResponse

router = APIRouter(prefix="/api/v1/stations", tags=["站点"])


@router.get("", response_model=StationListResponse, summary="查询监测站点")
def list_stations(
    county: str | None = None,
    name: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT id_station, source_site_id, site_name, county, longitude, latitude
            FROM air_quality.station
            WHERE (:county IS NULL OR county = :county)
              AND (:name IS NULL OR site_name ILIKE '%' || :name || '%')
            ORDER BY county, site_name, id_station
            LIMIT :limit OFFSET :offset
            """
        ),
        {"county": county, "name": name, "limit": limit, "offset": offset},
    ).mappings()
    return StationListResponse(
        items=[StationResponse(**row) for row in rows],
        limit=limit,
        offset=offset,
    )
