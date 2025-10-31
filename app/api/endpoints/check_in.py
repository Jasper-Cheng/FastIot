from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import date
from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.utils.time_utils import get_local_time
from app.crud.check_in import (
    get_check_in_by_date, 
    create_check_in, 
    get_check_in_calendar,
    get_check_in_stats,
    calculate_continuous_days
)
from app.models.check_in import (
    CheckInRequest,
    CheckInResponse,
    CheckInCalendarResponse,
    CheckInStatsResponse
)

router = APIRouter()


@router.post("/", response_model=CheckInResponse)
async def check_in(
    request: CheckInRequest,
    token_info: dict = Depends(get_current_token),
    db: AsyncSession = Depends(get_db)
):
    """用户签到"""
    today = date.today()
    account_id = token_info["account_id"]
    user_id = token_info["user_id"]
    
    # 检查今天是否已经签到
    existing_check_in = await get_check_in_by_date(db, account_id, today)
    if existing_check_in:
        raise HTTPException(status_code=400, detail="今天已经签到过了")
    
    # 计算连续签到天数
    continuous_days = await calculate_continuous_days(db, user_id)
    
    # 计算积分奖励
    if continuous_days >= 7:
        points_earned = 20  # 连续7天以上奖励20积分
    elif continuous_days >= 3:
        points_earned = 10  # 连续3-6天奖励10积分
    else:
        points_earned = 5   # 普通签到5积分
    
    # 创建签到记录
    check_in_data = {
        "account_id": account_id,
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
    token_info: dict = Depends(get_current_token),
    db: AsyncSession = Depends(get_db)
):
    """获取签到日历数据"""
    calendar_data = await get_check_in_calendar(db, token_info["account_id"], year, month)
    return calendar_data


@router.get("/stats", response_model=CheckInStatsResponse)
async def get_check_in_statistics(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """获取当前用户的签到统计信息"""
    account_id = token_info["account_id"]
    stats = await get_check_in_stats(db, account_id)
    return stats


@router.get("/history", response_model=List[CheckInResponse])
async def get_check_in_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """获取当前用户的签到历史记录"""
    account_id = token_info["account_id"]
    from app.crud.check_in import get_check_in_history
    history = await get_check_in_history(db, account_id, skip=skip, limit=limit)
    return history
