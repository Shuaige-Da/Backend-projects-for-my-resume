from datetime import date, datetime

from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    name: str
    docs: str


class HealthResponse(BaseModel):
    status: str
    database: str


class StatsResponse(BaseModel):
    total_measurements: int
    total_stations: int
    total_counties: int
    completed_imports: int
    rejected_rows: int
    earliest_observation: datetime | None
    latest_observation: datetime | None
    database_size: str


class StationResponse(BaseModel):
    id_station: int
    source_site_id: int | None
    site_name: str
    county: str
    longitude: float | None
    latitude: float | None


class StationListResponse(BaseModel):
    items: list[StationResponse]
    limit: int
    offset: int


class MeasurementResponse(BaseModel):
    id_measurement: int
    id_station: int
    site_name: str
    county: str
    observed_at: datetime
    aqi: int | None
    status_code: str | None
    primary_pollutant: str | None
    pm25: float | None
    pm10: float | None
    o3: float | None
    no2: float | None
    quality_flags: str | None


class MeasurementPage(BaseModel):
    items: list[MeasurementResponse]
    next_cursor: int | None


class CountyRankingResponse(BaseModel):
    county: str
    measurement_count: int
    average_aqi: float | None
    maximum_aqi: int | None
    unhealthy_hours: int


class StationRankingResponse(BaseModel):
    id_station: int
    site_name: str
    county: str
    measurement_count: int
    average_aqi: float | None
    maximum_aqi: int | None
    unhealthy_hours: int


class TrendPointResponse(BaseModel):
    bucket: datetime
    measurement_count: int
    average_aqi: float | None
    maximum_aqi: int | None
    average_pm25: float | None


class ImportFileResponse(BaseModel):
    id_import_file: int
    filename: str
    source_month: date
    status: str
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class LimitParams(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)


class DashboardOverviewResponse(BaseModel):
    total_measurements: int
    total_stations: int
    average_aqi: float | None
    maximum_aqi: int | None
    unhealthy_hours: int
    missing_aqi_count: int
    missing_aqi_rate: float


class DashboardTrendPoint(BaseModel):
    bucket: datetime
    measurement_count: int
    average_aqi: float | None
    moving_average: float | None
    average_pm25: float | None


class HistogramBucket(BaseModel):
    label: str
    lower_bound: int
    upper_bound: int
    count: int


class CategorySlice(BaseModel):
    name: str
    count: int


class DashboardDistributionResponse(BaseModel):
    histogram: list[HistogramBucket]
    categories: list[CategorySlice]
    missing_count: int


class CorrelationResponse(BaseModel):
    labels: list[str]
    matrix: list[list[float | None]]
    sample_size: int
