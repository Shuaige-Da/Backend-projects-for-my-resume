from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from api.routes.validation import validate_period


def test_validate_period_accepts_valid_window():
    start = datetime(2026, 1, 1)
    validate_period(start, start + timedelta(days=30))


@pytest.mark.parametrize(
    ("end_offset", "message"),
    [
        (timedelta(0), "结束时间必须晚于开始时间"),
        (timedelta(days=367), "单次查询范围不能超过 366 天"),
    ],
)
def test_validate_period_rejects_invalid_window(end_offset, message):
    start = datetime(2026, 1, 1)
    with pytest.raises(HTTPException) as exc_info:
        validate_period(start, start + end_offset)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == message
