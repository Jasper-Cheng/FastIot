from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db
from app.crud.device_message import (
    create_device_message,
    get_device_message,
    get_device_messages_by_device,
    get_user_device_messages,
    get_all_device_messages,
    update_device_message_status,
    update_device_message_content,
    update_device_message_full,
    get_unread_device_messages_count,
    mark_device_messages_as_read,
)
from app.crud.device import get_device
from app.models.device_message import (
    DeviceMessageCreate,
    DeviceMessageUpdate,
    DeviceMessageInDB,
    DeviceMessageLevel,
    DeviceMessageStatus,
)
router = APIRouter()


@router.get("/", response_model=List[DeviceMessageInDB])
async def list_device_messages(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    device_id: Optional[int] = Query(None, description="按设备ID筛选"),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    level: Optional[str] = Query(None, description="按消息级别筛选 (normal, error, fatal)"),
    status: Optional[str] = Query(None, description="按消息状态筛选 (new, read)"),
    days: Optional[int] = Query(None, ge=1, le=365, description="最近N天的消息"),
):
    """获取设备消息列表
    
    支持按设备ID、用户ID、级别、状态、时间范围筛选
    """
    # 验证 level 参数
    if level is not None:
        valid_levels = ["normal", "error", "fatal"]
        if level not in valid_levels:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的消息级别 '{level}'。有效值: {', '.join(valid_levels)}"
            )
    
    # 验证 status 参数
    if status is not None:
        valid_statuses = ["new", "read"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的消息状态 '{status}'。有效值: {', '.join(valid_statuses)}"
            )
    
    if device_id:
        alerts = await get_device_messages_by_device(db, device_id, limit)
    elif user_id:
        alerts = await get_user_device_messages(db, user_id, limit)
    else:
        alerts = await get_all_device_messages(db, limit)
    
    # 应用过滤条件
    filtered_alerts = []
    for alert in alerts:
        # 级别过滤
        if level and alert.level != level:
            continue
        # 状态过滤
        if status and alert.status != status:
            continue
        # 时间过滤
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            if alert.created_at < cutoff_date:
                continue
        
        filtered_alerts.append(alert)
    
    return filtered_alerts[skip:skip + limit]


@router.get("/{message_id}", response_model=DeviceMessageInDB)
async def get_device_message_detail(message_id: int, db: AsyncSession = Depends(get_db)):
    """获取设备消息详情"""
    message = await get_device_message(db, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="设备消息不存在")
    return message


@router.post("/", response_model=DeviceMessageInDB)
async def create_device_message_item(payload: DeviceMessageCreate, db: AsyncSession = Depends(get_db)):
    """创建设备消息
    
    示例请求体：
    {
      "device_id": 1,
      "level": "high",
      "message": "设备温度过高，请检查散热系统"
    }
    """
    # 验证设备存在
    device = await get_device(db, payload.device_id)
    if not device:
        raise HTTPException(status_code=400, detail="设备不存在")
    
    return await create_device_message(db, payload)


@router.put("/{message_id}", response_model=DeviceMessageInDB)
async def update_device_message_item(message_id: int, payload: DeviceMessageUpdate, db: AsyncSession = Depends(get_db)):
    """更新设备消息
    
    示例请求体：
    {
      "level": "medium",
      "message": "设备温度已恢复正常",
      "status": "read"
    }
    """
    # 验证消息存在
    existing_message = await get_device_message(db, message_id)
    if not existing_message:
        raise HTTPException(status_code=404, detail="设备消息不存在")
    
    updated = await update_device_message_full(db, message_id, payload)
    return updated


@router.patch("/{message_id}/status", response_model=DeviceMessageInDB)
async def update_device_message_status_item(
    message_id: int, 
    status: DeviceMessageStatus, 
    db: AsyncSession = Depends(get_db)
):
    """更新设备消息状态"""
    updated = await update_device_message_status(db, message_id, status)
    if not updated:
        raise HTTPException(status_code=404, detail="设备消息不存在")
    return updated


@router.delete("/{message_id}")
async def delete_device_message_item(message_id: int, db: AsyncSession = Depends(get_db)):
    """删除设备消息"""
    message = await get_device_message(db, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="设备消息不存在")
    
    await db.delete(message)
    await db.commit()
    return {"message": "删除成功"}


@router.patch("/user/{user_id}/mark-read")
async def mark_user_all_device_messages_read(user_id: int, db: AsyncSession = Depends(get_db)):
    """标记用户所有设备消息为已读"""
    from sqlalchemy import update
    from app.db.models.device_message import DeviceMessage
    from app.models.device_message import DeviceMessageStatus
    from app.db.models.device import Device
    
    # 更新用户所有设备的消息状态为已读
    await db.execute(
        update(DeviceMessage)
        .where(
            DeviceMessage.device_id.in_(
                select(Device.id).where(Device.user_id == user_id)
            )
        )
        .where(DeviceMessage.status == DeviceMessageStatus.new)
        .values(status=DeviceMessageStatus.read)
    )
    await db.commit()
    
    return {"message": f"用户 {user_id} 的所有设备消息已标记为已读"}


@router.get("/device/{device_id}/stats", response_model=dict)
async def get_device_message_stats(device_id: int, db: AsyncSession = Depends(get_db)):
    """获取设备消息统计信息"""
    # 验证设备存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    from sqlalchemy import select, func
    from app.db.models.device_message import DeviceMessage
    
    # 总消息数
    total_result = await db.execute(
        select(func.count(DeviceMessage.id)).filter(DeviceMessage.device_id == device_id)
    )
    total_messages = total_result.scalar()
    
    # 按级别统计
    level_stats_result = await db.execute(
        select(
            DeviceMessage.level,
            func.count(DeviceMessage.id).label('count')
        )
        .filter(DeviceMessage.device_id == device_id)
        .group_by(DeviceMessage.level)
    )
    level_stats = {row[0]: row[1] for row in level_stats_result.fetchall()}
    
    # 按状态统计
    status_stats_result = await db.execute(
        select(
            DeviceMessage.status,
            func.count(DeviceMessage.id).label('count')
        )
        .filter(DeviceMessage.device_id == device_id)
        .group_by(DeviceMessage.status)
    )
    status_stats = {row[0]: row[1] for row in status_stats_result.fetchall()}
    
    # 最近24小时消息数
    yesterday = datetime.now() - timedelta(days=1)
    recent_result = await db.execute(
        select(func.count(DeviceMessage.id))
        .filter(DeviceMessage.device_id == device_id)
        .filter(DeviceMessage.created_at >= yesterday)
    )
    recent_messages = recent_result.scalar()
    
    # 最早和最晚消息时间
    time_range_result = await db.execute(
        select(
            func.min(DeviceMessage.created_at).label('earliest'),
            func.max(DeviceMessage.created_at).label('latest')
        )
        .filter(DeviceMessage.device_id == device_id)
    )
    time_range = time_range_result.fetchone()
    
    return {
        "device_id": device_id,
        "total_messages": total_messages,
        "recent_24h_messages": recent_messages,
        "level_stats": level_stats,
        "status_stats": status_stats,
        "earliest_message": time_range[0].isoformat() if time_range[0] else None,
        "latest_message": time_range[1].isoformat() if time_range[1] else None,
    }


@router.get("/user/{user_id}/stats", response_model=dict)
async def get_user_device_message_stats(user_id: int, db: AsyncSession = Depends(get_db)):
    """获取用户设备消息统计信息"""
    from sqlalchemy import select, func
    from app.db.models.device_message import DeviceMessage
    from app.db.models.device import Device
    
    # 总消息数
    total_result = await db.execute(
        select(func.count(DeviceMessage.id))
        .join(Device, DeviceMessage.device_id == Device.id)
        .where(Device.user_id == user_id)
    )
    total_messages = total_result.scalar()
    
    # 未读消息数
    unread_count = await get_unread_device_messages_count(db, user_id)
    
    # 按级别统计
    level_stats_result = await db.execute(
        select(
            DeviceMessage.level,
            func.count(DeviceMessage.id).label('count')
        )
        .join(Device, DeviceMessage.device_id == Device.id)
        .where(Device.user_id == user_id)
        .group_by(DeviceMessage.level)
    )
    level_stats = {row[0]: row[1] for row in level_stats_result.fetchall()}
    
    # 按状态统计
    status_stats_result = await db.execute(
        select(
            DeviceMessage.status,
            func.count(DeviceMessage.id).label('count')
        )
        .join(Device, DeviceMessage.device_id == Device.id)
        .where(Device.user_id == user_id)
        .group_by(DeviceMessage.status)
    )
    status_stats = {row[0]: row[1] for row in status_stats_result.fetchall()}
    
    return {
        "user_id": user_id,
        "total_messages": total_messages,
        "unread_messages": unread_count,
        "level_stats": level_stats,
        "status_stats": status_stats,
    }
