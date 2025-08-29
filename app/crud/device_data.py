from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.device_data import DeviceData
from app.models.device_data import DeviceDataCreate
from typing import Optional, List

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
    """获取设备的最新数据（按id倒序视作最新）"""
    result = await db.execute(select(DeviceData).filter(DeviceData.device_id == device_id).order_by(DeviceData.id.desc()))
    return result.scalar_one_or_none()

# 已移除按时间范围查询功能（无 timestamp 字段）

async def delete_device_data(db: AsyncSession, data_id: int) -> bool:
    """删除设备数据"""
    db_device_data = await get_device_data(db, data_id)
    if not db_device_data:
        return False
    
    await db.delete(db_device_data)
    await db.commit()
    return True

# 已移除按时间清理旧数据功能（无 timestamp 字段）
