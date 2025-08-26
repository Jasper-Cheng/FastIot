from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.device_data import DeviceData
from app.models.device_data import DeviceDataCreate
from typing import Optional, List
from datetime import datetime

async def get_device_data(db: AsyncSession, data_id: int) -> Optional[DeviceData]:
    """根据ID获取设备数据"""
    result = await db.execute(select(DeviceData).filter(DeviceData.id == data_id))
    return result.scalar_one_or_none()

async def get_device_data_list(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DeviceData]:
    """获取设备数据列表"""
    result = await db.execute(select(DeviceData).offset(skip).limit(limit))
    return result.scalars().all()

async def get_device_data_by_device(db: AsyncSession, device_id: int, skip: int = 0, limit: int = 100) -> List[DeviceData]:
    """根据设备ID获取设备数据"""
    result = await db.execute(select(DeviceData).filter(DeviceData.device_id == device_id).offset(skip).limit(limit))
    return result.scalars().all()

async def create_device_data(db: AsyncSession, device_data: DeviceDataCreate) -> DeviceData:
    """创建新的设备数据记录"""
    db_device_data = DeviceData(**device_data.dict())
    db.add(db_device_data)
    await db.commit()
    await db.refresh(db_device_data)
    return db_device_data

async def get_latest_device_data(db: AsyncSession, device_id: int) -> Optional[DeviceData]:
    """获取设备的最新数据"""
    result = await db.execute(select(DeviceData).filter(DeviceData.device_id == device_id).order_by(DeviceData.timestamp.desc()))
    return result.scalar_one_or_none()

async def get_device_data_by_time_range(db: AsyncSession, device_id: int, start_time: datetime, end_time: datetime) -> List[DeviceData]:
    """根据时间范围获取设备数据"""
    result = await db.execute(select(DeviceData).filter(
        DeviceData.device_id == device_id,
        DeviceData.timestamp >= start_time,
        DeviceData.timestamp <= end_time
    ).order_by(DeviceData.timestamp.asc()))
    return result.scalars().all()

async def delete_device_data(db: AsyncSession, data_id: int) -> bool:
    """删除设备数据"""
    db_device_data = await get_device_data(db, data_id)
    if not db_device_data:
        return False
    
    await db.delete(db_device_data)
    await db.commit()
    return True

async def delete_old_device_data(db: AsyncSession, device_id: int, days: int = 30) -> int:
    """删除指定天数之前的旧数据"""
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(select(DeviceData).filter(
        DeviceData.device_id == device_id,
        DeviceData.timestamp < cutoff_date
    ))
    deleted_count = len(result.scalars().all())
    
    await db.execute(select(DeviceData).filter(
        DeviceData.device_id == device_id,
        DeviceData.timestamp < cutoff_date
    ).delete())
    await db.commit()
    return deleted_count
