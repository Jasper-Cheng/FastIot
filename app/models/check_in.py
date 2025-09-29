from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class CheckInType(str, Enum):
    """签到类型枚举"""
    NORMAL = "normal"
    BONUS = "bonus"
    MAKEUP = "makeup"


class CheckInBase(BaseModel):
    """签到基础模型"""
    check_in_date: date
    check_in_time: datetime
    points_earned: int = 0
    continuous_days: int = 1
    check_in_type: CheckInType = CheckInType.NORMAL
    extra: Optional[Dict[str, Any]] = None


class CheckInCreate(CheckInBase):
    """创建签到模型"""
    account_id: int


class CheckInUpdate(BaseModel):
    """更新签到模型"""
    location: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class CheckIn(CheckInBase):
    """签到模型"""
    id: int
    account_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CheckInCalendar(BaseModel):
    """签到日历模型"""
    year: int
    month: int
    check_in_dates: List[date]
    continuous_days: int
    total_check_ins: int
    total_points: int


class CheckInStats(BaseModel):
    """签到统计模型"""
    total_check_ins: int
    total_points: int
    continuous_days: int
    longest_continuous: int
    this_month_check_ins: int
    this_month_points: int
