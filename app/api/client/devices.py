from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.crud.device import (
    get_device,
    get_device_by_sn,
    get_devices_by_account,
    update_device,
)
from app.models.device import DeviceUpdate, DeviceInDB, DeviceStatus, DeviceNameUpdate, DeviceBindBySNRequest
from app.models.user_operation_log import OperationTypeEnum
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.api.utils import (
    extract_token_info,
    log_operation_with_token,
    check_family_member,
    send_device_notice
)

router = APIRouter()

"""
设备管理模块 - Client API

【App + Web 通用】
所有接口支持 App 和 Web 平台，平台信息通过 token.platform 字段识别。
"""


@router.get("/", response_model=List[DeviceInDB])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    family_id: Optional[int] = Query(None, description="当前家庭ID，如果提供则只返回该家庭的设备"),
):
    """获取设备列表
    
    - 如果提供 family_id：只返回个人设备 + 该家庭的设备
    - 如果不提供 family_id：返回个人设备 + 所有家庭的设备
    """
    account_id, _, _ = extract_token_info(token_info)
    
    # 如果提供了 family_id，验证是否是家庭成员
    if family_id:
        await check_family_member(db, family_id, account_id)
    
    return await get_devices_by_account(
        db, 
        account_id=account_id, 
        skip=skip, 
        limit=limit,
        family_id=family_id
    )


@router.patch("/{device_id}/name", response_model=DeviceInDB)
async def update_device_name(
    device_id: int, 
    payload: DeviceNameUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    family_id: Optional[int] = Query(None, description="当前家庭ID，如果提供则判断为家庭修改，可以修改家庭内的所有设备"),
):
    """修改设备名称
    
    - name: 新的设备名称
    - family_id: 可选，如果提供则判断为家庭修改，可以修改家庭内的所有设备；如果不提供则判断为个人修改，只能修改自己绑定的设备
    """
    from app.api.utils import check_device_in_family
    
    account_id, _, _ = extract_token_info(token_info)
    
    # 检查设备是否存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 权限检查
    if family_id is None:
        # 个人修改：只能修改自己绑定的设备
        if device.account_id != account_id:
            raise HTTPException(status_code=403, detail="无权修改此设备，只能修改自己绑定的设备")
    else:
        # 家庭修改：可以修改家庭内的所有设备
        await check_family_member(db, family_id, account_id)
        await check_device_in_family(db, device_id, family_id, "设备不属于此家庭")
    
    # 更新设备名称
    old_name = device.name
    updated = await update_device(db, device_id, DeviceUpdate(name=payload.name))
    if not updated:
        raise HTTPException(status_code=500, detail="更新设备失败")
    
    # 记录操作日志
    try:
        await log_operation_with_token(
            db=db,
            token_info=token_info,
            operation_type=OperationTypeEnum.device_name_update,
            description=f"修改设备名称：{old_name} -> {payload.name}",
            extra={
                "device_id": device.id,
                "device_name": payload.name,
                "old_name": old_name,
                "device_sn": device.sn,
                "family_id": family_id
            }
        )
    except Exception as e:
        # 记录操作失败不影响更新流程，回滚以清除错误状态
        await db.rollback()
        print(f"记录设备名称修改操作日志失败: {e}")
        # 重新获取设备对象以确保可以访问（因为会话已回滚）
        updated = await get_device(db, device_id)
        if not updated:
            raise HTTPException(status_code=500, detail="更新设备后无法获取设备信息")
    
    # 使用 utils 发送设备消息通知
    await send_device_notice(
        device_sn=updated.sn,
        payload={
            "type": "device_name_updated",
            "message": f"设备名称已更新：{old_name} -> {payload.name}",
            "device_id": updated.id,
            "device_name": payload.name,
            "old_name": old_name,
            "device_sn": updated.sn,
            "account_id": account_id,
            "family_id": family_id,
            "operator_account_id": account_id
        }
    )
    
    return DeviceInDB.model_validate(updated)


@router.post("/bind-by-sn/", response_model=DeviceInDB)
async def bind_device_by_sn(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    payload: DeviceBindBySNRequest = Body(...),
    family_id: Optional[int] = Query(None, description="家庭ID，如果提供则将该设备添加到该家庭")
):
    """通过序列号绑定设备到当前账号
    
    - sn: 设备序列号
    """
    from app.crud.family_device import check_device_in_family as check_device, create_family_device
    
    account_id, _, _ = extract_token_info(token_info)
    
    # 通过序列号查找设备
    device = await get_device_by_sn(db, payload.sn)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备状态是否允许绑定
    if device.account_id is not None:
        raise HTTPException(status_code=400, detail="设备已被其他账号绑定")
    
    if device.status != 'unbound':
        raise HTTPException(status_code=400, detail=f"设备状态不允许绑定，当前状态：{device.status}")
    
    # 绑定设备：绑定账号并更新状态
    device.account_id = account_id
    device.status = 'bound'
    
    await db.commit()
    await db.refresh(device)

    # 如果提供了 family_id，将设备添加到该家庭
    if family_id is not None:
        await check_family_member(db, family_id, account_id)
        
        # 检查设备是否已在家庭中
        if not await check_device(db, device.id, family_id):
            # 设备不在家庭中，添加到家庭
            family_device = await create_family_device(db, family_id, device.id)
            if not family_device:
                print(f"设备 {device.id} 添加到家庭 {family_id} 失败或已存在")

    # 记录设备绑定操作
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.device_bind,
        description=f"绑定设备：{device.name}（SN: {device.sn}）",
        extra={
            "device_id": device.id,
            "device_name": device.name,
            "device_sn": device.sn,
            "bound_account_id": account_id,
            "device_status": device.status
        }
    )

    # 发送设备绑定消息通知
    await send_device_notice(
        device_sn=device.sn,
        payload={
            "type": "device_bind",
            "message": f"设备已绑定：{device.name}（SN: {device.sn}）",
            "device_id": device.id,
            "device_name": device.name,
            "device_sn": device.sn,
            "account_id": account_id,
            "family_id": family_id,
            "operator_account_id": account_id
        }
    )

    return device


@router.delete("/unbind-by-sn/{sn}", response_model=DeviceInDB)
async def unbind_device_by_sn(
    sn: str, 
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """通过序列号解绑设备，将设备从账号中移除
    
    - sn: 设备序列号
    """
    from app.crud.family_device import delete_all_family_devices_by_device
    
    account_id, _, _ = extract_token_info(token_info)

    # 通过序列号查找设备
    device = await get_device_by_sn(db, sn)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 检查设备是否已绑定
    if device.account_id is None:
        raise HTTPException(status_code=400, detail="设备未绑定，无需解绑")
    
    # 验证设备是否属于当前账号
    if device.account_id != account_id:
        raise HTTPException(status_code=403, detail="无权解绑此设备")
    
    # 记录解绑前的设备信息
    device_name = device.name
    
    # 从所有家庭中移除设备
    removed_count = await delete_all_family_devices_by_device(db, device.id)
    if removed_count > 0:
        print(f"设备 {device_name} 已从 {removed_count} 个家庭中移除")
    
    # 通过统一更新逻辑处理解绑
    updated = await update_device(db, device.id, DeviceUpdate(account_id=None, status=DeviceStatus.unbound))
    
    # 记录设备解绑操作
    await log_operation_with_token(
        db=db,
        token_info=token_info,
        operation_type=OperationTypeEnum.device_unbind,
        description=f"解绑设备：{device_name}（SN: {sn}）",
        extra={
            "device_id": device.id,
            "device_name": device_name,
            "device_sn": sn,
            "unbound_account_id": account_id,
            "device_status": updated.status if updated else "unbound"
        }
    )

    await send_device_notice(
        device_sn=sn,
        payload={
            "type": "device_unbind",
            "message": f"设备已解绑：{device_name}（SN: {sn}）",
            "device_id": device.id,
            "device_name": device_name,
            "device_sn": sn,
            "operator_account_id": account_id
        }
    )
    
    return updated

