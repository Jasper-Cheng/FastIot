from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.crud.device_message import (
    get_account_device_messages,
    get_device_message,
    update_device_message_status,
    mark_all_account_device_messages_read
)
from app.models.device_message import DeviceMessageInDB
from app.api.dependencies import get_current_token
from app.db.session import get_db

router = APIRouter()


@router.get("/", response_model=List[DeviceMessageInDB])
async def list_device_messages(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    level: Optional[str] = Query(None, description="消息级别 (normal/warning/error/info)"),
    status: Optional[str] = Query(None, description="消息状态 (new/read)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取设备消息列表
    
    - 支持按级别和状态筛选
    - 支持分页
    - 按时间倒序排列
    """
    account_id = token_info["account_id"]
    
    skip = (page - 1) * page_size
    limit = page_size
    
    messages = await get_account_device_messages(
        db,
        account_id=account_id,
        level=[level] if level else None,
        status=status,
        skip=skip,
        limit=limit
    )
    
    return messages


@router.patch("/{id}/make-read")
async def mark_message_as_read(
    id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """标记消息为已读"""
    account_id = token_info["account_id"]
    
    # 获取消息
    message = await get_device_message(db, id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    
    # 检查权限：消息对应的设备必须属于当前用户或用户所在的家庭
    from app.crud.device import get_device
    device = await get_device(db, message.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备是否属于当前用户或用户所在的家庭
    if device.account_id != account_id:
        from app.crud.family_device import get_device_families
        from app.crud.family_member import get_family_member_by_family_and_account
        
        device_families = await get_device_families(db, device.id)
        has_permission = False
        
        for family in device_families:
            member = await get_family_member_by_family_and_account(db, family.id, account_id)
            if member:
                has_permission = True
                break
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="无权访问此消息")
    
    # 标记为已读
    from app.models.device_message import DeviceMessageStatus
    await update_device_message_status(db, id, DeviceMessageStatus.read)
    
    return {}


@router.patch("/mark-all-read")
async def mark_all_messages_as_read(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """标记所有消息为已读"""
    account_id = token_info["account_id"]
    
    count = await mark_all_account_device_messages_read(db, account_id)
    
    return {"count": count}


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """获取未读消息数量（包含设备消息和系统消息）"""
    account_id = token_info["account_id"]
    
    # 获取设备消息未读数量
    device_messages = await get_account_device_messages(
        db,
        account_id=account_id,
        status="new",
        skip=0,
        limit=1000
    )
    device_count = len(device_messages)
    
    # 获取系统消息未读数量
    from app.crud.system_message import get_system_messages
    system_messages = await get_system_messages(db, skip=0, limit=1000)
    system_count = len(system_messages)
    
    return {
        "device_messages": device_count,
        "system_messages": system_count
    }

