from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.models.device import Device
from app.models.device import DeviceUpdate
from typing import Optional, List
from app.db.models.room_device import RoomDevice
from app.db.models.member_device_permission import MemberDevicePermission

async def get_device(db: AsyncSession, device_id: int) -> Optional[Device]:
    """根据ID获取设备"""
    result = await db.execute(select(Device).filter(Device.id == device_id))
    return result.scalar_one_or_none()

async def get_device_by_sn(db: AsyncSession, sn: str) -> Optional[Device]:
    """根据序列号获取设备"""
    result = await db.execute(select(Device).filter(Device.sn == sn))
    return result.scalar_one_or_none()

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

async def get_devices_by_user(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> List[Device]:
    """根据用户ID获取设备列表"""
    result = await db.execute(select(Device).filter(Device.user_id == user_id).offset(skip).limit(limit))
    return result.scalars().all()
