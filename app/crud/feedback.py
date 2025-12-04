from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, asc, select, func
from typing import List, Optional, Dict, Any
from app.db.models.feedback import Feedback
from app.models.feedback import FeedbackCreate, FeedbackUpdate


class CRUDFeedback:
    async def create(self, db: AsyncSession, *, obj_in: FeedbackCreate, account_id: int) -> Feedback:
        """创建意见反馈"""
        db_obj = Feedback(**obj_in.dict(), account_id=account_id)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get(self, db: AsyncSession, id: int) -> Optional[Feedback]:
        """根据ID获取意见反馈"""
        result = await db.execute(select(Feedback).where(Feedback.id == id))
        return result.scalar_one_or_none()

    async def get_multi(
        self, 
        db: AsyncSession, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        account_id: Optional[int] = None,
        type: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[Feedback]:
        """获取意见反馈列表"""
        query = select(Feedback)
        
        # 过滤条件
        if account_id:
            query = query.where(Feedback.account_id == account_id)
        if type:
            query = query.where(Feedback.type == type)
        if status:
            query = query.where(Feedback.status == status)
        if source:
            query = query.where(Feedback.source == source)
        
        # 排序
        order_column = getattr(Feedback, order_by, Feedback.created_at)
        if order_desc:
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(asc(order_column))
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_account(self, db: AsyncSession, *, account_id: int, skip: int = 0, limit: int = 100) -> List[Feedback]:
        """获取指定用户的反馈列表"""
        result = await db.execute(
            select(Feedback)
            .where(Feedback.account_id == account_id)
            .order_by(desc(Feedback.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_family_members(
        self, 
        db: AsyncSession, 
        *, 
        account_id: int, 
        skip: int = 0, 
        limit: int = 100,
        type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Feedback]:
        """获取账号及其所在家庭所有成员的反馈列表"""
        from app.db.models.family_member import FamilyMember
        
        # 获取账号所在的所有家庭
        families_result = await db.execute(
            select(FamilyMember.family_id)
            .where(FamilyMember.account_id == account_id)
        )
        family_ids = [row[0] for row in families_result.fetchall()]
        
        # 获取所有家庭成员账号ID
        all_account_ids = [account_id]  # 包含自己
        if family_ids:
            members_result = await db.execute(
                select(FamilyMember.account_id)
                .where(FamilyMember.family_id.in_(family_ids))
            )
            member_account_ids = [row[0] for row in members_result.fetchall()]
            all_account_ids.extend(member_account_ids)
            # 去重
            all_account_ids = list(set(all_account_ids))
        
        # 构建查询
        query = select(Feedback).where(Feedback.account_id.in_(all_account_ids))
        
        # 添加过滤条件
        if type:
            query = query.where(Feedback.type == type)
        if status:
            query = query.where(Feedback.status == status)
        
        # 获取所有相关账号的反馈
        result = await db.execute(
            query
            .order_by(desc(Feedback.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_pending_count(self, db: AsyncSession) -> int:
        """获取待处理反馈数量"""
        result = await db.execute(select(func.count(Feedback.id)).where(Feedback.status == "pending"))
        return result.scalar()

    async def get_by_status(self, db: AsyncSession, *, status: str, skip: int = 0, limit: int = 100) -> List[Feedback]:
        """根据状态获取反馈列表"""
        result = await db.execute(
            select(Feedback)
            .where(Feedback.status == status)
            .order_by(desc(Feedback.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def update(self, db: AsyncSession, *, db_obj: Feedback, obj_in: FeedbackUpdate) -> Feedback:
        """更新意见反馈"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_status(self, db: AsyncSession, *, id: int, status: str, replay: Optional[str] = None) -> Optional[Feedback]:
        """更新反馈状态"""
        result = await db.execute(select(Feedback).where(Feedback.id == id))
        feedback = result.scalar_one_or_none()
        if feedback:
            feedback.status = status
            if replay:
                feedback.replay = replay
            if status in ["resolved", "rejected", "closed"]:
                from datetime import datetime
                feedback.processed_at = datetime.now()
            db.add(feedback)
            await db.commit()
            await db.refresh(feedback)
        return feedback

    async def remove(self, db: AsyncSession, *, id: int) -> Optional[Feedback]:
        """删除意见反馈"""
        result = await db.execute(select(Feedback).where(Feedback.id == id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    async def search(self, db: AsyncSession, *, keyword: str, skip: int = 0, limit: int = 100) -> List[Feedback]:
        """搜索意见反馈"""
        result = await db.execute(
            select(Feedback)
            .where(
                or_(
                    Feedback.content.contains(keyword),
                    Feedback.replay.contains(keyword)
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_statistics(self, db: AsyncSession) -> Dict[str, Any]:
        """获取反馈统计信息"""
        # 按类型统计
        type_result = await db.execute(
            select(Feedback.type, func.count(Feedback.id))
            .group_by(Feedback.type)
        )
        type_stats = dict(type_result.fetchall())
        
        # 按状态统计
        status_result = await db.execute(
            select(Feedback.status, func.count(Feedback.id))
            .group_by(Feedback.status)
        )
        status_stats = dict(status_result.fetchall())
        
        # 按来源统计
        source_result = await db.execute(
            select(Feedback.source, func.count(Feedback.id))
            .group_by(Feedback.source)
        )
        source_stats = dict(source_result.fetchall())
        
        # 总数量
        total_result = await db.execute(select(func.count(Feedback.id)))
        total_count = total_result.scalar()
        
        return {
            "type_statistics": type_stats,
            "status_statistics": status_stats,
            "source_statistics": source_stats,
            "total_count": total_count
        }


feedback = CRUDFeedback()
