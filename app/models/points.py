from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class PointsType(str, Enum):
    """积分类型枚举"""
    CHECK_IN = "check_in"
    TASK = "task"
    REWARD = "reward"
    EXCHANGE = "exchange"
    PENALTY = "penalty"
    ADMIN_ADJUST = "admin_adjust"


class PointsBase(BaseModel):
    """积分基础模型"""
    points: int
    balance: int
    type: PointsType
    source_type: Optional[str] = None
    description: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class PointsCreate(PointsBase):
    """创建积分模型"""
    account_id: int


class PointsUpdate(BaseModel):
    """更新积分模型"""
    description: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class Points(PointsBase):
    """积分模型"""
    id: int
    account_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PointsBalance(BaseModel):
    """积分余额模型"""
    total_balance: int
    available_balance: int
    frozen_balance: int = 0


class PointsStats(BaseModel):
    """积分统计模型"""
    total_earned: int
    total_spent: int
    current_balance: int
    this_month_earned: int
    this_month_spent: int
    check_in_points: int
    task_points: int
    reward_points: int
    exchange_points: int


class MonthlyPointsSummary(BaseModel):
    """月度积分汇总模型"""
    month: int
    total_points: int
    total_records: int
