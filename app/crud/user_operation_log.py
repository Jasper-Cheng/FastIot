from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, asc, select, func
from typing import List, Optional, Dict, Any, Tuple
from app.db.models.user_operation_log import UserOperationLog
from app.models.user_operation_log import UserOperationLogCreate, UserOperationLogUpdate
from datetime import datetime

class CRUDUserOperationLog:
    async def create(self, db: AsyncSession, *, obj_in: UserOperationLogCreate, account_id: int) -> UserOperationLog:
        """创建用户操作记录"""
        db_obj = UserOperationLog(**obj_in.dict(), account_id=account_id)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get(self, db: AsyncSession, id: int) -> Optional[UserOperationLog]:
        """根据ID获取操作记录"""
        result = await db.execute(select(UserOperationLog).where(UserOperationLog.id == id))
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[UserOperationLog]:
        """获取操作记录列表"""
        query = select(UserOperationLog)

        # 过滤条件
        if account_id:
            query = query.where(UserOperationLog.account_id == account_id)
        if operation_type:
            query = query.where(UserOperationLog.operation_type == operation_type)

        # 排序
        order_column = getattr(UserOperationLog, order_by, UserOperationLog.created_at)
        if order_desc:
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(asc(order_column))

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_account(self, db: AsyncSession, *, account_id: int, skip: int = 0, limit: int = 100) -> List[UserOperationLog]:
        """获取指定用户的操作记录列表"""
        result = await db.execute(
            select(UserOperationLog)
            .where(UserOperationLog.account_id == account_id)
            .order_by(desc(UserOperationLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_operation_type(self, db: AsyncSession, *, operation_type: str, skip: int = 0, limit: int = 100) -> List[UserOperationLog]:
        """根据操作类型获取记录列表"""
        result = await db.execute(
            select(UserOperationLog)
            .where(UserOperationLog.operation_type == operation_type)
            .order_by(desc(UserOperationLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


    async def update(self, db: AsyncSession, *, db_obj: UserOperationLog, obj_in: UserOperationLogUpdate) -> UserOperationLog:
        """更新操作记录"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[UserOperationLog]:
        """删除操作记录"""
        result = await db.execute(select(UserOperationLog).where(UserOperationLog.id == id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    async def search(self, db: AsyncSession, *, keyword: str, skip: int = 0, limit: int = 100) -> List[UserOperationLog]:
        """搜索操作记录"""
        result = await db.execute(
            select(UserOperationLog)
            .where(UserOperationLog.description.contains(keyword))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_statistics(self, db: AsyncSession, *, account_id: Optional[int] = None) -> Dict[str, Any]:
        """获取操作统计信息"""
        base_query = select(UserOperationLog)
        if account_id:
            base_query = base_query.where(UserOperationLog.account_id == account_id)

        # 按操作类型统计
        type_result = await db.execute(
            base_query.add_columns(UserOperationLog.operation_type, func.count(UserOperationLog.id))
            .group_by(UserOperationLog.operation_type)
        )
        type_stats = {row.operation_type: row[1] for row in type_result.fetchall()}


        # 总数量
        total_result = await db.execute(
            base_query.add_columns(func.count(UserOperationLog.id))
        )
        total_count = total_result.scalar()

        # 今日操作数量
        today_result = await db.execute(
            base_query.where(func.date(UserOperationLog.created_at) == func.curdate())
            .add_columns(func.count(UserOperationLog.id))
        )
        today_count = today_result.scalar()

        return {
            "operation_type_statistics": type_stats,
            "total_count": total_count,
            "today_count": today_count
        }

    async def get_recent_operations(self, db: AsyncSession, *, account_id: int, hours: int = 24, limit: int = 50) -> List[UserOperationLog]:
        """获取最近N小时的操作记录"""
        from datetime import datetime, timedelta
        since_time = datetime.now() - timedelta(hours=hours)
        
        result = await db.execute(
            select(UserOperationLog)
            .where(
                and_(
                    UserOperationLog.account_id == account_id,
                    UserOperationLog.created_at >= since_time
                )
            )
            .order_by(desc(UserOperationLog.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_logs_with_pagination(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 10,
        account_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Tuple[List[UserOperationLog], int]:
        """获取操作日志列表（支持分页和搜索）"""
        query = select(UserOperationLog)
        count_query = select(func.count(UserOperationLog.id))
        
        # 构建搜索条件
        conditions = []
        if account_id:
            conditions.append(UserOperationLog.account_id == account_id)
        if operation_type:
            conditions.append(UserOperationLog.operation_type == operation_type)
        if start_time:
            try:
                start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                conditions.append(UserOperationLog.created_at >= start_dt)
            except ValueError:
                pass
        if end_time:
            try:
                end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                conditions.append(UserOperationLog.created_at <= end_dt)
            except ValueError:
                pass
        
        if conditions:
            query = query.filter(and_(*conditions))
            count_query = count_query.filter(and_(*conditions))
        
        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 获取分页数据，按创建时间倒序
        result = await db.execute(
            query.order_by(desc(UserOperationLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        logs = result.scalars().all()
        
        return logs, total

user_operation_log = CRUDUserOperationLog()
