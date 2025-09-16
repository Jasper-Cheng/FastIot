from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.db.models.device import Device
from app.models.device import DeviceCreate, DeviceUpdate
from typing import Optional, List, Tuple
from app.db.models.room_device import RoomDevice
from app.db.models.member_device_permission import MemberDevicePermission

async def get_device(db: AsyncSession, device_id: int) -> Optional[Device]:
    """根据ID获取设备"""
    result = await db.execute(select(Device).filter(Device.id == device_id))
    return result.scalar_one_or_none()

async def get_devices(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Device]:
    """获取设备列表"""
    result = await db.execute(select(Device).offset(skip).limit(limit))
    return result.scalars().all()

async def get_device_by_sn(db: AsyncSession, sn: str) -> Optional[Device]:
    """根据序列号获取设备"""
    result = await db.execute(select(Device).filter(Device.sn == sn))
    return result.scalar_one_or_none()

async def create_device(db: AsyncSession, device: DeviceCreate) -> Device:
    """创建新设备"""
    db_device = Device(
        name=device.name,
        sn=device.sn,
        user_id=device.user_id,
        model_id=device.model_id,
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
    
    previous_user_id = db_device.user_id
    update_data = device.dict(exclude_unset=True)
    # 允许更新的字段白名单
    allowed_fields = {"name", "sn", "status", "user_id"}
    for field, value in update_data.items():
        if field not in allowed_fields:
            continue
        if field == "status" and value is not None:
            setattr(db_device, field, (value.value if hasattr(value, 'value') else value))
        else:
            setattr(db_device, field, value)
    # 如果设备从绑定状态改为未绑定，清理与用户相关的关联记录
    if previous_user_id is not None and db_device.user_id is None:
        # 删除房间-设备关系
        await db.execute(
            delete(RoomDevice).where(RoomDevice.device_id == device_id)
        )
        # 删除成员-设备权限关系
        await db.execute(
            delete(MemberDevicePermission).where(MemberDevicePermission.device_id == device_id)
        )

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

async def get_devices_by_user(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> List[Device]:
    """根据用户ID获取设备列表"""
    result = await db.execute(select(Device).filter(Device.user_id == user_id).offset(skip).limit(limit))
    return result.scalars().all()

async def get_devices_by_user_with_count(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> Tuple[List[Device], int]:
    """根据用户ID获取设备列表和总数"""
    # 获取总数
    count_result = await db.execute(
        select(func.count(Device.id)).filter(Device.user_id == user_id)
    )
    total = count_result.scalar()
    
    # 获取设备列表
    devices_result = await db.execute(
        select(Device).filter(Device.user_id == user_id).offset(skip).limit(limit)
    )
    devices = devices_result.scalars().all()
    
    return devices, total

async def get_device_count_by_user(db: AsyncSession, user_id: int) -> int:
    """获取用户设备总数"""
    result = await db.execute(
        select(func.count(Device.id)).filter(Device.user_id == user_id)
    )
    return result.scalar()
