from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.user_operation_log import user_operation_log
from app.db.models.user_operation_log import UserOperationLog
from app.db.models.account import Account

router = APIRouter()


@router.get("/log/list")
async def get_log_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    accountId: Optional[int] = Query(None, description="操作人ID"),
    operationType: Optional[str] = Query(None, description="操作类型"),
    startTime: Optional[str] = Query(None, description="开始时间"),
    endTime: Optional[str] = Query(None, description="结束时间"),
    role: Optional[str] = Query(None, description="角色筛选（admin/user）"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取操作日志列表"""
    skip = (page - 1) * pageSize
    
    logs, total = await user_operation_log.get_logs_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        account_id=accountId,
        operation_type=operationType,
        start_time=startTime,
        end_time=endTime,
        role=role
    )
    
    items = []
    for log in logs:
        # 获取账号信息
        account_result = await db.execute(
            select(Account).filter(Account.id == log.account_id)
        )
        account = account_result.scalar_one_or_none()
        
        items.append({
            "id": log.id,
            "accountId": log.account_id,
            "accountName": account.nickname if account else None,
            "role": account.role if account else None,
            "operationType": log.operation_type,
            "description": log.description,
            "extra": log.extra or {},
            "createdAt": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else None
        })
    
    return {
        "items": items,
        "total": total
    }

