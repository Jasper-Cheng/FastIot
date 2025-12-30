from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.crud.family import (
    get_family,
    get_families_by_account,
    create_family,
    delete_family
)
from app.crud.user_operation_log import user_operation_log
from app.models.family import FamilyCreate, FamilyInDB
from app.models.device import DeviceInDB
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.services.mqtt_service import mqtt_service

router = APIRouter()


@router.post("/", response_model=FamilyInDB)
async def create_family_endpoint(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    family: FamilyCreate = Body(...)
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
            description=f"通过App创建家庭: {family.name}",
            extra={"family_id": db_family.id, "family_name": family.name, "platform": "app"}
        ),
        account_id=account_id
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
    account_id = token_info["account_id"]
    return await get_families_by_account(db, account_id, skip=skip, limit=limit)


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
            description=f"通过App删除家庭: {family_name}",
            extra={"family_id": family_id, "family_name": family_name, "platform": "app"}
        ),
        account_id=account_id
    )
    
    # 暂时不发送家庭消息通知
    # try:
    #     role = token_info.get("role")
    #     if family_id is not None:
    #         await mqtt_service.publish_home_notice(
    #             home_id=str(family_id),
    #             payload={
    #                 "method": "family.message",
    #                 "params": {
    #                     "type": "family.delete",
    #                     "data": {
    #                         "senderId": account_id,
    #                         "senderRole": role,
    #                         "title": "家庭删除",
    #                         "message": f"家庭 {family_name} 已删除",
    #                         "level": "warning",
    #                         "familyId": family_id,
    #                         "familyName": family_name
    #                     }
    #                 }
    #             }
    #         )
    # except Exception as e:
    #     # 发送消息失败不影响删除流程
    #     print(f"发送删除家庭消息失败: {e}")
    
    return {"message": "家庭已删除"}


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
    
    # 获取家庭信息用于消息和日志
    family = await get_family(db, family_id)
    family_name = family.name if family else None
    
    # 记录操作日志
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.device_add_to_family,
                description=f"通过App将设备 {device.name} 添加到家庭 {family_name or family_id}",
                extra={
                    "family_id": family_id,
                    "family_name": family_name,
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_sn": device.sn,
                    "platform": "app"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        # 记录操作失败不影响添加流程
        print(f"记录设备添加到家庭操作日志失败: {e}")
    
    # 暂时不发送家庭消息通知设备已添加到家庭
    # try:
    #     role = token_info.get("role")
    #     if family_id is not None:
    #         await mqtt_service.publish_home_notice(
    #             home_id=str(family_id),
    #             payload={
    #                 "method": "family.message",
    #                 "params": {
    #                     "type": "device.add",
    #                     "data": {
    #                         "senderId": account_id,
    #                         "senderRole": role,
    #                         "title": "设备已添加到家庭",
    #                         "message": f"设备 {device.name} 已添加到家庭 {family_name or family_id}",
    #                         "level": "normal",
    #                         "familyId": family_id,
    #                         "familyName": family_name,
    #                         "deviceId": device.id,
    #                         "deviceName": device.name,
    #                         "deviceSn": device.sn
    #                     }
    #                 }
    #             }
    #         )
    # except Exception as e:
    #     # 发送消息失败不影响添加流程
    #     print(f"发送设备添加到家庭消息失败: {e}")
    
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
    
    # 获取家庭信息用于消息和日志
    family = await get_family(db, family_id)
    family_name = family.name if family else None
    
    # 记录操作日志
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.device_remove_from_family,
                description=f"通过App将设备 {device.name} 从家庭 {family_name or family_id} 中移除",
                extra={
                    "family_id": family_id,
                    "family_name": family_name,
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_sn": device.sn,
                    "platform": "app"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        # 记录操作失败不影响移除流程
        print(f"记录设备从家庭移除操作日志失败: {e}")
    
    # 暂时不发送家庭消息通知设备已从家庭中移除
    # try:
    #     role = token_info.get("role")
    #     if family_id is not None:
    #         await mqtt_service.publish_home_notice(
    #             home_id=str(family_id),
    #             payload={
    #                 "method": "family.message",
    #                 "params": {
    #                     "type": "device.remove",
    #                     "data": {
    #                         "senderId": account_id,
    #                         "senderRole": role,
    #                         "title": "设备已从家庭中移除",
    #                         "message": f"设备 {device.name} 已从家庭 {family_name or family_id} 中移除",
    #                         "level": "normal",
    #                         "familyId": family_id,
    #                         "familyName": family_name,
    #                         "deviceId": device.id,
    #                         "deviceName": device.name,
    #                         "deviceSn": device.sn
    #                     }
    #                 }
    #             }
    #         )
    # except Exception as e:
    #     # 发送消息失败不影响移除流程
    #     print(f"发送设备从家庭移除消息失败: {e}")
    
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
    account_id = token_info["account_id"]
    
    # 检查是否是家庭成员
    from app.crud.family_member import get_family_member_by_family_and_account
    family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
    if not family_member:
        raise HTTPException(status_code=403, detail="无权访问此家庭")
    
    from app.crud.family_device import get_family_devices
    devices = await get_family_devices(db, family_id, skip=skip, limit=limit)
    return devices
