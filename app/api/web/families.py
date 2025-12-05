from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.crud.family import (
    get_family,
    get_families_by_account,
    create_family,
    update_family,
    delete_family,
    regenerate_invite_code
)
from app.crud.user_operation_log import user_operation_log
from app.models.family import FamilyCreate, FamilyUpdate, FamilyInDB
from app.models.device import DeviceInDB
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token

router = APIRouter()


@router.post("/", response_model=FamilyInDB)
async def create_family_endpoint(
    family: FamilyCreate,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """创建家庭
    
    限制：每个账号最多只能创建6个家庭
    """
    account_id = token_info["account_id"]
    
    try:
        db_family = await create_family(db, family, account_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 记录操作日志
    await user_operation_log.create(
        db=db,
        obj_in=UserOperationLogCreate(
            operation_type=OperationTypeEnum.family_create,
            description=f"创建家庭: {family.name}",
            extra={"family_id": db_family.id, "family_name": family.name}
        ),
        account_id=account_id
    )
    
    return db_family


@router.get("/", response_model=List[FamilyInDB])
async def list_families(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    token_info: dict = Depends(get_current_token)
):
    """获取当前账号所在的所有家庭"""
    account_id = token_info["account_id"]
    return await get_families_by_account(db, account_id, skip=skip, limit=limit)


@router.get("/{family_id}", response_model=FamilyInDB)
async def get_family_endpoint(
    family_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """获取家庭详情"""
    account_id = token_info["account_id"]
    
    family = await get_family(db, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    # 检查是否是家庭成员
    from app.crud.family_member import get_family_member_by_family_and_account
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member:
        raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    return family


@router.patch("/{family_id}", response_model=FamilyInDB)
async def update_family_endpoint(
    family_id: int,
    family: FamilyUpdate,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """更新家庭信息（家庭成员）"""
    account_id = token_info["account_id"]
    
    # 检查是否是家庭成员
    from app.crud.family_member import get_family_member_by_family_and_account
    
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member:
        raise HTTPException(status_code=403, detail="无权修改此家庭信息")
    
    updated = await update_family(db, family_id, family)
    if not updated:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    return updated


@router.delete("/{family_id}")
async def delete_family_endpoint(
    family_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """删除家庭（仅创建者）"""
    account_id = token_info["account_id"]
    
    # 检查是否是家庭创建者
    from app.crud.family_member import get_family_member_by_family_and_account
    from app.models.family_member import FamilyMemberRole

    family = await get_family(db, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member or family_member.role != FamilyMemberRole.creator:
        raise HTTPException(status_code=403, detail="只有家庭创建者可以删除家庭")
    
    family_name = family.name
    success = await delete_family(db, family_id)
    if not success:
        raise HTTPException(status_code=404, detail="删除家庭失败")
    
    # 记录操作日志
    await user_operation_log.create(
        db=db,
        obj_in=UserOperationLogCreate(
            operation_type=OperationTypeEnum.family_delete,
            description=f"删除家庭: {family_name}",
            extra={"family_id": family_id, "family_name": family_name}
        ),
        account_id=account_id
    )
    
    return {"message": "家庭已删除"}


@router.post("/{family_id}/regenerate-invite-code")
async def regenerate_invite_code_endpoint(
    family_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """重新生成家庭邀请码（仅创建者）"""
    account_id = token_info["account_id"]
    
    # 检查是否是家庭创建者
    from app.crud.family_member import get_family_member_by_family_and_account
    from app.models.family_member import FamilyMemberRole
    
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member or family_member.role != FamilyMemberRole.creator:
        raise HTTPException(status_code=403, detail="只有家庭创建者可以重新生成邀请码")
    
    invite_code = await regenerate_invite_code(db, family_id)
    if not invite_code:
        raise HTTPException(status_code=404, detail="重新生成邀请码失败")
    
    return {"invite_code": invite_code}


@router.post("/{family_id}/devices/{device_id}")
async def add_device_to_family(
    family_id: int,
    device_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """将设备添加到家庭（只有当前用户绑定的设备才可以被添加到家庭设备中）"""
    account_id = token_info["account_id"]
    
    # 检查设备是否存在
    from app.crud.device import get_device
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备是否属于当前用户
    if device.account_id != account_id:
        raise HTTPException(status_code=403, detail="无权将设备添加到此家庭，只能添加自己绑定的设备")
    
    # 检查是否是家庭成员
    from app.crud.family_member import get_family_member_by_family_and_account
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member:
        raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    # 检查设备是否已在家庭中
    from app.crud.family_device import check_device_in_family, create_family_device
    if await check_device_in_family(db, device_id, family_id):
        raise HTTPException(status_code=400, detail="设备已在此家庭中")
    
    family_device = await create_family_device(db, family_id, device_id)
    if not family_device:
        raise HTTPException(status_code=400, detail="设备添加失败")
    
    return {"message": "设备已添加到家庭", "device_id": device_id, "family_id": family_id}


@router.delete("/{family_id}/devices/{device_id}")
async def remove_device_from_family(
    family_id: int,
    device_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """从家庭中移除设备（只要是属于该家庭的成员，都可以移除设备）"""
    account_id = token_info["account_id"]
    
    # 检查设备是否存在
    from app.crud.device import get_device
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查是否是家庭成员
    from app.crud.family_member import get_family_member_by_family_and_account
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member:
        raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    # 检查设备是否属于该家庭
    from app.crud.family_device import check_device_in_family
    if not await check_device_in_family(db, device_id, family_id):
        raise HTTPException(status_code=404, detail="设备不属于此家庭")
    
    # 移除设备
    from app.crud.family_device import delete_family_device
    success = await delete_family_device(db, family_id, device_id)
    if not success:
        raise HTTPException(status_code=404, detail="设备不在此家庭中")
    
    return {"message": "设备已从家庭中移除", "device_id": device_id, "family_id": family_id}


@router.get("/{family_id}/devices", response_model=List[DeviceInDB])
async def list_family_devices(
    family_id: int,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    token_info: dict = Depends(get_current_token)
):
    """获取家庭的所有设备（需要是家庭成员）"""
    account_id = token_info["account_id"]
    
    # 检查是否是家庭成员
    from app.crud.family_member import get_family_member_by_family_and_account
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member:
        raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    from app.crud.family_device import get_family_devices
    devices = await get_family_devices(db, family_id, skip=skip, limit=limit)
    return devices

