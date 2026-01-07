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