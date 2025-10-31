from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List, Dict, Any


class CheckInRequest(BaseModel):
    """签到请求"""
    extra: Optional[Dict[str, Any]] = None


class CheckInResponse(BaseModel):
    """签到响应"""
    id: int
    account_id: int
    check_in_date: date
    check_in_time: datetime
    points_earned: int
    continuous_days: int
    check_in_type: str
    extra: Optional[Dict[str, Any]] = None
    created_at: datetime


class CheckInCalendarResponse(BaseModel):
    """签到日历响应"""
    year: int
    month: int
    check_in_dates: List[date]


class CheckInStatsResponse(BaseModel):
    """签到统计响应"""
    total_check_ins: int
    continuous_days: int
    longest_continuous: int