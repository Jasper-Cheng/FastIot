from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models.device_log import DeviceLog
from app.models.device_log import DeviceLogCreate, DeviceLogUpdate
from typing import Optional, List

async def get_device_log(db: AsyncSession, log_id: int) -> Optional[DeviceLog]:
    """根据ID获取设备日志"""
    result = await db.execute(select(DeviceLog).filter(DeviceLog.id == log_id))
    return result.scalar_one_or_none()

async def get_device_logs_by_device(db: AsyncSession, device_id: int, skip: int = 0, limit: int = 100) -> List[DeviceLog]:
    """根据设备ID获取设备日志列表"""
    result = await db.execute(
        select(DeviceLog)
        .filter(DeviceLog.device_id == device_id)
        .order_by(desc(DeviceLog.created_at))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_device_logs_by_type(db: AsyncSession, device_id: int, type: str, skip: int = 0, limit: int = 100) -> List[DeviceLog]:
    """根据设备ID和类型获取日志"""
    result = await db.execute(
        select(DeviceLog)
        .filter(DeviceLog.device_id == device_id, DeviceLog.type == type)
        .order_by(desc(DeviceLog.created_at))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_device_log(db: AsyncSession, log: DeviceLogCreate) -> DeviceLog:
    """创建设备日志"""
    db_log = DeviceLog(
        device_id=log.device_id,
        type=log.type,
        params=log.params
    )
    db.add(db_log)
    await db.commit()
    await db.refresh(db_log)
    return db_log

async def update_device_log(db: AsyncSession, log_id: int, log: DeviceLogUpdate) -> Optional[DeviceLog]:
    """更新设备日志"""
    db_log = await get_device_log(db, log_id)
    if not db_log:
        return None
    
    update_data = log.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_log, field, value)
    
    await db.commit()
    await db.refresh(db_log)
    return db_log

async def delete_device_log(db: AsyncSession, log_id: int) -> bool:
    """删除设备日志"""
    db_log = await get_device_log(db, log_id)
    if not db_log:
        return False
    
    await db.delete(db_log)
    await db.commit()
    return True
