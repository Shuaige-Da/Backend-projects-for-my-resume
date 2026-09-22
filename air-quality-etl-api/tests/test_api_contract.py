from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_root_does_not_require_database_connection():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "空气质量 ETL 与数据分析 API",
        "docs": "/docs",
    }


def test_openapi_exposes_air_quality_routes():
    paths = app.openapi()["paths"]

    assert "/api/v1/stations" in paths
    assert "/api/v1/measurements" in paths
    assert "/api/v1/analytics/counties" in paths
    assert "/api/v1/analytics/stations" in paths
    assert "/api/v1/analytics/stations/{station_id}/trend" in paths
    assert "/api/v1/imports" in paths
    assert "/api/v1/stats" in paths
    assert "/api/v1/dashboard/overview" in paths
    assert "/api/v1/dashboard/trend" in paths
    assert "/api/v1/dashboard/distribution" in paths
    assert "/api/v1/dashboard/correlation" in paths
