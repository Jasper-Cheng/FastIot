from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import date, datetime
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.utils.time_utils import get_local_time
from app.crud.check_in import (
    get_check_in_by_date, 
    create_check_in, 
    get_check_in_calendar,
    get_check_in_stats,
    calculate_continuous_days,
    get_check_in_history
)
from app.models.check_in import (
    CheckInResponse,
    CheckInCalendarResponse,
    CheckInStatsResponse
)
from app.api.utils import extract_token_info, send_personal_notice

router = APIRouter()

"""
签到功能模块 - Client API

【App + Web 通用】
所有接口支持 App 和 Web 平台，平台信息通过 token.platform 字段识别。
"""


@router.post("/", response_model=CheckInResponse)
async def check_in(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    extra: dict = Body(default={})
):
    """用户签到
    
    - 每天只能签到一次
    - 连续签到有额外积分奖励
    """
    today = date.today()
    account_id, _, _ = extract_token_info(token_info)
    
    # 检查今天是否已经签到
    existing_check_in = await get_check_in_by_date(db, account_id, today)
    if existing_check_in:
        raise HTTPException(status_code=400, detail="今天已经签到过了")
    
    # 计算连续签到天数
    continuous_days = await calculate_continuous_days(db, account_id)
    
    # 计算积分奖励
    check_in_type = "normal"
    if continuous_days >= 7:
        points_earned = 20  # 连续7天以上奖励20积分
        check_in_type = "bonus"
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
        "check_in_type": check_in_type,
        "extra": extra or {}
    }
    
    check_in_record = await create_check_in(db, check_in_data)
    
    # 使用 utils 发送个人通知
    await send_personal_notice(
        account_id=account_id,
        payload={
            "type": "check_in_success",
            "message": f"签到成功！获得 {points_earned} 积分，连续签到 {continuous_days} 天",
            "check_in_id": check_in_record.id,
            "points_earned": points_earned,
            "continuous_days": continuous_days,
            "check_in_type": check_in_type,
            "check_in_date": today.isoformat(),
        }
    )
    
    return check_in_record


@router.get("/calendar", response_model=CheckInCalendarResponse)
async def get_check_in_calendar_data(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    year: int = Query(None, ge=2020, le=2030, description="年份，默认当前年"),
    month: int = Query(None, ge=1, le=12, description="月份，默认当前月")
):
    """获取签到日历数据
    
    - 返回指定年月的签到日期列表
    - 如果不指定年月，则返回当前月的数据
    """
    # 如果没有指定年月，使用当前年月
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month
    
    calendar_data = await get_check_in_calendar(db, extract_token_info(token_info)[0], year, month)
    return calendar_data


@router.get("/stats", response_model=CheckInStatsResponse)
async def get_check_in_statistics(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """获取当前用户的签到统计信息
    
    - total_check_ins: 总签到次数
    - continuous_days: 当前连续签到天数
    - longest_continuous: 最长连续签到天数
    """
    account_id, _, _ = extract_token_info(token_info)
    stats = await get_check_in_stats(db, account_id)
    return stats


@router.get("/history", response_model=List[CheckInResponse])
async def get_user_check_in_history(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取当前用户的签到历史记录
    
    - 按时间倒序排列
    - 支持分页
    """
    account_id, _, _ = extract_token_info(token_info)
    skip = (page - 1) * page_size
    limit = page_size
    
    history = await get_check_in_history(db, account_id, skip=skip, limit=limit)
    return history

