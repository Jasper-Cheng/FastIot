from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.crud.device import (
    get_device,
    get_device_by_sn,
    get_devices_by_user,
    update_device,
)
from app.crud.user import get_user
from app.crud.user_operation_log import user_operation_log
from app.models.device import DeviceUpdate, DeviceInDB, DeviceStatus, DeviceNameUpdate, DeviceBindBySNRequest
from app.models.account import AccountRole
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token

router = APIRouter()


@router.get("/", response_model=List[DeviceInDB])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    token_info: dict = Depends(get_current_token),
):
    # 使用token中的user_id来获取设备
    user_id = token_info["user_id"]
    return await get_devices_by_user(db, user_id=user_id, skip=skip, limit=limit)


@router.patch("/{device_id}/name", response_model=DeviceInDB)
async def update_device_name(
    device_id: int, 
    payload: DeviceNameUpdate, 
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """修改设备名称
    
    - name: 新的设备名称
    """
    # 使用token中的user_id来获取设备
    user_id = token_info["user_id"]
    
    if token_info["role"] != AccountRole.owner:
        raise HTTPException(status_code=403, detail="无权修改设备名称")

    # 检查设备是否存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 验证设备是否属于当前用户
    if device.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权修改此设备")
    
    # 更新设备名称
    updated = await update_device(db, device_id, DeviceUpdate(name=payload.name))
    return updated


@router.post("/bind-by-sn/", response_model=DeviceInDB)
async def bind_device_by_sn(
    payload: DeviceBindBySNRequest,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """通过序列号绑定设备到当前用户
    
    - sn: 设备序列号
    - 只有owner角色才能绑定设备
    """

    user_id = token_info["user_id"]

    # 验证只有owner角色才能绑定设备
    if token_info["role"] != AccountRole.owner:
        raise HTTPException(status_code=403, detail="无权绑定设备")
    
    # 通过序列号查找设备
    device = await get_device_by_sn(db, payload.sn)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备状态是否允许绑定
    if device.user_id is not None:
        raise HTTPException(status_code=400, detail="设备已被其他用户绑定")
    
    if device.status not in ['unconfigured', 'configured', 'unbound']:
        raise HTTPException(status_code=400, detail="设备状态不允许激活，当前状态：" + device.status)
    
    # 绑定设备：绑定用户并更新状态
    device.user_id = user_id
    device.status = 'bound'  # 激活后状态变为已绑定
    
    await db.commit()
    await db.refresh(device)

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
                    "bound_user_id": user_id,
                    "device_status": device.status
                }
            ),
            account_id=token_info["account_id"]
        )
    except Exception as e:
        # 记录操作失败不影响绑定流程
        print(f"记录设备绑定操作失败: {e}")

    return device



@router.delete("/unbind-by-sn/{sn}", response_model=DeviceInDB)
async def unbind_device_by_sn(
    sn: str, 
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """通过序列号解绑设备，将设备从用户中移除
    
    - sn: 设备序列号
    """

    user_id = token_info["user_id"]
    
    if token_info["role"] != AccountRole.owner:
        raise HTTPException(status_code=403, detail="无权解绑设备")

    # 通过序列号查找设备
    device = await get_device_by_sn(db, sn)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 检查设备是否已绑定
    if device.user_id is None:
        raise HTTPException(status_code=400, detail="设备未绑定，无需解绑")
    
    # 验证设备是否属于当前用户
    if device.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权解绑此设备")
    
    # 记录解绑前的设备信息
    original_user_id = device.user_id
    device_name = device.name
    
    # 通过统一更新逻辑处理解绑与清理关联关系
    updated = await update_device(db, device.id, DeviceUpdate(user_id=None, status=DeviceStatus.unbound))
    
    # 记录设备解绑操作
    try:
        # 获取被解绑用户的账号信息
        unbound_user = await get_user(db, original_user_id)
        if unbound_user:
            await user_operation_log.create(
                db=db,
                obj_in=UserOperationLogCreate(
                    operation_type=OperationTypeEnum.device_unbind,
                    description=f"解绑设备：{device_name}（SN: {sn}）",
                    extra={
                        "device_id": device.id,
                        "device_name": device_name,
                        "device_sn": sn,
                        "unbound_user_id": original_user_id,
                        "device_status": updated.status if updated else "unbound"
                    }
                ),
                account_id=unbound_user.account_id
            )
    except Exception as e:
        # 记录操作失败不影响解绑流程
        print(f"记录设备解绑操作失败: {e}")
    
    return updated


 