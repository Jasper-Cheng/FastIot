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


async def get_latest_points_by_all_accounts(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[Points]:
    """获取所有用户的最新一条积分记录
    
    使用子查询获取每个用户的最新记录
    """
    from sqlalchemy import text
    
    # 使用窗口函数获取每个用户的最新记录（MySQL 8.0+ 支持）
    # 如果数据库不支持窗口函数，可以使用子查询方式
    query = text("""
        SELECT p.*
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY created_at DESC) as rn
            FROM points
        ) p
        WHERE p.rn = 1
        ORDER BY p.created_at DESC
        LIMIT :limit_val OFFSET :skip_val
    """)
    
    result = await db.execute(query, {"limit_val": limit, "skip_val": skip})
    rows = result.fetchall()
    
    # 将结果转换为 Points 对象
    points_list = []
    for row in rows:
        # SQLAlchemy Row 对象支持通过列名访问，也支持通过索引访问
        try:
            # 尝试通过列名访问（推荐方式）
            point = Points(
                id=row.id,
                account_id=row.account_id,
                points=row.points,
                balance=row.balance,
                type=row.type,
                description=row.description,
                extra=row.extra,
                created_at=row.created_at
            )
        except (AttributeError, KeyError):
            # 如果列名访问失败，使用索引访问（兼容性处理）
            point = Points(
                id=row[0],
                account_id=row[1],
                points=row[2],
                balance=row[3],
                type=row[4],
                description=row[5],
                extra=row[6],
                created_at=row[7]
            )
        points_list.append(point)
    
    return points_list


async def get_latest_points_by_all_accounts_count(db: AsyncSession) -> int:
    """获取有积分记录的用户总数"""
    result = await db.execute(
        select(func.count(func.distinct(Points.account_id)))
    )
    return result.scalar() or 0


async def get_user_latest_points(db: AsyncSession, account_id: int) -> Optional[Points]:
    """获取用户的最新一条积分记录"""
    result = await db.execute(
        select(Points)
        .where(Points.account_id == account_id)
        .order_by(desc(Points.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()