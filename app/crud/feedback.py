from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from typing import List, Optional, Dict, Any
from app.db.models.feedback import Feedback
from app.models.feedback import FeedbackCreate, FeedbackUpdate


class CRUDFeedback:
    def create(self, db: Session, *, obj_in: FeedbackCreate) -> Feedback:
        """创建意见反馈"""
        db_obj = Feedback(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, id: int) -> Optional[Feedback]:
        """根据ID获取意见反馈"""
        return db.query(Feedback).filter(Feedback.id == id).first()

    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        account_id: Optional[int] = None,
        type: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        priority: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[Feedback]:
        """获取意见反馈列表"""
        query = db.query(Feedback)
        
        # 过滤条件
        if account_id:
            query = query.filter(Feedback.account_id == account_id)
        if type:
            query = query.filter(Feedback.type == type)
        if status:
            query = query.filter(Feedback.status == status)
        if source:
            query = query.filter(Feedback.source == source)
        if priority:
            query = query.filter(Feedback.priority == priority)
        
        # 排序
        order_column = getattr(Feedback, order_by, Feedback.created_at)
        if order_desc:
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(asc(order_column))
        
        return query.offset(skip).limit(limit).all()

    def get_by_account(self, db: Session, *, account_id: int, skip: int = 0, limit: int = 100) -> List[Feedback]:
        """获取指定用户的反馈列表"""
        return (
            db.query(Feedback)
            .filter(Feedback.account_id == account_id)
            .order_by(desc(Feedback.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_pending_count(self, db: Session) -> int:
        """获取待处理反馈数量"""
        return db.query(Feedback).filter(Feedback.status == "pending").count()

    def get_by_status(self, db: Session, *, status: str, skip: int = 0, limit: int = 100) -> List[Feedback]:
        """根据状态获取反馈列表"""
        return (
            db.query(Feedback)
            .filter(Feedback.status == status)
            .order_by(desc(Feedback.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, db: Session, *, db_obj: Feedback, obj_in: FeedbackUpdate) -> Feedback:
        """更新意见反馈"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(self, db: Session, *, id: int, status: str, replay: Optional[str] = None) -> Optional[Feedback]:
        """更新反馈状态"""
        feedback = db.query(Feedback).filter(Feedback.id == id).first()
        if feedback:
            feedback.status = status
            if replay:
                feedback.replay = replay
            if status in ["resolved", "rejected", "closed"]:
                from datetime import datetime
                feedback.processed_at = datetime.now()
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
        return feedback

    def remove(self, db: Session, *, id: int) -> Optional[Feedback]:
        """删除意见反馈"""
        obj = db.query(Feedback).get(id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    def search(self, db: Session, *, keyword: str, skip: int = 0, limit: int = 100) -> List[Feedback]:
        """搜索意见反馈"""
        return (
            db.query(Feedback)
            .filter(
                or_(
                    Feedback.title.contains(keyword),
                    Feedback.content.contains(keyword),
                    Feedback.replay.contains(keyword)
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_statistics(self, db: Session) -> Dict[str, Any]:
        """获取反馈统计信息"""
        from sqlalchemy import func
        
        # 按类型统计
        type_stats = (
            db.query(Feedback.type, func.count(Feedback.id))
            .group_by(Feedback.type)
            .all()
        )
        
        # 按状态统计
        status_stats = (
            db.query(Feedback.status, func.count(Feedback.id))
            .group_by(Feedback.status)
            .all()
        )
        
        # 按来源统计
        source_stats = (
            db.query(Feedback.source, func.count(Feedback.id))
            .group_by(Feedback.source)
            .all()
        )
        
        return {
            "type_statistics": dict(type_stats),
            "status_statistics": dict(status_stats),
            "source_statistics": dict(source_stats),
            "total_count": db.query(Feedback).count()
        }


feedback = CRUDFeedback()
