from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.account import Account
from app.utils.time_utils import get_local_time
from app.crud.check_in import (
    get_check_in_by_date, 
    create_check_in, 
    get_check_in_calendar,
    get_continuous_days,
    get_check_in_stats,
    calculate_continuous_days
)

router = APIRouter()


class CheckInRequest(BaseModel):
    """签到请求"""
    extra: Optional[dict] = None


class CheckInResponse(BaseModel):
    """签到响应"""
    id: int
    account_id: int
    check_in_date: date
    check_in_time: datetime
    points_earned: int
    continuous_days: int
    check_in_type: str
    extra: Optional[dict] = None
    created_at: datetime


class CheckInCalendarResponse(BaseModel):
    """签到日历响应"""
    year: int
    month: int
    check_in_dates: List[date]
    continuous_days: int
    total_check_ins: int


class CheckInStatsResponse(BaseModel):
    """签到统计响应"""
    total_check_ins: int
    continuous_days: int
    longest_continuous: int
    this_month_check_ins: int


@router.post("/", response_model=CheckInResponse)
async def check_in(
    request: CheckInRequest,
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """用户签到"""
    today = date.today()
    
    # 检查今天是否已经签到
    existing_check_in = await get_check_in_by_date(db, current_user.account_id, today)
    if existing_check_in:
        raise HTTPException(status_code=400, detail="今天已经签到过了")
    
    # 计算连续签到天数
    continuous_days = await calculate_continuous_days(db, current_user.account_id)
    
    # 计算积分奖励
    if continuous_days >= 7:
        points_earned = 20  # 连续7天以上奖励20积分
    elif continuous_days >= 3:
        points_earned = 10  # 连续3-6天奖励10积分
    else:
        points_earned = 5   # 普通签到5积分
    
    # 创建签到记录
    check_in_data = {
        "account_id": current_user.account_id,
        "check_in_date": today,
        "check_in_time": get_local_time(),
        "points_earned": points_earned,
        "continuous_days": continuous_days,
        "check_in_type": "normal",
        "extra": request.extra or {}
    }
    
    check_in = await create_check_in(db, check_in_data)
    return check_in


@router.get("/calendar", response_model=CheckInCalendarResponse)
async def get_check_in_calendar_data(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取签到日历数据"""
    calendar_data = await get_check_in_calendar(db, current_user.account_id, year, month)
    return calendar_data


@router.get("/stats/{account_id}", response_model=CheckInStatsResponse)
async def get_check_in_statistics(
    account_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取签到统计信息"""
    stats = await get_check_in_stats(db, account_id)
    return stats


@router.get("/history/{account_id}", response_model=List[CheckInResponse])
async def get_check_in_history(
    account_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取签到历史记录"""
    from app.crud.check_in import get_check_in_history
    history = await get_check_in_history(db, account_id, skip=skip, limit=limit)
    return history
