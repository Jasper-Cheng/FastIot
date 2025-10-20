"""
系统消息API端点
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.crud.system_message import (
    create_system_message,
    get_system_message,
    get_system_messages,
    get_system_messages_count,
    get_system_messages_by_platform,
    get_latest_system_messages,
    update_system_message,
    delete_system_message
)
from app.models.system_message import SystemMessage, SystemMessageList, SystemMessageCreate, SystemMessageUpdate, Platform, SystemMessageType, SystemMessagePriority
from app.api.dependencies import get_current_user
from app.models.account import Account

router = APIRouter()


@router.get("/", response_model=List[SystemMessage])
async def get_system_messages(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=500, description="限制数量"),
    type: Optional[str] = Query(None, description="消息类型 (notification, announcement, alert, maintenance, update)"),
    priority: Optional[str] = Query(None, description="优先级 (low, normal, high, urgent)"),
    platform: Optional[str] = Query(None, description="平台 (android, ios, web, desktop)"),
    days: Optional[int] = Query(None, ge=1, le=365, description="最近N天的消息")
):
    """获取系统消息列表
    
    支持按类型、优先级、平台、时间范围筛选
    """
    from datetime import timedelta
    from app.utils.time_utils import get_local_time
    
    # 验证 type 参数
    if type is not None:
        valid_types = ["notification", "announcement", "alert", "maintenance", "update"]
        if type not in valid_types:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的消息类型 '{type}'。有效值: {', '.join(valid_types)}"
            )
    
    # 验证 priority 参数
    if priority is not None:
        valid_priorities = ["low", "normal", "high", "urgent"]
        if priority not in valid_priorities:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的优先级 '{priority}'。有效值: {', '.join(valid_priorities)}"
            )
    
    # 验证 platform 参数
    if platform is not None:
        valid_platforms = ["android", "ios", "web", "desktop"]
        if platform not in valid_platforms:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的平台 '{platform}'。有效值: {', '.join(valid_platforms)}"
            )
    
    # 获取所有消息
    messages = await get_system_messages(
        db=db,
        skip=0,  # 先获取所有消息，然后应用过滤
        limit=1000,  # 设置一个较大的限制
        type=type,
        priority=priority,
        platform=Platform(platform) if platform else None
    )
    
    # 应用时间过滤
    filtered_messages = []
    for message in messages:
        # 时间过滤
        if days:
            cutoff_date = get_local_time() - timedelta(days=days)
            if message.created_at < cutoff_date:
                continue
        
        filtered_messages.append(message)
    
    # 按创建时间排序（最新的在前）
    filtered_messages.sort(key=lambda x: x.created_at, reverse=True)
    
    return filtered_messages[skip:skip + limit]


@router.get("/paginated", response_model=SystemMessageList)
async def get_system_messages_paginated(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    type: Optional[str] = Query(None, description="消息类型"),
    priority: Optional[str] = Query(None, description="优先级"),
    platform: Optional[str] = Query(None, description="平台"),
    days: Optional[int] = Query(None, ge=1, le=365, description="最近N天的消息")
):
    """获取系统消息列表（分页版本）"""
    skip = (page - 1) * size
    
    # 获取消息列表
    messages = await get_system_messages(
        db=db,
        skip=skip,
        limit=size,
        type=type,
        priority=priority,
        platform=Platform(platform) if platform else None
    )
    
    # 获取总数
    total = await get_system_messages_count(
        db=db,
        type=type,
        priority=priority,
        platform=Platform(platform) if platform else None
    )
    
    # 计算总页数
    pages = (total + size - 1) // size
    
    return SystemMessageList(
        items=messages,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/latest", response_model=List[SystemMessage])
async def get_latest_messages(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50, description="数量限制"),
    platform: Optional[Platform] = Query(None, description="平台")
):
    """获取最新系统消息"""
    return await get_latest_system_messages(
        db=db,
        platform=platform,
        limit=limit
    )


@router.get("/platform/{platform}", response_model=List[SystemMessage])
async def get_messages_by_platform(
    platform: Platform,
    *,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量")
):
    """根据平台获取系统消息"""
    skip = (page - 1) * size
    
    return await get_system_messages_by_platform(
        db=db,
        platform=platform,
        skip=skip,
        limit=size
    )


@router.get("/{message_id}", response_model=SystemMessage)
async def get_system_message_detail(
    message_id: int,
    *,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_user)
):
    """根据ID获取系统消息详情"""
    message = await get_system_message(db=db, message_id=message_id)
    if not message:
        raise HTTPException(status_code=404, detail="系统消息不存在")
    return message


@router.post("/", response_model=SystemMessage)
async def create_system_message_item(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_user),
    message_in: SystemMessageCreate
):
    """创建系统消息（需要管理员权限）"""
    # 检查用户是否为管理员
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以创建系统消息")
    
    message = await create_system_message(db=db, message_in=message_in)
    return message


@router.put("/{message_id}", response_model=SystemMessage)
async def update_system_message_item(
    message_id: int,
    *,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_user),
    message_in: SystemMessageUpdate
):
    """更新系统消息（需要管理员权限）"""
    # 检查用户是否为管理员
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以更新系统消息")
    
    message = await get_system_message(db=db, message_id=message_id)
    if not message:
        raise HTTPException(status_code=404, detail="系统消息不存在")
    
    message = await update_system_message(db=db, message_id=message_id, message_in=message_in)
    return message


@router.delete("/{message_id}")
async def delete_system_message_item(
    message_id: int,
    *,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_user)
):
    """删除系统消息（需要管理员权限）"""
    # 检查用户是否为管理员
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以删除系统消息")
    
    message = await get_system_message(db=db, message_id=message_id)
    if not message:
        raise HTTPException(status_code=404, detail="系统消息不存在")
    
    await delete_system_message(db=db, message_id=message_id)
    return {"message": "系统消息已删除"}


@router.get("/stats/summary")
async def get_message_stats(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_user)
):
    """获取系统消息统计信息（需要管理员权限）"""
    # 检查用户是否为管理员
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以查看统计信息")
    
    from sqlalchemy import select, func
    from app.db.models.system_message import SystemMessage
    from datetime import timedelta
    from app.utils.time_utils import get_local_time
    
    # 总消息数
    total_result = await db.execute(select(func.count(SystemMessage.id)))
    total_messages = total_result.scalar()
    
    # 按类型统计
    type_stats_result = await db.execute(
        select(
            SystemMessage.type,
            func.count(SystemMessage.id).label('count')
        )
        .group_by(SystemMessage.type)
    )
    type_stats = {row[0]: row[1] for row in type_stats_result.fetchall()}
    
    # 按优先级统计
    priority_stats_result = await db.execute(
        select(
            SystemMessage.priority,
            func.count(SystemMessage.id).label('count')
        )
        .group_by(SystemMessage.priority)
    )
    priority_stats = {row[0]: row[1] for row in priority_stats_result.fetchall()}
    
    # 最近24小时消息数
    yesterday = get_local_time() - timedelta(days=1)
    recent_result = await db.execute(
        select(func.count(SystemMessage.id))
        .filter(SystemMessage.created_at >= yesterday)
    )
    recent_messages = recent_result.scalar()
    
    # 最近7天消息数
    week_ago = get_local_time() - timedelta(days=7)
    week_result = await db.execute(
        select(func.count(SystemMessage.id))
        .filter(SystemMessage.created_at >= week_ago)
    )
    week_messages = week_result.scalar()
    
    # 最早和最晚消息时间
    time_range_result = await db.execute(
        select(
            func.min(SystemMessage.created_at).label('earliest'),
            func.max(SystemMessage.created_at).label('latest')
        )
    )
    time_range = time_range_result.fetchone()
    
    return {
        "total_messages": total_messages,
        "recent_24h_messages": recent_messages,
        "recent_7d_messages": week_messages,
        "type_stats": type_stats,
        "priority_stats": priority_stats,
        "earliest_message": time_range[0].isoformat() if time_range[0] else None,
        "latest_message": time_range[1].isoformat() if time_range[1] else None,
    }
