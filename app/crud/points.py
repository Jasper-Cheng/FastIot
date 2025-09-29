from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, or_
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from app.db.models.points import Points
from app.db.models.check_in import CheckIn


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


async def get_points_history(
    db: AsyncSession, 
    account_id: int, 
    skip: int = 0, 
    limit: int = 20,
    type: Optional[str] = None
) -> List[Points]:
    """获取积分历史记录"""
    query = select(Points).where(Points.account_id == account_id)
    
    if type:
        query = query.where(Points.type == type)
    
    result = await db.execute(
        query.order_by(desc(Points.created_at))
        .offset(skip)
        .limit(limit)
    )
    
    return result.scalars().all()


async def get_points_stats(db: AsyncSession, account_id: int) -> Dict[str, Any]:
    """获取积分统计信息"""
    # 总获得积分
    earned_result = await db.execute(
        select(func.coalesce(func.sum(Points.points), 0))
        .where(
            and_(
                Points.account_id == account_id,
                Points.points > 0
            )
        )
    )
    total_earned = earned_result.scalar() or 0
    
    # 总消耗积分
    spent_result = await db.execute(
        select(func.coalesce(func.sum(func.abs(Points.points)), 0))
        .where(
            and_(
                Points.account_id == account_id,
                Points.points < 0
            )
        )
    )
    total_spent = spent_result.scalar() or 0
    
    # 当前余额
    current_balance = total_earned - total_spent
    
    # 本月获得积分
    today = date.today()
    month_start = date(today.year, today.month, 1)
    
    month_earned_result = await db.execute(
        select(func.coalesce(func.sum(Points.points), 0))
        .where(
            and_(
                Points.account_id == account_id,
                Points.points > 0,
                Points.created_at >= month_start
            )
        )
    )
    this_month_earned = month_earned_result.scalar() or 0
    
    # 本月消耗积分
    month_spent_result = await db.execute(
        select(func.coalesce(func.sum(func.abs(Points.points)), 0))
        .where(
            and_(
                Points.account_id == account_id,
                Points.points < 0,
                Points.created_at >= month_start
            )
        )
    )
    this_month_spent = month_spent_result.scalar() or 0
    
    # 按类型统计积分
    type_stats = await get_points_by_type(db, account_id)
    
    return {
        "total_earned": total_earned,
        "total_spent": total_spent,
        "current_balance": current_balance,
        "this_month_earned": this_month_earned,
        "this_month_spent": this_month_spent,
        "check_in_points": type_stats.get("check_in", 0),
        "task_points": type_stats.get("task", 0),
        "reward_points": type_stats.get("reward", 0),
        "exchange_points": type_stats.get("exchange", 0)
    }


async def get_points_by_type(db: AsyncSession, account_id: int) -> Dict[str, int]:
    """按类型统计积分"""
    result = await db.execute(
        select(
            Points.type,
            func.coalesce(func.sum(Points.points), 0).label('total_points')
        )
        .where(Points.account_id == account_id)
        .group_by(Points.type)
    )
    
    type_stats = {}
    for record in result.fetchall():
        type_stats[record.type] = record.total_points
    
    return type_stats


async def add_points(db: AsyncSession, points_data: Dict[str, Any]) -> Points:
    """添加积分"""
    # 获取当前余额
    current_balance = await get_user_points_balance(db, points_data["account_id"])
    points_data["balance"] = current_balance["total_balance"] + points_data["points"]
    
    points = Points(**points_data)
    db.add(points)
    await db.commit()
    await db.refresh(points)
    return points


async def deduct_points(db: AsyncSession, points_data: Dict[str, Any]) -> Points:
    """扣除积分"""
    # 获取当前余额
    current_balance = await get_user_points_balance(db, points_data["account_id"])
    points_data["balance"] = current_balance["total_balance"] + points_data["points"]  # points_data["points"] 已经是负数
    
    points = Points(**points_data)
    db.add(points)
    await db.commit()
    await db.refresh(points)
    return points


async def get_recent_points(db: AsyncSession, account_id: int, limit: int = 10) -> List[Points]:
    """获取最近的积分记录"""
    result = await db.execute(
        select(Points)
        .where(Points.account_id == account_id)
        .order_by(desc(Points.created_at))
        .limit(limit)
    )
    
    return result.scalars().all()


async def get_points_by_date_range(
    db: AsyncSession, 
    account_id: int, 
    start_date: date, 
    end_date: date
) -> List[Points]:
    """获取指定日期范围内的积分记录"""
    result = await db.execute(
        select(Points)
        .where(
            and_(
                Points.account_id == account_id,
                Points.created_at >= start_date,
                Points.created_at <= end_date
            )
        )
        .order_by(desc(Points.created_at))
    )
    
    return result.scalars().all()


async def get_points_summary_by_month(db: AsyncSession, account_id: int, year: int) -> List[Dict[str, Any]]:
    """获取按月份的积分汇总"""
    result = await db.execute(
        select(
            func.extract('month', Points.created_at).label('month'),
            func.coalesce(func.sum(Points.points), 0).label('total_points'),
            func.count(Points.id).label('total_records')
        )
        .where(
            and_(
                Points.account_id == account_id,
                func.extract('year', Points.created_at) == year
            )
        )
        .group_by(func.extract('month', Points.created_at))
        .order_by(func.extract('month', Points.created_at))
    )
    
    monthly_summary = []
    for record in result.fetchall():
        monthly_summary.append({
            "month": int(record.month),
            "total_points": record.total_points,
            "total_records": record.total_records
        })
    
    return monthly_summary
