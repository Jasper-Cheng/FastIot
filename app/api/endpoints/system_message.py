"""
系统消息API端点
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.crud.system_message import (
    get_system_messages as crud_get_system_messages,
)
from app.models.system_message import SystemMessage, Platform, SystemMessageType, SystemMessagePriority

router = APIRouter()


@router.get("/", response_model=List[SystemMessage])
async def get_system_messages(
    *,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=500, description="限制数量"),
    type: Optional[str] = Query(None, description="消息类型 (notification, announcement, alert, maintenance, update)"),
    priority: Optional[str] = Query(None, description="优先级 (low, normal, high, urgent)"),
    platform: Optional[str] = Query(None, description="平台 (android, ios, web, desktop)")
):
    """获取系统消息列表
    
    支持按类型、优先级、平台筛选
    """
    # 验证 type 参数
    if type is not None:
        try:
            SystemMessageType(type)
        except ValueError:
            valid_types = [t.value for t in SystemMessageType]
            raise HTTPException(
                status_code=400, 
                detail=f"无效的消息类型 '{type}'。有效值: {', '.join(valid_types)}"
            )
    
    # 验证 priority 参数
    if priority is not None:
        try:
            SystemMessagePriority(priority)
        except ValueError:
            valid_priorities = [p.value for p in SystemMessagePriority]
            raise HTTPException(
                status_code=400, 
                detail=f"无效的优先级 '{priority}'。有效值: {', '.join(valid_priorities)}"
            )
    
    # 验证 platform 参数
    platform_enum = None
    if platform is not None:
        try:
            platform_enum = Platform(platform)
        except ValueError:
            valid_platforms = [p.value for p in Platform]
            raise HTTPException(
                status_code=400, 
                detail=f"无效的平台 '{platform}'。有效值: {', '.join(valid_platforms)}"
            )
    
    # 获取消息（所有过滤都在数据库层面完成）
    messages = await crud_get_system_messages(
        db=db,
        skip=skip,
        limit=limit,
        type=type,
        priority=priority,
        platform=platform_enum
    )
    
    return messages
