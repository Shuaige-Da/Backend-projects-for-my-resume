import logging

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db_conn import get_db
from api.routes.analytics import router as analytics_router
from api.routes.dashboard import router as dashboard_router
from api.routes.imports import router as imports_router
from api.routes.measurements import router as measurements_router
from api.routes.stations import router as stations_router
from api.schemas import HealthResponse, RootResponse, StatsResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="空气质量 ETL 与数据分析 API",
    version="1.0.0",
    description=(
        "面向台湾环境部 AQX_P_488 月度历史资料的数据清洗、批量入库、"
        "质量审计与可视化分析服务。"
    ),
    openapi_tags=[
        {"name": "系统", "description": "服务状态与数据库健康检查"},
        {"name": "站点", "description": "空气质量监测站点查询"},
        {"name": "观测数据", "description": "逐站逐小时观测数据分页查询"},
        {"name": "数据分析", "description": "县市排名与站点趋势分析"},
        {"name": "数据看板", "description": "图表所需的统计分析数据"},
        {"name": "导入审计", "description": "ETL 文件执行状态与质量计数"},
    ],
)
app.include_router(stations_router)
app.include_router(measurements_router)
app.include_router(analytics_router)
app.include_router(dashboard_router)
app.include_router(imports_router)


@app.get("/", response_model=RootResponse, tags=["系统"], summary="查看服务入口")
def root():
    return RootResponse(name="空气质量 ETL 与数据分析 API", docs="/docs")


@app.get("/health", response_model=HealthResponse, tags=["系统"], summary="数据库健康检查")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return HealthResponse(status="正常", database="可连接")
    except Exception as exc:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="数据库暂时不可用") from exc


@app.get(
    "/api/v1/stats",
    response_model=StatsResponse,
    tags=["数据分析"],
    summary="查看全库统计信息",
)
def stats(db: Session = Depends(get_db)):
    row = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM air_quality.measurement) AS total_measurements,
                (SELECT COUNT(*) FROM air_quality.station) AS total_stations,
                (SELECT COUNT(DISTINCT county) FROM air_quality.station) AS total_counties,
                (SELECT COUNT(*) FROM air_quality.import_file WHERE status = 'COMPLETED') AS completed_imports,
                (SELECT COALESCE(SUM(rejected_rows), 0) FROM air_quality.import_file) AS rejected_rows,
                (SELECT MIN(observed_at) FROM air_quality.measurement) AS earliest_observation,
                (SELECT MAX(observed_at) FROM air_quality.measurement) AS latest_observation,
                pg_size_pretty(pg_database_size(current_database())) AS database_size
            """
        )
    ).mappings().one()
    return StatsResponse(**row)
