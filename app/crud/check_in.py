from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from calendar import monthrange
from app.db.models.check_in import CheckIn
from app.db.models.points import Points


async def get_check_in_by_date(db: AsyncSession, account_id: int, check_date: date) -> Optional[CheckIn]:
    """根据日期获取签到记录"""
    result = await db.execute(
        select(CheckIn).where(
            and_(
                CheckIn.account_id == account_id,
                CheckIn.check_in_date == check_date
            )
        ).order_by(CheckIn.created_at.desc())
    )
    return result.scalars().first()


async def create_check_in(db: AsyncSession, check_in_data: Dict[str, Any]) -> CheckIn:
    """创建签到记录"""
    check_in = CheckIn(**check_in_data)
    db.add(check_in)
    await db.flush()
    
    # 同时创建积分记录
    points_data = {
        "account_id": check_in.account_id,
        "points": check_in.points_earned,
        "type": "check_in",
        "description": f"每日签到奖励（连续{check_in.continuous_days}天）",
        "extra": {
            "check_in_id": check_in.id,
            "continuous_days": check_in.continuous_days,
            "check_in_type": check_in.check_in_type
        }
    }
    
    # 获取当前积分余额
    current_balance = await get_user_points_balance(db, check_in.account_id)
    points_data["balance"] = current_balance["total_balance"] + check_in.points_earned
    
    points = Points(**points_data)
    db.add(points)
    
    await db.commit()
    await db.refresh(check_in)
    return check_in


async def get_check_in_calendar(db: AsyncSession, account_id: int, year: int, month: int) -> Dict[str, Any]:
    """获取签到日历数据"""
    # 获取该月的所有签到记录
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    
    result = await db.execute(
        select(CheckIn.check_in_date)
        .where(
            and_(
                CheckIn.account_id == account_id,
                CheckIn.check_in_date >= start_date,
                CheckIn.check_in_date <= end_date
            )
        )
        .order_by(CheckIn.check_in_date)
    )
    
    check_ins = result.fetchall()
    check_in_dates = [record.check_in_date for record in check_ins]
    
    # 获取连续签到天数
    continuous_days = await get_continuous_days(db, account_id)
    
    return {
        "year": year,
        "month": month,
        "check_in_dates": check_in_dates,
        "continuous_days": continuous_days,
        "total_check_ins": len(check_in_dates)
    }


async def get_continuous_days(db: AsyncSession, account_id: int) -> int:
    """获取连续签到天数"""
    # 直接查询最新的签到记录的continuous_days字段
    result = await db.execute(
        select(CheckIn.continuous_days)
        .where(CheckIn.account_id == account_id)
        .order_by(CheckIn.check_in_date.desc())
        .limit(1)
    )
    
    continuous_days = result.scalar()
    return continuous_days or 0


async def get_latest_check_in(db: AsyncSession, account_id: int) -> Optional[CheckIn]:
    """获取最新的签到记录"""
    result = await db.execute(
        select(CheckIn)
        .where(CheckIn.account_id == account_id)
        .order_by(CheckIn.check_in_date.desc())
        .limit(1)
    )
    
    return result.scalars().first()


async def calculate_continuous_days(db: AsyncSession, account_id: int) -> int:
    """计算连续签到天数"""
    from datetime import date, timedelta
    
    # 获取最新的签到记录
    latest_check_in = await get_latest_check_in(db, account_id)
    
    if not latest_check_in:
        # 如果没有签到记录，连续天数为1
        return 1
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    if latest_check_in.check_in_date == yesterday:
        # 如果最新签到是昨天，则连续天数 = 昨天的连续天数 + 1
        return latest_check_in.continuous_days + 1
    else:
        # 如果最新签到不是昨天，则连续天数重新开始为1
        return 1


async def get_check_in_stats(db: AsyncSession, account_id: int) -> Dict[str, Any]:
    """获取签到统计信息"""
    # 总签到次数
    total_result = await db.execute(
        select(func.count(CheckIn.id).label('total_check_ins'))
        .where(CheckIn.account_id == account_id)
    )
    total_check_ins = total_result.scalar() or 0
    
    # 连续签到天数 - 直接获取最新签到记录中的continuous_days字段
    latest_check_in = await get_latest_check_in(db, account_id)
    continuous_days = latest_check_in.continuous_days if latest_check_in else 0
    
    # 最长连续签到天数
    longest_continuous = await get_longest_continuous_days(db, account_id)
    
    # 本月签到次数
    today = date.today()
    month_start = date(today.year, today.month, 1)
    
    month_result = await db.execute(
        select(func.count(CheckIn.id).label('month_check_ins'))
        .where(
            and_(
                CheckIn.account_id == account_id,
                CheckIn.check_in_date >= month_start
            )
        )
    )
    this_month_check_ins = month_result.scalar() or 0
    
    return {
        "total_check_ins": total_check_ins,
        "continuous_days": continuous_days,
        "longest_continuous": longest_continuous,
        "this_month_check_ins": this_month_check_ins
    }


async def get_longest_continuous_days(db: AsyncSession, account_id: int) -> int:
    """获取最长连续签到天数"""
    # 获取所有签到记录，按日期排序
    result = await db.execute(
        select(CheckIn.check_in_date)
        .where(CheckIn.account_id == account_id)
        .order_by(CheckIn.check_in_date.desc())
    )
    
    check_in_dates = [record.check_in_date for record in result.fetchall()]
    
    if not check_in_dates:
        return 0
    
    max_continuous = 1
    current_continuous = 1
    
    for i in range(1, len(check_in_dates)):
        if (check_in_dates[i-1] - check_in_dates[i]).days == 1:
            current_continuous += 1
        else:
            max_continuous = max(max_continuous, current_continuous)
            current_continuous = 1
    
    return max(max_continuous, current_continuous)


async def get_check_in_history(db: AsyncSession, account_id: int, skip: int = 0, limit: int = 20) -> List[CheckIn]:
    """获取签到历史记录"""
    result = await db.execute(
        select(CheckIn)
        .where(CheckIn.account_id == account_id)
        .order_by(desc(CheckIn.check_in_date))
        .offset(skip)
        .limit(limit)
    )
    
    return result.scalars().all()


async def get_user_points_balance(db: AsyncSession, account_id: int) -> Dict[str, int]:
    """获取用户积分余额"""
    result = await db.execute(
        select(func.coalesce(func.sum(Points.points), 0))
        .where(Points.account_id == account_id)
    )
    
    total_balance = result.scalar() or 0
    
    return {
        "total_balance": total_balance,
        "available_balance": total_balance,
        "frozen_balance": 0
    }
