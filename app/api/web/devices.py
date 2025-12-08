from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.crud.device import (
    get_device,
    get_device_by_sn,
    get_devices_by_account,
    update_device,
)
from app.crud.user_operation_log import user_operation_log
from app.models.device import DeviceUpdate, DeviceInDB, DeviceStatus, DeviceNameUpdate, DeviceBindBySNRequest
from app.models.account import AccountRole
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.services.websocket_tool import websocket_tool

router = APIRouter()


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
    account_id = token_info["account_id"]
    
    # 如果提供了 family_id，验证是否是家庭成员
    if family_id:
        from app.crud.family_member import get_family_member_by_family_and_account
        family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
        if not family_member:
            raise HTTPException(status_code=403, detail="无权访问此家庭")
    
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
    account_id = token_info["account_id"]
    
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
        # 1. 检查是否是家庭成员
        from app.crud.family_member import get_family_member_by_family_and_account
        family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
        if not family_member:
            raise HTTPException(status_code=403, detail="无权访问此家庭")
        
        # 2. 检查设备是否属于该家庭
        from app.crud.family_device import check_device_in_family
        if not await check_device_in_family(db, device_id, family_id):
            raise HTTPException(status_code=403, detail="设备不属于此家庭")
    
    # 更新设备名称
    old_name = device.name
    updated = await update_device(db, device_id, DeviceUpdate(name=payload.name))
    
    # 发送websocket消息通知设备名称修改
    try:
        role = token_info.get("role")
        account_id = token_info.get("account_id")
        if account_id is not None and device.sn:
            await websocket_tool.send_device_family_message(
                device_sn=device.sn,
                message_type="device.name.update",
                data={
                    "senderId": account_id,
                    "senderRole": role,
                    "title": "设备名称修改",
                    "message": f"设备 {old_name} 已更名为 {payload.name}",
                    "level": "normal",
                    "deviceId": device.id,
                    "deviceName": payload.name,
                    "oldName": old_name
                }
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送设备名称修改通知失败: {e}")
    
    return updated


@router.post("/bind-by-sn/", response_model=DeviceInDB)
async def bind_device_by_sn(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    payload: DeviceBindBySNRequest = Body(...),
    family_id: Optional[int] = Query(None, description="家庭ID，如果提供则将该设备添加到该家庭并发送消息；如果不提供则不发送消息")
):
    """通过序列号绑定设备到当前账号
    
    - sn: 设备序列号
    """

    account_id = token_info["account_id"]
    
    # 通过序列号查找设备
    device = await get_device_by_sn(db, payload.sn)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备状态是否允许绑定
    if device.account_id is not None:
        raise HTTPException(status_code=400, detail="设备已被其他账号绑定")
    
    if device.status not in ['unconfigured', 'configured', 'unbound']:
        raise HTTPException(status_code=400, detail="设备状态不允许激活，当前状态：" + device.status)
    
    # 绑定设备：绑定账号并更新状态
    device.account_id = account_id
    device.status = 'bound'  # 激活后状态变为已绑定
    
    await db.commit()
    await db.refresh(device)

    # 如果提供了 family_id，将设备添加到该家庭
    if family_id is not None:
        # 检查是否是家庭成员
        from app.crud.family_member import get_family_member_by_family_and_account
        family_member = await get_family_member_by_family_and_account(db, family_id, account_id)
        if not family_member:
            raise HTTPException(status_code=403, detail="无权访问此家庭")
        
        # 检查设备是否已在家庭中
        from app.crud.family_device import check_device_in_family, create_family_device
        if not await check_device_in_family(db, device.id, family_id):
            # 设备不在家庭中，添加到家庭
            family_device = await create_family_device(db, family_id, device.id)
            if not family_device:
                # 如果创建失败（可能已存在），不影响绑定流程
                print(f"设备 {device.id} 添加到家庭 {family_id} 失败或已存在")

    # 记录设备绑定操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.device_bind,
                description=f"绑定设备：{device.name}（SN: {device.sn}）",
                extra={
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_sn": device.sn,
                    "bound_account_id": account_id,
                    "device_status": device.status
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        # 记录操作失败不影响绑定流程
        print(f"记录设备绑定操作失败: {e}")

    # 发送websocket消息通知设备绑定
    try:
        role = token_info.get("role")
        if account_id is not None and family_id is not None:
            await websocket_tool.send_family_message_by_id(
                family_id=family_id,
                message_type="device.bind",
                data={
                    "senderId": account_id,
                    "senderRole": role,
                    "title": "设备绑定",
                    "message": f"设备 {device.name} 已绑定",
                    "level": "normal",
                    "deviceId": device.id,
                    "deviceName": device.name,
                    "deviceSn": device.sn
                }
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送设备绑定通知失败: {e}")

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

    account_id = token_info["account_id"]

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
    from app.crud.family_device import delete_all_family_devices_by_device
    removed_count = await delete_all_family_devices_by_device(db, device.id)
    if removed_count > 0:
        print(f"设备 {device_name} 已从 {removed_count} 个家庭中移除")
    
    # 通过统一更新逻辑处理解绑
    updated = await update_device(db, device.id, DeviceUpdate(account_id=None, status=DeviceStatus.unbound))
    
    # 记录设备解绑操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.device_unbind,
                description=f"解绑设备：{device_name}（SN: {sn}）",
                extra={
                    "device_id": device.id,
                    "device_name": device_name,
                    "device_sn": sn,
                    "unbound_account_id": account_id,
                    "device_status": updated.status if updated else "unbound"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        # 记录操作失败不影响解绑流程
        print(f"记录设备解绑操作失败: {e}")
    
    # 发送websocket消息通知设备解绑
    try:
        role = token_info.get("role")
        if account_id is not None:
            # 查询该用户的所有家庭，然后为每个家庭发送消息
            from app.crud.family import get_families_by_account
            families = await get_families_by_account(db, account_id)
            
            for family in families:
                if family.id is not None:
                    try:
                        await websocket_tool.send_family_message_by_id(
                            family_id=family.id,
                message_type="device.unbind",
                data={
                    "senderId": account_id,
                    "senderRole": role,
                    "title": "设备解绑",
                    "message": f"设备 {device_name} 已解绑",
                    "level": "normal",
                    "deviceId": device.id,
                    "deviceName": device_name,
                    "deviceSn": sn
                            }
            )
                    except Exception as e:
                        print(f"发送设备解绑消息失败 (family_id={family.id}): {e}")
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送设备解绑通知失败: {e}")
    
    return updated


 