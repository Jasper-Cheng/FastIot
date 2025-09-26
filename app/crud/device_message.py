from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List, Optional
from datetime import datetime
from app.db.models.device_message import DeviceMessage
from app.models.device_message import DeviceMessageCreate, DeviceMessageUpdate, DeviceMessageStatus

async def create_device_message(db: AsyncSession, message: DeviceMessageCreate) -> DeviceMessage:
    """创建新的设备消息记录"""
    db_message = DeviceMessage(
        device_id=message.device_id,
        level=message.level,
        message=message.message,
        detail=message.detail,
        status=DeviceMessageStatus.new
    )
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    return db_message

async def get_device_message(db: AsyncSession, message_id: int) -> Optional[DeviceMessage]:
    """根据ID获取设备消息记录"""
    result = await db.execute(select(DeviceMessage).where(DeviceMessage.id == message_id))
    return result.scalar_one_or_none()

async def get_device_messages_by_device(db: AsyncSession, device_id: int, limit: int = 100) -> List[DeviceMessage]:
    """获取指定设备的所有消息记录"""
    result = await db.execute(
        select(DeviceMessage)
        .where(DeviceMessage.device_id == device_id)
        .order_by(
            func.coalesce(DeviceMessage.updated_at, DeviceMessage.created_at).desc()
        )
        .limit(limit)
    )
    return result.scalars().all()

async def get_user_device_messages(db: AsyncSession, user_id: int, limit: int = 100) -> List[DeviceMessage]:
    """获取指定用户所有设备的消息记录"""
    # 这里需要关联查询用户拥有的设备
    from app.db.models.device import Device
    result = await db.execute(
        select(DeviceMessage)
        .join(Device, DeviceMessage.device_id == Device.id)
        .where(Device.user_id == user_id)
        .order_by(
            func.coalesce(DeviceMessage.updated_at, DeviceMessage.created_at).desc()
        )
        .limit(limit)
    )
    return result.scalars().all()

async def get_all_device_messages(db: AsyncSession, limit: int = 100) -> List[DeviceMessage]:
    """获取所有设备消息记录（Admin专用）"""
    result = await db.execute(
        select(DeviceMessage)
        .order_by(
            func.coalesce(DeviceMessage.updated_at, DeviceMessage.created_at).desc()
        )
        .limit(limit)
    )
    return result.scalars().all()

async def update_device_message_status(db: AsyncSession, message_id: int, status: DeviceMessageStatus) -> Optional[DeviceMessage]:
    """更新设备消息状态"""
    await db.execute(
        update(DeviceMessage)
        .where(DeviceMessage.id == message_id)
        .values(status=status, updated_at=datetime.utcnow())
    )
    await db.commit()
    
    # 返回更新后的消息记录
    return await get_device_message(db, message_id)

async def update_device_message_content(db: AsyncSession, message_id: int, level: Optional[str] = None, message: Optional[str] = None) -> Optional[DeviceMessage]:
    """更新设备消息内容（level和message）"""
    update_data = {}
    if level is not None:
        update_data["level"] = level
    if message is not None:
        update_data["message"] = message
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.execute(
            update(DeviceMessage)
            .where(DeviceMessage.id == message_id)
            .values(**update_data)
        )
        await db.commit()
    
    # 返回更新后的消息记录
    return await get_device_message(db, message_id)

async def update_device_message_full(db: AsyncSession, message_id: int, message_update: DeviceMessageUpdate) -> Optional[DeviceMessage]:
    """完整更新设备消息信息"""
    update_data = {}
    
    # 收集需要更新的字段
    if message_update.level is not None:
        update_data["level"] = message_update.level
    if message_update.message is not None:
        update_data["message"] = message_update.message
    if message_update.status is not None:
        update_data["status"] = message_update.status
    if message_update.detail is not None:
        update_data["detail"] = message_update.detail
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.execute(
            update(DeviceMessage)
            .where(DeviceMessage.id == message_id)
            .values(**update_data)
        )
        await db.commit()
    
    # 返回更新后的消息记录
    return await get_device_message(db, message_id)

async def get_unread_device_messages_count(db: AsyncSession, user_id: int) -> int:
    """获取用户未读设备消息数量"""
    from app.db.models.device import Device
    result = await db.execute(
        select(DeviceMessage)
        .join(Device, DeviceMessage.device_id == Device.id)
        .where(Device.user_id == user_id, DeviceMessage.status == DeviceMessageStatus.new)
    )
    return len(result.scalars().all())

async def mark_device_messages_as_read(db: AsyncSession, message_ids: List[int]) -> bool:
    """批量标记设备消息为已读"""
    await db.execute(
        update(DeviceMessage)
        .where(DeviceMessage.id.in_(message_ids))
        .values(status=DeviceMessageStatus.read, updated_at=datetime.utcnow())
    )
    await db.commit()
    return True
