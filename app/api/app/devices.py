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
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token
from app.db.session import get_db
from app.services.mqtt_service import mqtt_service

router = APIRouter()


@router.get("/", response_model=List[DeviceInDB])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    status: Optional[str] = Query(None, description="设备状态筛选 (online/offline)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
):
    """获取设备列表
    
    - 返回当前用户绑定的设备 + 所有家庭的设备
    - 支持按状态筛选
    - 支持分页
    """
    account_id = token_info["account_id"]
    
    skip = (page - 1) * page_size
    limit = page_size
    
    devices = await get_devices_by_account(
        db, 
        account_id=account_id, 
        skip=skip, 
        limit=limit
    )
    
    # 如果指定了状态，进行过滤
    if status:
        devices = [d for d in devices if d.status == status]
    
    return devices


@router.post("/bind-by-sn/", response_model=DeviceInDB)
async def bind_device_by_sn(
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
    payload: DeviceBindBySNRequest = Body(...),
):
    """通过序列号绑定设备到当前账号
    
    - sn: 设备序列号
    - name: 设备名称（可选，如果不提供则使用默认名称）
    """

    account_id = token_info["account_id"]
    
    # 通过序列号查找设备
    device = await get_device_by_sn(db, payload.sn)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备状态是否允许绑定
    if device.account_id is not None:
        raise HTTPException(status_code=409, detail="设备已被其他用户绑定")
    
    if device.status != 'unbound':
        raise HTTPException(status_code=400, detail="设备状态不允许绑定，当前状态：" + device.status)
    
    # 绑定设备：绑定账号并更新状态和名称
    device.account_id = account_id
    device.status = 'bound'
    if payload.name:
        device.name = payload.name
    
    await db.commit()
    await db.refresh(device)

    # 记录设备绑定操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.device_bind,
                description=f"通过App绑定设备：{device.name}（SN: {device.sn}）",
                extra={
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_sn": device.sn,
                    "bound_account_id": account_id,
                    "device_status": device.status,
                    "platform": "app"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        # 记录操作失败不影响绑定流程
        print(f"记录设备绑定操作失败: {e}")

    return device


@router.delete("/unbind-by-sn/{sn}")
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
                description=f"通过App解绑设备：{device_name}（SN: {sn}）",
                extra={
                    "device_id": device.id,
                    "device_name": device_name,
                    "device_sn": sn,
                    "unbound_account_id": account_id,
                    "device_status": updated.status if updated else "unbound",
                    "platform": "app"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        # 记录操作失败不影响解绑流程
        print(f"记录设备解绑操作失败: {e}")
    
    return {}


@router.patch("/{id}/name", response_model=DeviceInDB)
async def update_device_name(
    id: int, 
    payload: DeviceNameUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """修改设备名称
    
    - name: 新的设备名称
    - 只能修改自己绑定的设备或所在家庭内的设备
    """
    account_id = token_info["account_id"]
    
    # 检查设备是否存在
    device = await get_device(db, id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 权限检查：检查设备是否属于当前用户或用户所在的家庭
    if device.account_id != account_id:
        # 检查设备是否属于用户的某个家庭
        from app.crud.family_device import get_device_families
        from app.crud.family_member import get_family_member_by_family_and_account
        
        device_families = await get_device_families(db, id)
        has_permission = False
        
        for family in device_families:
            member = await get_family_member_by_family_and_account(db, family.id, account_id)
            if member:
                has_permission = True
                break
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="无权修改此设备")
    
    # 更新设备名称
    old_name = device.name
    updated = await update_device(db, id, DeviceUpdate(name=payload.name))
    if not updated:
        raise HTTPException(status_code=500, detail="更新设备失败")
    
    # 记录操作日志
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.device_name_update,
                description=f"通过App修改设备名称：{old_name} -> {payload.name}",
                extra={
                    "device_id": device.id,
                    "device_name": payload.name,
                    "old_name": old_name,
                    "device_sn": device.sn,
                    "platform": "app"
                }
            ),
            account_id=account_id
        )
    except Exception as e:
        print(f"记录设备名称修改操作日志失败: {e}")
    
    return DeviceInDB.model_validate(updated)

