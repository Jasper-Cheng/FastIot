from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, or_, and_
from typing import List, Optional, Tuple
from datetime import datetime
from app.db.models.device_message import DeviceMessage
from app.models.device_message import DeviceMessageCreate, DeviceMessageStatus
from app.utils.time_utils import get_local_time

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

async def get_account_device_messages(
    db: AsyncSession, 
    account_id: int, 
    skip: int = 0,
    limit: int = 100,
    level: Optional[List[str]] = None,
    status: Optional[str] = None,
    family_id: Optional[int] = None
) -> List[DeviceMessage]:
    """获取指定账号设备的消息记录，支持按级别和状态筛选
    
    Args:
        db: 数据库会话
        account_id: 账号ID
        skip: 跳过数量
        limit: 限制数量
        level: 消息级别筛选
        status: 消息状态筛选
        family_id: 家庭ID，如果提供则只返回该家庭中所有设备的消息；如果不提供则返回个人所有设备的消息
    """
    from app.db.models.device import Device
    from app.db.models.family_device import FamilyDevice
    
    if family_id:
        # 如果有 family_id，查询该家庭中所有设备的消息
        # 获取该家庭的所有设备ID
        device_ids_result = await db.execute(
            select(FamilyDevice.device_id).filter(FamilyDevice.family_id == family_id)
        )
        family_device_ids = [row[0] for row in device_ids_result.all()]
        
        if not family_device_ids:
            # 如果家庭没有设备，返回空列表
            return []
        
        query = (
            select(DeviceMessage)
            .join(Device, DeviceMessage.device_id == Device.id)
            .where(Device.id.in_(family_device_ids))
        )
    else:
        # 如果没有 family_id，只查询个人设备的消息
        query = (
            select(DeviceMessage)
            .join(Device, DeviceMessage.device_id == Device.id)
            .where(Device.account_id == account_id)
        )
    
    # 添加级别过滤
    if level:
        query = query.where(DeviceMessage.level.in_(level))
    
    # 添加状态过滤
    if status:
        query = query.where(DeviceMessage.status == status)
    
    # 排序和分页
    query = query.order_by(
        func.coalesce(DeviceMessage.updated_at, DeviceMessage.created_at).desc()
    ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

async def update_device_message_status(db: AsyncSession, message_id: int, status: DeviceMessageStatus) -> Optional[DeviceMessage]:
    """更新设备消息状态"""
    await db.execute(
        update(DeviceMessage)
        .where(DeviceMessage.id == message_id)
        .values(status=status, updated_at=get_local_time())
    )
    await db.commit()
    
    # 返回更新后的消息记录
    return await get_device_message(db, message_id)

async def mark_all_account_device_messages_read(
    db: AsyncSession, 
    account_id: int, 
    family_id: Optional[int] = None
) -> int:
    """标记设备消息为已读
    
    Args:
        db: 数据库会话
        account_id: 账号ID
        family_id: 家庭ID，如果提供则标记该家庭中所有设备的消息为已读；如果不提供则标记个人所有设备的消息为已读
    
    Returns:
        更新的记录数
    """
    from app.db.models.device import Device
    from app.db.models.family_device import FamilyDevice
    
    if family_id:
        # 如果有 family_id，标记该家庭中所有设备的消息为已读
        # 获取该家庭的所有设备ID
        device_ids_result = await db.execute(
            select(FamilyDevice.device_id).filter(FamilyDevice.family_id == family_id)
        )
        family_device_ids = [row[0] for row in device_ids_result.all()]
        
        if not family_device_ids:
            # 如果家庭没有设备，返回0
            return 0
        
        device_ids_query = select(Device.id).where(Device.id.in_(family_device_ids))
    else:
        # 如果没有 family_id，只标记个人设备的消息为已读
        device_ids_query = select(Device.id).where(Device.account_id == account_id)
    
    result = await db.execute(
        update(DeviceMessage)
        .where(DeviceMessage.device_id.in_(device_ids_query))
        .where(DeviceMessage.status == DeviceMessageStatus.new)
        .values(status=DeviceMessageStatus.read, updated_at=get_local_time())
    )
    await db.commit()
    
    # 返回更新的记录数
    return result.rowcount

async def get_device_messages_with_pagination(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    device_id: Optional[int] = None,
    level: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Tuple[List[DeviceMessage], int]:
    """获取设备消息列表（支持分页和搜索）"""
    query = select(DeviceMessage)
    count_query = select(func.count(DeviceMessage.id))
    
    # 构建搜索条件（使用 AND 组合，因为这些都是筛选条件）
    conditions = []
    if device_id:
        conditions.append(DeviceMessage.device_id == device_id)
    if level:
        conditions.append(DeviceMessage.level == level)
    if status:
        conditions.append(DeviceMessage.status == status)
    if start_date:
        conditions.append(DeviceMessage.created_at >= start_date)
    if end_date:
        conditions.append(DeviceMessage.created_at <= end_date)
    # type 参数暂时不使用，因为数据库中没有 type 字段
    
    if conditions:
        query = query.filter(and_(*conditions))
        count_query = count_query.filter(and_(*conditions))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 获取分页数据，按创建时间倒序
    result = await db.execute(
        query.order_by(DeviceMessage.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    messages = result.scalars().all()
    
    return messages, total

