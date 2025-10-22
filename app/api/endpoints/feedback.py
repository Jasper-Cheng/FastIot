from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.api.dependencies import get_db, get_current_account, get_current_admin
from app.crud.feedback import feedback
from app.models.feedback import Feedback, FeedbackCreate, FeedbackUpdate
from app.db.models.account import Account
from app.db.models.admin import Admin

router = APIRouter()


@router.post("/", response_model=Feedback)
async def create_feedback(
    *,
    db: AsyncSession = Depends(get_db),
    feedback_in: FeedbackCreate,
    current_account: Account = Depends(get_current_account)
):
    """创建意见反馈"""
    return await feedback.create(db=db, obj_in=feedback_in, account_id=current_account.id)


@router.get("/", response_model=List[Feedback])
async def get_feedbacks(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    order_by: str = Query("created_at"),
    order_desc: bool = Query(True),
    current_account: Account = Depends(get_current_account)
):
    """获取意见反馈列表"""
    # 根据用户角色决定返回的数据
    if current_account.role == "admin":
        # 管理员可以看到所有反馈
        return await feedback.get_multi(
            db=db,
            skip=skip,
            limit=limit,
            type=type,
            status=status,
            source=source,
            order_by=order_by,
            order_desc=order_desc
        )
    elif current_account.role == "owner":
        # 主账号可以看到自己和所有成员的反馈
        return await feedback.get_by_user_and_members(
            db=db,
            user_account_id=current_account.id,
            skip=skip,
            limit=limit
        )
    elif current_account.role == "member":
        # 成员可以看到自己和所属user的所有反馈
        # 首先找到成员所属的user
        from app.db.models.user import User
        from app.db.models.member import Member
        
        # 获取成员所属的user的account_id
        user_result = await db.execute(
            select(User.account_id)
            .join(Member, User.id == Member.user_id)
            .where(Member.account_id == current_account.id)
        )
        user_account_id = user_result.scalar_one_or_none()
        
        if user_account_id:
            # 返回user及其所有成员的反馈
            return await feedback.get_by_user_and_members(
                db=db,
                user_account_id=user_account_id,
                skip=skip,
                limit=limit
            )
        else:
            # 如果找不到所属user，只返回自己的反馈
            return await feedback.get_multi(
                db=db,
                skip=skip,
                limit=limit,
                account_id=current_account.id,
                type=type,
                status=status,
                source=source,
                order_by=order_by,
                order_desc=order_desc
            )
    else:
        # 其他角色只能看到自己的反馈
        return await feedback.get_multi(
            db=db,
            skip=skip,
            limit=limit,
            account_id=current_account.id,
            type=type,
            status=status,
            source=source,
            order_by=order_by,
            order_desc=order_desc
        )




@router.get("/{feedback_id}", response_model=Feedback)
async def get_feedback(
    *,
    db: AsyncSession = Depends(get_db),
    feedback_id: int,
    current_account: Account = Depends(get_current_account)
):
    """根据ID获取意见反馈"""
    feedback_obj = await feedback.get(db=db, id=feedback_id)
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
async def update_feedback(
    *,
    db: AsyncSession = Depends(get_db),
    feedback_id: int,
    feedback_in: FeedbackUpdate,
    current_account: Account = Depends(get_current_account)
):
    """更新意见反馈"""
    feedback_obj = await feedback.get(db=db, id=feedback_id)
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
    user_update_fields = ["type", "content", "source", "contact_info", "extra"]
    update_data = {k: v for k, v in feedback_in.dict(exclude_unset=True).items() if k in user_update_fields}
    
    if update_data:
        from app.models.feedback import FeedbackUpdate
        user_update = FeedbackUpdate(**update_data)
        return await feedback.update(db=db, db_obj=feedback_obj, obj_in=user_update)
    
    return feedback_obj


@router.put("/{feedback_id}/status")
async def update_feedback_status(
    *,
    db: AsyncSession = Depends(get_db),
    feedback_id: int,
    status: str,
    replay: Optional[str] = Query(None),
    current_admin: Admin = Depends(get_current_admin)
):
    """更新反馈状态（管理员）"""
    feedback_obj = await feedback.get(db=db, id=feedback_id)
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
    
    return await feedback.update_status(
        db=db,
        id=feedback_id,
        status=status,
        replay=replay
    )


@router.delete("/{feedback_id}")
async def delete_feedback(
    *,
    db: AsyncSession = Depends(get_db),
    feedback_id: int,
    current_account: Account = Depends(get_current_account)
):
    """删除意见反馈"""
    feedback_obj = await feedback.get(db=db, id=feedback_id)
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
    
    await feedback.remove(db=db, id=feedback_id)
    return {"message": "反馈已删除"}


@router.get("/search/{keyword}")
async def search_feedbacks(
    *,
    db: AsyncSession = Depends(get_db),
    keyword: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_admin: Admin = Depends(get_current_admin)
):
    """搜索意见反馈"""
    return await feedback.search(db=db, keyword=keyword, skip=skip, limit=limit)
