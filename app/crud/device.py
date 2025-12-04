from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.device import Device
from app.models.device import DeviceUpdate
from typing import Optional, List

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
    
    update_data = device.dict(exclude_unset=True)
    # 允许更新的字段白名单（移除 family_id，因为现在使用 family_device 关联表）
    allowed_fields = {"name", "sn", "status", "account_id"}
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

async def get_devices_by_account(
    db: AsyncSession,
    account_id: int,
    skip: int = 0,
    limit: int = 100,
    family_id: Optional[int] = None
) -> List[Device]:
    """根据账号ID获取设备列表

    - 提供 family_id 时：只返回该家庭的设备
    - 未提供 family_id 时：只返回个人设备
    """
    from app.db.models.family_member import FamilyMember
    from app.db.models.family_device import FamilyDevice

    if family_id:
        # 检查账号是否属于该家庭
        family_member_result = await db.execute(
            select(FamilyMember).filter(
                FamilyMember.family_id == family_id,
                FamilyMember.account_id == account_id
            )
        )
        if not family_member_result.scalar_one_or_none():
            return []

        query = (
            select(Device)
            .join(FamilyDevice, Device.id == FamilyDevice.device_id)
            .filter(FamilyDevice.family_id == family_id)
            .offset(skip)
            .limit(limit)
        )
    else:
        # 仅返回个人设备
        query = (
            select(Device)
            .filter(Device.account_id == account_id)
            .offset(skip)
            .limit(limit)
        )

    result = await db.execute(query)
    return result.scalars().all()
