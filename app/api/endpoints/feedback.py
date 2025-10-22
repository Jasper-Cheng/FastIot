from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api.dependencies import get_db, get_current_account, get_current_admin
from app.crud.feedback import feedback
from app.models.feedback import Feedback, FeedbackCreate, FeedbackUpdate
from app.db.models.account import Account
from app.db.models.admin import Admin

router = APIRouter()


@router.post("/", response_model=Feedback)
def create_feedback(
    *,
    db: Session = Depends(get_db),
    feedback_in: FeedbackCreate,
    current_account: Account = Depends(get_current_account)
):
    """创建意见反馈"""
    # 设置当前用户ID
    feedback_in.account_id = current_account.id
    return feedback.create(db=db, obj_in=feedback_in)


@router.get("/", response_model=List[Feedback])
def get_feedbacks(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    order_by: str = Query("created_at"),
    order_desc: bool = Query(True),
    current_admin: Admin = Depends(get_current_admin)
):
    """获取意见反馈列表（管理员）"""
    return feedback.get_multi(
        db=db,
        skip=skip,
        limit=limit,
        type=type,
        status=status,
        source=source,
        priority=priority,
        order_by=order_by,
        order_desc=order_desc
    )


@router.get("/my", response_model=List[Feedback])
def get_my_feedbacks(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_account: Account = Depends(get_current_account)
):
    """获取我的反馈列表"""
    return feedback.get_by_account(
        db=db,
        account_id=current_account.id,
        skip=skip,
        limit=limit
    )


@router.get("/pending")
def get_pending_feedbacks(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_admin: Admin = Depends(get_current_admin)
):
    """获取待处理反馈列表"""
    return feedback.get_by_status(db=db, status="pending", skip=skip, limit=limit)


@router.get("/statistics")
def get_feedback_statistics(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """获取反馈统计信息"""
    return feedback.get_statistics(db=db)


@router.get("/pending/count")
def get_pending_count(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """获取待处理反馈数量"""
    count = feedback.get_pending_count(db=db)
    return {"pending_count": count}


@router.get("/{feedback_id}", response_model=Feedback)
def get_feedback(
    *,
    db: Session = Depends(get_db),
    feedback_id: int,
    current_account: Account = Depends(get_current_account)
):
    """根据ID获取意见反馈"""
    feedback_obj = feedback.get(db=db, id=feedback_id)
    if not feedback_obj:
        raise HTTPException(
            status_code=404,
            detail="反馈不存在"
        )
    
    # 只有反馈创建者或管理员可以查看
    if feedback_obj.account_id != current_account.id and current_account.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="无权限查看此反馈"
        )
    
    return feedback_obj


@router.put("/{feedback_id}", response_model=Feedback)
def update_feedback(
    *,
    db: Session = Depends(get_db),
    feedback_id: int,
    feedback_in: FeedbackUpdate,
    current_account: Account = Depends(get_current_account)
):
    """更新意见反馈"""
    feedback_obj = feedback.get(db=db, id=feedback_id)
    if not feedback_obj:
        raise HTTPException(
            status_code=404,
            detail="反馈不存在"
        )
    
    # 只有反馈创建者可以更新
    if feedback_obj.account_id != current_account.id:
        raise HTTPException(
            status_code=403,
            detail="无权限修改此反馈"
        )
    
    # 用户只能更新部分字段
    user_update_fields = ["title", "content", "priority", "source", "contact_info", "extra"]
    update_data = {k: v for k, v in feedback_in.dict(exclude_unset=True).items() if k in user_update_fields}
    
    if update_data:
        from app.models.feedback import FeedbackUpdate
        user_update = FeedbackUpdate(**update_data)
        return feedback.update(db=db, db_obj=feedback_obj, obj_in=user_update)
    
    return feedback_obj


@router.put("/{feedback_id}/status")
def update_feedback_status(
    *,
    db: Session = Depends(get_db),
    feedback_id: int,
    status: str,
    replay: Optional[str] = Query(None),
    current_admin: Admin = Depends(get_current_admin)
):
    """更新反馈状态（管理员）"""
    feedback_obj = feedback.get(db=db, id=feedback_id)
    if not feedback_obj:
        raise HTTPException(
            status_code=404,
            detail="反馈不存在"
        )
    
    valid_statuses = ["pending", "processing", "resolved", "rejected", "closed"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"无效的状态，必须是: {', '.join(valid_statuses)}"
        )
    
    return feedback.update_status(
        db=db,
        id=feedback_id,
        status=status,
        replay=replay
    )


@router.delete("/{feedback_id}")
def delete_feedback(
    *,
    db: Session = Depends(get_db),
    feedback_id: int,
    current_account: Account = Depends(get_current_account)
):
    """删除意见反馈"""
    feedback_obj = feedback.get(db=db, id=feedback_id)
    if not feedback_obj:
        raise HTTPException(
            status_code=404,
            detail="反馈不存在"
        )
    
    # 只有反馈创建者或管理员可以删除
    if feedback_obj.account_id != current_account.id and current_account.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="无权限删除此反馈"
        )
    
    feedback.remove(db=db, id=feedback_id)
    return {"message": "反馈已删除"}


@router.get("/search/{keyword}")
def search_feedbacks(
    *,
    db: Session = Depends(get_db),
    keyword: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_admin: Admin = Depends(get_current_admin)
):
    """搜索意见反馈"""
    return feedback.search(db=db, keyword=keyword, skip=skip, limit=limit)
