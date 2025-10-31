from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from app.utils.time_utils import get_local_time

from app.db.session import get_db
from app.crud.device_message import (
    get_user_device_messages,
    update_device_message_status,
)
from app.models.device_message import (
    DeviceMessageInDB,
    DeviceMessageStatus,
)
from app.db.models.device_message import DeviceMessage
from app.db.models.device import Device
from app.api.dependencies import get_current_token
router = APIRouter()


@router.get("/", response_model=List[DeviceMessageInDB])
async def list_device_messages(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    level: Optional[List[str]] = Query(None, description="按消息级别筛选，可传入多个值 (low, normal, error, fatal)"),
    status: Optional[str] = Query(None, description="按消息状态极筛选 (new, read)"),
    token_info: dict = Depends(get_current_token)
):
    """获取当前用户的设备消息列表
    
    支持按级别、状态筛选
    """
    # 验证 level 参数
    if level is not None:
        valid_levels = ["low", "normal", "error", "fatal"]
        invalid_levels = [l for l in level if l not in valid_levels]
        if invalid_levels:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的消息级别: {', '.join(invalid_levels)}。有效值: {', '.join(valid_levels)}"
            )
    
    # 验证 status 参数
    if status is not None:
        valid_statuses = ["new", "read"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的消息状态 '{status}'。有效值: {', '.join(valid_statuses)}"
            )
    
    # 使用当前用户的ID
    user_id = token_info["id"]
    
    # 获取当前用户的所有极设备消息
    alerts = await get_user_device_messages(db, user_id, limit)
    
    # 应用过滤条件
    filtered_alerts = []
    for alert in alerts:
        # 级别过滤
        if level and alert.level not in level:
            continue
        # 状态过滤
        if status and alert.status != status:
            continue
        
        filtered_alerts.append(alert)
    
    # 按 updated_at 排序，如果 updated_at 为 None 则按 created_at 排序
    filtered_alerts.sort(key=lambda x: x.updated_at or x.created_at, reverse=True)
    
    return filtered_alerts[skip:skip + limit]


@router.patch("/{message_id}/make-read", response_model=DeviceMessageInDB)
async def make_device_message_read(
    message_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """标记设备消息为已读状态"""
    updated = await update_device_message_status(db, message_id, DeviceMessageStatus.read)
    if not updated:
        raise HTTPException(status_code=404, detail="设备消息不存在")
    return updated


@router.patch("/mark-all-read")
async def mark_all_device_messages_read(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """标记当前用户所有设备消息为已读"""
    from sqlalchemy import update
    from app.db.models.device_message import DeviceMessage
    from app.models.device_message import DeviceMessageStatus
    from app.db.models.device import Device
    
    # 使用当前用户的ID
    user_id = token_info["id"]
    
    # 更新用户所有设备的消息状态为已读
    await db.execute(
        update(DeviceMessage)
        .where(
            DeviceMessage.device_id.in_(
                select(Device.id).where(Device.user_id == user_id)
            )
        )
        .where(DeviceMessage.status == DeviceMessageStatus.new)
        .values(status=DeviceMessageStatus.read, updated_at=get_local_time())
    )
    await db.commit()
    
    return {"message": f"用户 {user_id} 的所有设备消息已标记为已读"}
