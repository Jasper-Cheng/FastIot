from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.dependencies import get_db
from app.crud.member_device_permission import (
    get_member_device_permission, get_permission_by_member_and_device,
    get_permissions_by_member, get_permissions_by_device,
    create_member_device_permission, update_member_device_permission,
    delete_member_device_permission, check_member_device_permission
)
from app.crud.member import get_member
from app.crud.device import get_device
from app.models.member_device_permission import (
    MemberDevicePermission, MemberDevicePermissionCreate, MemberDevicePermissionUpdate
)
from app.models.user import User
from app.api.endpoints.auth import get_current_user

router = APIRouter()

@router.get("/member/{member_id}", response_model=List[MemberDevicePermission], tags=["member-device-permissions"])
async def read_member_permissions(
    member_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取成员的设备权限列表"""
    # 检查成员是否属于当前用户
    member = await get_member(db, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    if member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问该成员的权限信息"
        )
    
    permissions = await get_permissions_by_member(db, member_id=member_id, skip=skip, limit=limit)
    return permissions

@router.get("/device/{device_id}", response_model=List[MemberDevicePermission], tags=["member-device-permissions"])
async def read_device_permissions(
    device_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备的成员权限列表"""
    # 检查设备是否属于当前用户
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问该设备的权限信息"
        )
    
    permissions = await get_permissions_by_device(db, device_id=device_id, skip=skip, limit=limit)
    return permissions

@router.post("/", response_model=MemberDevicePermission, tags=["member-device-permissions"])
async def create_new_permission(
    permission: MemberDevicePermissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建成员设备权限"""
    # 检查成员是否属于当前用户
    member = await get_member(db, permission.member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    if member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限为该成员设置权限"
        )
    
    # 检查设备是否属于当前用户
    device = await get_device(db, permission.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限为该设备设置权限"
        )
    
    # 检查权限是否已存在
    existing_permission = await get_permission_by_member_and_device(db, permission.member_id, permission.device_id)
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该成员对该设备的权限已存在"
        )
    
    return await create_member_device_permission(db=db, permission=permission)

@router.get("/{permission_id}", response_model=MemberDevicePermission, tags=["member-device-permissions"])
async def read_permission(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定权限信息"""
    permission = await get_member_device_permission(db, permission_id=permission_id)
    if permission is None:
        raise HTTPException(status_code=404, detail="权限不存在")
    
    # 检查成员是否属于当前用户
    member = await get_member(db, permission.member_id)
    if not member or member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问该权限信息"
        )
    
    return permission

@router.put("/{permission_id}", response_model=MemberDevicePermission, tags=["member-device-permissions"])
async def update_permission_info(
    permission_id: int,
    permission: MemberDevicePermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新权限信息"""
    # 先获取权限信息，检查成员权限
    db_permission = await get_member_device_permission(db, permission_id=permission_id)
    if db_permission is None:
        raise HTTPException(status_code=404, detail="权限不存在")
    
    # 检查成员是否属于当前用户
    member = await get_member(db, db_permission.member_id)
    if not member or member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改该权限信息"
        )
    
    updated_permission = await update_member_device_permission(db=db, permission_id=permission_id, permission=permission)
    if updated_permission is None:
        raise HTTPException(status_code=404, detail="权限不存在")
    
    return updated_permission

@router.delete("/{permission_id}", tags=["member-device-permissions"])
async def delete_permission_info(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除权限"""
    # 先获取权限信息，检查成员权限
    db_permission = await get_member_device_permission(db, permission_id=permission_id)
    if db_permission is None:
        raise HTTPException(status_code=404, detail="权限不存在")
    
    # 检查成员是否属于当前用户
    member = await get_member(db, db_permission.member_id)
    if not member or member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除该权限信息"
        )
    
    success = await delete_member_device_permission(db=db, permission_id=permission_id)
    if not success:
        raise HTTPException(status_code=404, detail="权限不存在")
    
    return {"message": "权限删除成功"}

@router.get("/check/{member_id}/{device_id}", tags=["member-device-permissions"])
async def check_permission(
    member_id: int,
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查成员是否有设备控制权限"""
    # 检查成员是否属于当前用户
    member = await get_member(db, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    if member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限检查该成员的权限"
        )
    
    # 检查设备是否属于当前用户
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限检查该设备的权限"
        )
    
    can_control = await check_member_device_permission(db, member_id, device_id)
    return {"can_control": can_control}
