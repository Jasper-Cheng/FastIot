from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_db
from app.crud.member_device_permission import (
    get_permission_by_member_and_device,
    get_permissions_by_member,
    get_permissions_by_device,
    create_member_device_permission,
    delete_member_device_permission,
)
from app.crud.member import get_member
from app.crud.device import get_device
from app.models.member_device_permission import (
    MemberDevicePermissionCreate,
    MemberDevicePermissionInDB,
)

router = APIRouter()


@router.get("/", response_model=List[MemberDevicePermissionInDB])
async def list_member_device_permissions(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    member_id: Optional[int] = Query(None, description="按成员ID筛选"),
    device_id: Optional[int] = Query(None, description="按设备ID筛选"),
):
    """获取成员设备权限列表
    
    支持按成员ID、设备ID筛选
    """
    if member_id:
        # 验证成员存在
        member = await get_member(db, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="成员不存在")
        
        return await get_permissions_by_member(db, member_id, skip, limit)
    elif device_id:
        # 验证设备存在
        device = await get_device(db, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")
        
        return await get_permissions_by_device(db, device_id, skip, limit)
    else:
        raise HTTPException(status_code=400, detail="必须指定成员ID或设备ID")


@router.post("/", response_model=MemberDevicePermissionInDB)
async def create_member_device_permission_item(
    payload: MemberDevicePermissionCreate, 
    db: AsyncSession = Depends(get_db)
):
    """创建成员设备权限
    
    示例请求体：
    {
      "member_id": 1,
      "device_id": 1
    }
    """
    # 验证成员存在
    member = await get_member(db, payload.member_id)
    if not member:
        raise HTTPException(status_code=400, detail="成员不存在")
    
    # 验证设备存在
    device = await get_device(db, payload.device_id)
    if not device:
        raise HTTPException(status_code=400, detail="设备不存在")
    
    # 检查是否已存在权限记录
    existing = await get_permission_by_member_and_device(db, payload.member_id, payload.device_id)
    if existing:
        raise HTTPException(status_code=400, detail="权限记录已存在")
    
    return await create_member_device_permission(db, payload)


@router.delete("/{permission_id}")
async def delete_member_device_permission_item(permission_id: int, db: AsyncSession = Depends(get_db)):
    """删除成员设备权限"""
    ok = await delete_member_device_permission(db, permission_id)
    if not ok:
        raise HTTPException(status_code=404, detail="权限记录不存在")
    return {"message": "删除成功"}


@router.get("/member/{member_id}/stats", response_model=dict)
async def get_member_permission_stats(member_id: int, db: AsyncSession = Depends(get_db)):
    """获取成员权限统计信息"""
    # 验证成员存在
    member = await get_member(db, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    from sqlalchemy import select, func
    from app.db.models.member_device_permission import MemberDevicePermission
    
    # 总权限数
    total_result = await db.execute(
        select(func.count(MemberDevicePermission.id))
        .filter(MemberDevicePermission.member_id == member_id)
    )
    total_permissions = total_result.scalar()
    
    return {
        "member_id": member_id,
        "total_permissions": total_permissions
    }
