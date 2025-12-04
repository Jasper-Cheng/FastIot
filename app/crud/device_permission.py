"""简化的设备权限检查：个人设备由拥有者控制，家庭设备由家庭成员控制"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.db.models.device import Device
from app.db.models.family_device import FamilyDevice
from app.db.models.family_member import FamilyMember

async def can_control_device(
    db: AsyncSession,
    account_id: int,
    device_id: int,
    family_id: Optional[int] = None
) -> bool:
    """检查账号是否可以控制设备
    
    - 个人设备：只有拥有者可以控制
    - 家庭设备：家庭成员都可以控制（如果提供了 family_id，则检查该家庭；否则检查所有家庭）
    """
    # 获取设备
    device_result = await db.execute(select(Device).filter(Device.id == device_id))
    device = device_result.scalar_one_or_none()
    if not device:
        return False
    
    # 如果是个人设备，只有拥有者可以控制
    if device.account_id == account_id:
        return True
    
    # 如果是家庭设备，检查是否是家庭成员
    if family_id:
        # 检查设备是否属于指定家庭
        device_in_family_result = await db.execute(
            select(FamilyDevice).filter(
                FamilyDevice.device_id == device_id,
                FamilyDevice.family_id == family_id
            )
        )
        if not device_in_family_result.scalar_one_or_none():
            return False  # 设备不属于指定家庭
        
        # 检查是否是家庭成员
        member_result = await db.execute(
            select(FamilyMember).filter(
                FamilyMember.family_id == family_id,
                FamilyMember.account_id == account_id
            )
        )
        return member_result.scalar_one_or_none() is not None
    
    # 如果没有指定家庭，检查设备是否属于账号所在的任何家庭
    # 获取账号所在的所有家庭ID
    family_ids_result = await db.execute(
        select(FamilyMember.family_id).filter(FamilyMember.account_id == account_id)
    )
    family_ids = [row[0] for row in family_ids_result.all()]
    
    if not family_ids:
        return False
    
    # 检查设备是否属于这些家庭中的任何一个
    device_families_result = await db.execute(
        select(FamilyDevice.family_id).filter(
            FamilyDevice.device_id == device_id,
            FamilyDevice.family_id.in_(family_ids)
        )
    )
    return device_families_result.first() is not None

