from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.device import Device
from app.models.device import DeviceCreate, DeviceUpdate
from typing import Optional, List

async def get_device(db: AsyncSession, device_id: int) -> Optional[Device]:
    """根据ID获取设备"""
    result = await db.execute(select(Device).filter(Device.id == device_id))
    return result.scalar_one_or_none()

async def get_devices(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Device]:
    """获取设备列表"""
    result = await db.execute(select(Device).offset(skip).limit(limit))
    return result.scalars().all()

async def get_device_by_serial(db: AsyncSession, serial_number: str) -> Optional[Device]:
    """根据序列号获取设备"""
    result = await db.execute(select(Device).filter(Device.serial_number == serial_number))
    return result.scalar_one_or_none()

async def create_device(db: AsyncSession, device: DeviceCreate) -> Device:
    """创建新设备"""
    db_device = Device(**device.dict())
    db.add(db_device)
    await db.commit()
    await db.refresh(db_device)
    return db_device

async def update_device(db: AsyncSession, device_id: int, device: DeviceUpdate) -> Optional[Device]:
    """更新设备信息"""
    db_device = await get_device(db, device_id)
    if not db_device:
        return None
    
    update_data = device.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_device, field, value)
    
    await db.commit()
    await db.refresh(db_device)
    return db_device

async def delete_device(db: AsyncSession, device_id: int) -> bool:
    """删除设备"""
    db_device = await get_device(db, device_id)
    if not db_device:
        return False
    
    await db.delete(db_device)
    await db.commit()
    return True

async def get_devices_by_owner(db: AsyncSession, owner_id: int, skip: int = 0, limit: int = 100) -> List[Device]:
    """根据所有者ID获取设备列表"""
    result = await db.execute(select(Device).filter(Device.owner_id == owner_id).offset(skip).limit(limit))
    return result.scalars().all()
