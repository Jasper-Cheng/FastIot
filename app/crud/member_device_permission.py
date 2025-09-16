from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.member_device_permission import MemberDevicePermission
from app.models.member_device_permission import MemberDevicePermissionCreate, MemberDevicePermissionUpdate
from typing import Optional, List

async def get_member_device_permission(db: AsyncSession, permission_id: int) -> Optional[MemberDevicePermission]:
    """根据ID获取成员设备权限"""
    result = await db.execute(select(MemberDevicePermission).filter(MemberDevicePermission.id == permission_id))
    return result.scalar_one_or_none()

async def get_permission_by_member_and_device(db: AsyncSession, member_id: int, device_id: int) -> Optional[MemberDevicePermission]:
    """根据成员ID和设备ID获取权限"""
    result = await db.execute(
        select(MemberDevicePermission).filter(
            MemberDevicePermission.member_id == member_id,
            MemberDevicePermission.device_id == device_id
        )
    )
    return result.scalar_one_or_none()

async def get_permissions_by_member(db: AsyncSession, member_id: int, skip: int = 0, limit: int = 100) -> List[MemberDevicePermission]:
    """根据成员ID获取所有权限"""
    result = await db.execute(
        select(MemberDevicePermission)
        .filter(MemberDevicePermission.member_id == member_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_permissions_by_device(db: AsyncSession, device_id: int, skip: int = 0, limit: int = 100) -> List[MemberDevicePermission]:
    """根据设备ID获取所有权限"""
    result = await db.execute(
        select(MemberDevicePermission)
        .filter(MemberDevicePermission.device_id == device_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_member_device_permission(db: AsyncSession, permission: MemberDevicePermissionCreate) -> MemberDevicePermission:
    """创建成员设备权限"""
    db_permission = MemberDevicePermission(
        member_id=permission.member_id,
        device_id=permission.device_id
    )
    db.add(db_permission)
    await db.commit()
    await db.refresh(db_permission)
    return db_permission

async def update_member_device_permission(db: AsyncSession, permission_id: int, permission: MemberDevicePermissionUpdate) -> Optional[MemberDevicePermission]:
    """更新成员设备权限"""
    db_permission = await get_member_device_permission(db, permission_id)
    if not db_permission:
        return None
    
    update_data = permission.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_permission, field, value)
    
    await db.commit()
    await db.refresh(db_permission)
    return db_permission

async def delete_member_device_permission(db: AsyncSession, permission_id: int) -> bool:
    """删除成员设备权限"""
    db_permission = await get_member_device_permission(db, permission_id)
    if not db_permission:
        return False
    
    await db.delete(db_permission)
    await db.commit()
    return True

async def check_member_device_permission(db: AsyncSession, member_id: int, device_id: int) -> bool:
    """检查成员是否有设备控制权限"""
    permission = await get_permission_by_member_and_device(db, member_id, device_id)
    return permission.can_control if permission else False
