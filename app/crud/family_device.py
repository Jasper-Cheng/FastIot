from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.db.models.family_device import FamilyDevice
from app.db.models.device import Device
from app.db.models.family import Family
from typing import Optional, List

async def create_family_device(
    db: AsyncSession, family_id: int, device_id: int
) -> Optional[FamilyDevice]:
    """将设备添加到家庭"""
    # 检查是否已存在
    existing = await db.execute(
        select(FamilyDevice).filter(
            and_(
                FamilyDevice.family_id == family_id,
                FamilyDevice.device_id == device_id
            )
        )
    )
    if existing.scalar_one_or_none():
        return None  # 已存在
    
    family_device = FamilyDevice(family_id=family_id, device_id=device_id)
    db.add(family_device)
    await db.commit()
    await db.refresh(family_device)
    return family_device

async def delete_family_device(
    db: AsyncSession, family_id: int, device_id: int
) -> bool:
    """从家庭中移除设备"""
    result = await db.execute(
        select(FamilyDevice).filter(
            and_(
                FamilyDevice.family_id == family_id,
                FamilyDevice.device_id == device_id
            )
        )
    )
    family_device = result.scalar_one_or_none()
    if family_device:
        await db.delete(family_device)
        await db.commit()
        return True
    return False

async def get_family_devices(
    db: AsyncSession, family_id: int, skip: int = 0, limit: int = 100
) -> List[Device]:
    """获取家庭的所有设备"""
    result = await db.execute(
        select(Device)
        .join(FamilyDevice, Device.id == FamilyDevice.device_id)
        .filter(FamilyDevice.family_id == family_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_device_families(
    db: AsyncSession, device_id: int, skip: int = 0, limit: int = 100
) -> List[Family]:
    """获取设备所属的所有家庭"""
    result = await db.execute(
        select(Family)
        .join(FamilyDevice, Family.id == FamilyDevice.family_id)
        .filter(FamilyDevice.device_id == device_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def check_device_in_family(
    db: AsyncSession, device_id: int, family_id: int
) -> bool:
    """检查设备是否属于指定家庭"""
    result = await db.execute(
        select(FamilyDevice).filter(
            and_(
                FamilyDevice.device_id == device_id,
                FamilyDevice.family_id == family_id
            )
        )
    )
    return result.scalar_one_or_none() is not None

async def delete_all_family_devices_by_device(
    db: AsyncSession, device_id: int
) -> int:
    """删除设备的所有家庭关联（解绑设备时使用）"""
    from sqlalchemy import delete
    
    result = await db.execute(
        delete(FamilyDevice).filter(FamilyDevice.device_id == device_id)
    )
    await db.commit()
    return result.rowcount

async def add_account_devices_to_family(
    db: AsyncSession, account_id: int, family_id: int
) -> int:
    """将账号的所有设备添加到家庭
    
    返回成功添加的设备数量（不包括已存在的设备）
    """
    from app.crud.device import get_devices_by_account
    
    # 获取账号的所有个人设备
    devices = await get_devices_by_account(db, account_id, skip=0, limit=1000)
    
    if not devices:
        return 0
    
    # 获取已存在的设备ID列表
    existing_result = await db.execute(
        select(FamilyDevice.device_id).filter(
            and_(
                FamilyDevice.family_id == family_id,
                FamilyDevice.device_id.in_([device.id for device in devices])
            )
        )
    )
    existing_device_ids = {row[0] for row in existing_result.all()}
    
    # 批量添加新设备
    new_devices = [device for device in devices if device.id not in existing_device_ids]
    for device in new_devices:
        family_device = FamilyDevice(family_id=family_id, device_id=device.id)
        db.add(family_device)
    
    if new_devices:
        await db.commit()
    
    return len(new_devices)

async def delete_account_devices_from_family(
    db: AsyncSession, account_id: int, family_id: int
) -> int:
    """从家庭中移除账号的所有设备
    
    返回成功移除的设备数量
    """
    from sqlalchemy import delete
    from app.crud.device import get_devices_by_account
    
    # 获取账号的所有个人设备
    devices = await get_devices_by_account(db, account_id, skip=0, limit=1000)
    
    if not devices:
        return 0
    
    device_ids = [device.id for device in devices]
    
    # 批量删除该账号在该家庭中的设备关联
    result = await db.execute(
        delete(FamilyDevice).filter(
            and_(
                FamilyDevice.family_id == family_id,
                FamilyDevice.device_id.in_(device_ids)
            )
        )
    )
    await db.commit()
    return result.rowcount

