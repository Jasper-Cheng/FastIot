from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.crud.family import (
    get_family,
    get_families_by_account,
    create_family,
    delete_family,
    count_created_families_by_account
)
from app.models.family import FamilyCreate, FamilyInDB
from app.models.device import DeviceInDB
from app.models.user_operation_log import OperationTypeEnum
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.api.utils import (
    extract_token_info,
    log_operation_with_token,
    check_family_creator,
    send_family_notice
)

router = APIRouter()

"""
家庭管理模块 - Client API

【App + Web 通用】
所有接口支持 App 和 Web 平台，平台信息通过 token.platform 字段识别。
"""


@router.post("/", response_model=FamilyInDB)
async def create_family_endpoint(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    family: FamilyCreate = Body(...)
):
    """创建家庭
    
    限制：每个账号最多只能创建6个家庭
    """
    account_id, platform, _ = extract_token_info(token_info)
    
    # 检查创建家庭数量限制
    created_count = await count_created_families_by_account(db, account_id)
    if created_count >= 6:
        raise HTTPException(status_code=400, detail="每个账号最多只能创建6个家庭")
    
    try:
        db_family = await create_family(db, family, account_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_create,
        description=f"创建家庭: {family.name}",
        extra={"family_id": db_family.id, "family_name": family.name}
    )
    
    return db_family


@router.get("/", response_model=List[FamilyInDB])
async def list_families(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """获取当前账号所在的所有家庭"""
    account_id, _, _ = extract_token_info(token_info)
    return await get_families_by_account(db, account_id, skip=skip, limit=limit)


@router.delete("/{family_id}")
async def delete_family_endpoint(
    family_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """删除家庭（仅创建者）"""
    account_id, platform, _ = extract_token_info(token_info)
    
    # 检查家庭是否存在
    family = await get_family(db, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="家庭不存在")
    
    # 检查是否是家庭创建者
    await check_family_creator(db, family_id, account_id, "只有家庭创建者可以删除家庭")
    
    family_name = family.name
    
    # 在删除家庭之前发送通知给所有家庭成员
    await send_family_notice(
        family_id=family_id,
        payload={
            "type": "family_deleted",
            "message": f"家庭 {family_name} 已被删除",
            "family_id": family_id,
            "family_name": family_name,
            "deleted_by_account_id": account_id,
            "platform": platform
        }
    )
    
    # 删除家庭
    success = await delete_family(db, family_id)
    if not success:
        raise HTTPException(status_code=404, detail="删除家庭失败")
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.family_delete,
        description=f"删除家庭: {family_name}",
        extra={"family_id": family_id, "family_name": family_name, "platform": platform, "deleted_by_account_id": account_id}
    )
    
    return {"message": "家庭已删除"}


@router.post("/{family_id}/devices/{device_id}")
async def add_device_to_family(
    family_id: int,
    device_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """将设备添加到家庭（只有当前用户绑定的设备才可以被添加到家庭设备中）"""
    from app.crud.device import get_device
    from app.crud.family_device import check_device_in_family as check_device, create_family_device
    from app.api.utils import check_family_member
    
    account_id, _, _ = extract_token_info(token_info)
    
    # 检查设备是否存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备是否属于当前用户
    if device.account_id != account_id:
        raise HTTPException(status_code=403, detail="无权将设备添加到此家庭，只能添加自己绑定的设备")
    
    # 检查是否是家庭成员
    await check_family_member(db, family_id, account_id)
    
    # 检查设备是否已在家庭中
    if await check_device(db, device_id, family_id):
        raise HTTPException(status_code=400, detail="设备已在此家庭中")
    
    family_device = await create_family_device(db, family_id, device_id)
    if not family_device:
        raise HTTPException(status_code=400, detail="设备添加失败")
    
    # 获取家庭信息用于日志
    family = await get_family(db, family_id)
    family_name = family.name if family else None
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.device_add_to_family,
        description=f"将设备 {device.name} 添加到家庭 {family_name or family_id}",
        extra={
            "family_id": family_id,
            "family_name": family_name,
            "device_id": device.id,
            "device_name": device.name,
            "device_sn": device.sn
        }
    )
    
    # 发送家庭通知
    await send_family_notice(
        family_id=family_id,
        payload={
            "type": "device_added_to_family",
            "message": f"设备 {device.name} 已添加到家庭 {family_name or family_id}",
            "device_id": device.id,
            "device_name": device.name,
            "device_sn": device.sn
        }
    )
    
    return {"message": "设备已添加到家庭", "device_id": device_id, "family_id": family_id}


@router.delete("/{family_id}/devices/{device_id}")
async def remove_device_from_family(
    family_id: int,
    device_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """从家庭中移除设备（只要是属于该家庭的成员，都可以移除设备）"""
    from app.crud.device import get_device
    from app.crud.family_device import delete_family_device
    from app.api.utils import check_family_member, check_device_in_family
    
    account_id, _, _ = extract_token_info(token_info)
    
    # 检查设备是否存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查是否是家庭成员
    await check_family_member(db, family_id, account_id)
    
    # 检查设备是否属于该家庭
    await check_device_in_family(db, device_id, family_id, "设备不属于此家庭")
    
    # 移除设备
    success = await delete_family_device(db, family_id, device_id)
    if not success:
        raise HTTPException(status_code=404, detail="设备不在此家庭中")
    
    # 获取家庭信息用于日志
    family = await get_family(db, family_id)
    family_name = family.name if family else None
    
    # 记录操作日志
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.device_remove_from_family,
        description=f"将设备 {device.name} 从家庭 {family_name or family_id} 中移除",
        extra={
            "family_id": family_id,
            "family_name": family_name,
            "device_id": device.id,
            "device_name": device.name,
            "device_sn": device.sn
        }
    )
    
    # 发送家庭通知
    await send_family_notice(
        family_id=family_id,
        payload={
            "type": "device_removed_from_family",
            "message": f"设备 {device.name} 已从家庭 {family_name or family_id} 中移除",
            "device_id": device.id,
            "device_name": device.name,
            "device_sn": device.sn
        }
    )
    
    return {"message": "设备已从家庭中移除", "device_id": device_id, "family_id": family_id}


@router.get("/{family_id}/devices", response_model=List[DeviceInDB])
async def list_family_devices(
    family_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """获取家庭的所有设备（需要是家庭成员）"""
    from app.crud.family_device import get_family_devices
    from app.api.utils import check_family_member
    
    account_id, _, _ = extract_token_info(token_info)
    
    # 检查是否是家庭成员
    await check_family_member(db, family_id, account_id)
    
    devices = await get_family_devices(db, family_id, skip=skip, limit=limit)
    return devices

