from datetime import datetime, timedelta

from api.services.dashboard import (
    calculate_correlation,
    calculate_distribution,
    calculate_trend,
)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_args, **_kwargs):
        return FakeResult(self.rows)


def test_distribution_uses_weighted_histogram_and_categories():
    rows = [
        {"aqi": None, "frequency": 3},
        {"aqi": 20, "frequency": 10},
        {"aqi": 80, "frequency": 5},
        {"aqi": 120, "frequency": 2},
        {"aqi": 350, "frequency": 1},
    ]

    result = calculate_distribution(
        FakeSession(rows), datetime(2024, 1, 1), datetime(2024, 2, 1), None
    )

    assert result["missing_count"] == 3
    assert sum(item["count"] for item in result["histogram"]) == 18
    assert result["categories"][0] == {"name": "良好", "count": 10}
    assert result["categories"][-1] == {"name": "危害", "count": 1}


def test_trend_adds_pandas_rolling_average():
    start = datetime(2024, 1, 1)
    rows = [
        {
            "bucket": start + timedelta(days=index),
            "measurement_count": 24,
            "average_aqi": value,
            "average_pm25": value / 2,
        }
        for index, value in enumerate((10, 20, 30))
    ]

    result = calculate_trend(
        FakeSession(rows), start, start + timedelta(days=4), None, None, "day"
    )

    assert [item["moving_average"] for item in result] == [10.0, 15.0, 20.0]


def test_correlation_returns_square_matrix():
    start = datetime(2024, 1, 1)
    rows = []
    for index in range(8):
        rows.append(
            {
                "bucket": start + timedelta(days=index),
                "id_station": 1,
                "aqi": index,
                "pm25": index * 2,
                "pm10": index * 3,
                "o3": 20 - index,
                "no2": index + 4,
                "co": index / 10,
                "so2": index + 1,
            }
        )

    result = calculate_correlation(
        FakeSession(rows), start, start + timedelta(days=9), None
    )

    assert result["sample_size"] == 8
    assert len(result["labels"]) == 7
    assert len(result["matrix"]) == 7
    assert result["matrix"][0][1] == 1.0
