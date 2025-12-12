from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.device_message import get_device_messages_with_pagination
from app.db.models.device_message import DeviceMessage
from app.db.models.device import Device

router = APIRouter()


@router.get("/device-message/list")
async def get_device_message_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    deviceId: Optional[int] = Query(None, description="设备ID筛选"),
    level: Optional[str] = Query(None, description="消息级别筛选"),
    type: Optional[str] = Query(None, description="消息类型筛选"),
    status: Optional[str] = Query(None, description="消息状态筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取设备消息列表"""
    skip = (page - 1) * pageSize
    
    messages, total = await get_device_messages_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        device_id=deviceId,
        level=level,
        type=type,
        status=status
    )
    
    items = []
    for message in messages:
        # 获取设备信息
        device_result = await db.execute(
            select(Device).filter(Device.id == message.device_id)
        )
        device = device_result.scalar_one_or_none()
        
        items.append({
            "id": message.id,
            "deviceId": message.device_id,
            "deviceSn": device.sn if device else None,
            "deviceName": device.name if device else None,
            "level": message.level,
            "status": message.status,
            "message": message.message,
            "detail": message.detail or {},
            "createdAt": message.created_at.strftime("%Y-%m-%d %H:%M:%S") if message.created_at else None,
            "updatedAt": message.updated_at.strftime("%Y-%m-%d %H:%M:%S") if message.updated_at else None
        })
    
    return {
        "items": items,
        "total": total
    }

