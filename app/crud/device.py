from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.db.models.device import Device
from app.models.device import DeviceCreate, DeviceUpdate
from app.db.models.device_data import DeviceData
from typing import Optional, List, Tuple
from datetime import datetime

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
    # 仅传递 ORM 支持的字段，避免未知字段报错
    db_device = Device(
        name=device.name,
        serial_number=device.serial_number,
        owner_id=device.owner_id,
        status=(device.status.value if hasattr(device.status, 'value') else device.status),
    )
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
    # 允许更新的字段白名单
    allowed_fields = {"name", "serial_number", "status"}
    for field, value in update_data.items():
        if field not in allowed_fields:
            continue
        if field == "status" and value is not None:
            setattr(db_device, field, (value.value if hasattr(value, 'value') else value))
        else:
            setattr(db_device, field, value)
    
    await db.commit()
    await db.refresh(db_device)
    return db_device

async def delete_device(db: AsyncSession, device_id: int) -> bool:
    """删除设备"""
    db_device = await get_device(db, device_id)
    if not db_device:
        return False
    # 先删除关联的 DeviceData，避免外键约束错误
    await db.execute(delete(DeviceData).where(DeviceData.device_id == device_id))
    await db.delete(db_device)
    await db.commit()
    return True

async def get_devices_by_owner(db: AsyncSession, owner_id: int, skip: int = 0, limit: int = 100) -> List[Device]:
    """根据所有者ID获取设备列表"""
    result = await db.execute(select(Device).filter(Device.owner_id == owner_id).offset(skip).limit(limit))
    return result.scalars().all()

async def get_devices_by_owner_with_count(db: AsyncSession, owner_id: int, skip: int = 0, limit: int = 100) -> Tuple[List[Device], int]:
    """根据所有者ID获取设备列表和总数"""
    # 获取总数
    count_result = await db.execute(
        select(func.count(Device.id)).filter(Device.owner_id == owner_id)
    )
    total = count_result.scalar()
    
    # 获取设备列表
    devices_result = await db.execute(
        select(Device).filter(Device.owner_id == owner_id).offset(skip).limit(limit)
    )
    devices = devices_result.scalars().all()
    
    return devices, total

async def update_device_last_active(db: AsyncSession, device_id: int) -> bool:
    """更新设备最后活跃时间"""
    db_device = await get_device(db, device_id)
    if not db_device:
        return False
    
    db_device.last_active = datetime.utcnow()
    await db.commit()
    return True

async def get_device_count_by_owner(db: AsyncSession, owner_id: int) -> int:
    """获取用户设备总数"""
    result = await db.execute(
        select(func.count(Device.id)).filter(Device.owner_id == owner_id)
    )
    return result.scalar()
