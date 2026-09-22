from datetime import datetime, timedelta

from fastapi import HTTPException


def validate_period(start: datetime, end: datetime, maximum_days: int = 366) -> None:
    """校验分析接口的时间窗口，避免无效或代价过高的查询。"""
    if end <= start:
        raise HTTPException(status_code=422, detail="结束时间必须晚于开始时间")
    if end - start > timedelta(days=maximum_days):
        raise HTTPException(
            status_code=422,
            detail=f"单次查询范围不能超过 {maximum_days} 天",
        )
