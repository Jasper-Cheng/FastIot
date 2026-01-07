from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.api.utils import extract_token_info, log_operation_with_token
from app.crud.feedback import feedback
from app.db.models.feedback import Feedback
from app.db.models.account import Account
from app.models.user_operation_log import OperationTypeEnum

router = APIRouter()


@router.get("/feedback/list")
async def get_feedback_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    accountName: Optional[str] = Query(None, description="账号名称搜索"),
    name: Optional[str] = Query(None, description="反馈人姓名搜索"),
    type: Optional[str] = Query(None, description="反馈类型筛选"),
    status: Optional[str] = Query(None, description="反馈状态筛选"),
    source: Optional[str] = Query(None, description="来源筛选"),
    hasReply: Optional[bool] = Query(None, description="是否已回复"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取反馈列表"""
    skip = (page - 1) * pageSize
    
    feedbacks, total = await feedback.get_feedbacks_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        account_name=accountName,
        name=name,
        type=type,
        status=status,
        source=source,
        has_reply=hasReply
    )
    
    items = []
    for fb in feedbacks:
        # 获取账号信息
        account_result = await db.execute(
            select(Account).filter(Account.id == fb.account_id)
        )
        account = account_result.scalar_one_or_none()
        
        items.append({
            "id": fb.id,
            "accountId": fb.account_id,
            "accountName": account.nickname if account else None,
            "name": fb.name,
            "type": fb.type,
            "content": fb.content,
            "status": fb.status,
            "source": fb.source,
            "contactInfo": fb.contact_info,
            "replay": fb.replay,
            "processedAt": fb.processed_at.strftime("%Y-%m-%d %H:%M:%S") if fb.processed_at else None,
            "extra": fb.extra or {},
            "createdAt": fb.created_at.strftime("%Y-%m-%d %H:%M:%S") if fb.created_at else None,
            "updatedAt": fb.updated_at.strftime("%Y-%m-%d %H:%M:%S") if fb.updated_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.put("/feedback/{id}/reply")
async def reply_feedback(
    id: int,
    reply_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """回复反馈"""
    # 验证反馈是否存在
    fb = await feedback.get(db, id)
    if not fb:
        raise HTTPException(status_code=404, detail="反馈不存在")
    
    # 更新反馈状态和回复内容
    status = reply_data.get("status", fb.status)
    replay = reply_data.get("replay")
    
    # 保存更新前的状态用于日志
    old_status = fb.status
    
    updated_fb = await feedback.update_status(db, id=id, status=status, replay=replay)
    if not updated_fb:
        raise HTTPException(status_code=500, detail="更新失败")
    
    # 获取账号信息
    account_result = await db.execute(
        select(Account).filter(Account.id == updated_fb.account_id)
    )
    account = account_result.scalar_one_or_none()
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.feedback_reply,
        description=f"回复反馈：{updated_fb.name} - {old_status} -> {updated_fb.status}",
        extra={
            "feedback_id": id,
            "account_id": updated_fb.account_id,
            "account_name": account.nickname if account else None,
            "name": updated_fb.name,
            "type": updated_fb.type,
            "old_status": old_status,
            "new_status": updated_fb.status,
            "has_reply": bool(replay)
        }
    )
    
    return {
        "id": updated_fb.id,
        "accountId": updated_fb.account_id,
        "accountName": account.nickname if account else None,
        "name": updated_fb.name,
        "type": updated_fb.type,
        "content": updated_fb.content,
        "status": updated_fb.status,
        "source": updated_fb.source,
        "contactInfo": updated_fb.contact_info,
        "replay": updated_fb.replay,
        "processedAt": updated_fb.processed_at.strftime("%Y-%m-%d %H:%M:%S") if updated_fb.processed_at else None,
        "updatedAt": updated_fb.updated_at.strftime("%Y-%m-%d %H:%M:%S") if updated_fb.updated_at else None
    }


@router.put("/feedback/{id}/status")
async def update_feedback_status(
    id: int,
    status_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新反馈状态"""
    # 验证反馈是否存在
    fb = await feedback.get(db, id)
    if not fb:
        raise HTTPException(status_code=404, detail="反馈不存在")
    
    status = status_data.get("status")
    if not status:
        raise HTTPException(status_code=400, detail="状态不能为空")
    
    # 保存更新前的状态用于日志
    old_status = fb.status
    
    updated_fb = await feedback.update_status(db, id=id, status=status)
    if not updated_fb:
        raise HTTPException(status_code=500, detail="更新失败")
    
    # 获取账号信息
    account_result = await db.execute(
        select(Account).filter(Account.id == updated_fb.account_id)
    )
    account = account_result.scalar_one_or_none()
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.feedback_status_update,
        description=f"更新反馈状态：{updated_fb.name} - {old_status} -> {updated_fb.status}",
        extra={
            "feedback_id": id,
            "account_id": updated_fb.account_id,
            "account_name": account.nickname if account else None,
            "name": updated_fb.name,
            "type": updated_fb.type,
            "old_status": old_status,
            "new_status": updated_fb.status
        }
    )
    
    return {
        "id": updated_fb.id,
        "accountId": updated_fb.account_id,
        "accountName": account.nickname if account else None,
        "name": updated_fb.name,
        "type": updated_fb.type,
        "content": updated_fb.content,
        "status": updated_fb.status,
        "source": updated_fb.source,
        "contactInfo": updated_fb.contact_info,
        "replay": updated_fb.replay,
        "processedAt": updated_fb.processed_at.strftime("%Y-%m-%d %H:%M:%S") if updated_fb.processed_at else None,
        "updatedAt": updated_fb.updated_at.strftime("%Y-%m-%d %H:%M:%S") if updated_fb.updated_at else None
    }

