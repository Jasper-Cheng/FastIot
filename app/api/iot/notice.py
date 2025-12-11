from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select, func

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.system_message import (
    get_system_messages,
    get_system_messages_count,
    get_system_message,
    create_system_message,
    update_system_message,
    delete_system_message
)
from app.models.system_message import SystemMessageCreate, SystemMessageUpdate

router = APIRouter()


@router.get("/notice/list")
async def get_notice_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    title: Optional[str] = Query(None, description="标题搜索"),
    type: Optional[str] = Query(None, description="消息类型筛选"),
    priority: Optional[str] = Query(None, description="优先级筛选"),
    platform: Optional[str] = Query(None, description="平台筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取系统消息列表"""
    skip = (page - 1) * pageSize
    
    messages = await get_system_messages(
        db=db,
        skip=skip,
        limit=pageSize,
        type=type,
        priority=priority,
        platform=platform
    )
    
    # 如果提供了 title 搜索，需要额外过滤
    if title:
        messages = [msg for msg in messages if title.lower() in (msg.title or "").lower()]
    
    total = await get_system_messages_count(
        db=db,
        type=type,
        priority=priority,
        platform=platform
    )
    
    # 如果提供了 title 搜索，需要重新计算总数
    if title:
        total = len(messages)
    
    items = []
    for message in messages:
        items.append({
            "id": message.id,
            "title": message.title,
            "content": message.content,
            "type": message.type,
            "priority": message.priority,
            "platforms": message.platforms or [],
            "extra": message.extra or {},
            "createdAt": message.created_at.strftime("%Y-%m-%d %H:%M:%S") if message.created_at else None,
            "updatedAt": message.updated_at.strftime("%Y-%m-%d %H:%M:%S") if message.updated_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.post("/notice")
async def create_notice(
    notice_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """创建系统消息"""
    # 验证必填字段
    if not notice_data.get("title"):
        raise HTTPException(status_code=400, detail="标题不能为空")
    if not notice_data.get("content"):
        raise HTTPException(status_code=400, detail="内容不能为空")
    if not notice_data.get("type"):
        raise HTTPException(status_code=400, detail="消息类型不能为空")
    if not notice_data.get("platforms"):
        raise HTTPException(status_code=400, detail="平台不能为空")
    
    message_create = SystemMessageCreate(
        title=notice_data["title"],
        content=notice_data["content"],
        type=notice_data["type"],
        priority=notice_data.get("priority", "normal"),
        platforms=notice_data["platforms"],
        extra=notice_data.get("extra", {})
    )
    
    message = await create_system_message(db, message_create)
    
    return {
        "id": message.id,
        "title": message.title,
        "content": message.content,
        "type": message.type,
        "priority": message.priority,
        "platforms": message.platforms or [],
        "extra": message.extra or {},
        "createdAt": message.created_at.strftime("%Y-%m-%d %H:%M:%S") if message.created_at else None,
        "updatedAt": message.updated_at.strftime("%Y-%m-%d %H:%M:%S") if message.updated_at else None
    }


@router.put("/notice/{id}")
async def update_notice(
    id: int,
    notice_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """更新系统消息"""
    # 验证消息是否存在
    message = await get_system_message(db, id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    
    message_update = SystemMessageUpdate()
    if "title" in notice_data:
        message_update.title = notice_data["title"]
    if "content" in notice_data:
        message_update.content = notice_data["content"]
    if "type" in notice_data:
        message_update.type = notice_data["type"]
    if "priority" in notice_data:
        message_update.priority = notice_data["priority"]
    if "platforms" in notice_data:
        message_update.platforms = notice_data["platforms"]
    if "extra" in notice_data:
        message_update.extra = notice_data["extra"]
    
    updated_message = await update_system_message(db, id, message_update)
    if not updated_message:
        raise HTTPException(status_code=500, detail="更新失败")
    
    return {
        "id": updated_message.id,
        "title": updated_message.title,
        "content": updated_message.content,
        "type": updated_message.type,
        "priority": updated_message.priority,
        "platforms": updated_message.platforms or [],
        "extra": updated_message.extra or {},
        "updatedAt": updated_message.updated_at.strftime("%Y-%m-%d %H:%M:%S") if updated_message.updated_at else None
    }


@router.delete("/notice/{id}")
async def delete_notice(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """删除系统消息"""
    # 验证消息是否存在
    message = await get_system_message(db, id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    
    deleted_message = await delete_system_message(db, id)
    if not deleted_message:
        raise HTTPException(status_code=500, detail="删除失败")
    
    return {}


@router.post("/notice/{id}/publish")
async def publish_notice(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """发布系统消息"""
    # 验证消息是否存在
    message = await get_system_message(db, id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    
    # 这里可以添加发布逻辑，比如更新状态、推送给用户等
    # 目前只是返回成功
    return {}

