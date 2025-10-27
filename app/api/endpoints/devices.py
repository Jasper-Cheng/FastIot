from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_db
from app.crud.device import (
    get_devices,
    get_device,
    get_device_by_sn,
    create_device,
    update_device,
    delete_device,
    get_devices_by_user,
)
from app.crud.user import get_user
from app.crud.device_model import get_device_model
from app.crud.user_operation_log import user_operation_log
from app.models.device import DeviceCreate, DeviceUpdate, DeviceInDB, DeviceStatus, DeviceBindRequest
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from pydantic import BaseModel

class DeviceNameUpdate(BaseModel):
    name: str

router = APIRouter()


@router.get("/", response_model=List[DeviceInDB])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    user_id: Optional[int] = Query(None),
):
    if user_id is not None:
        return await get_devices_by_user(db, user_id=user_id, skip=skip, limit=limit)
    else:
        return await get_devices(db, skip=skip, limit=limit)


@router.get("/{device_id}", response_model=DeviceInDB)
async def get_device_detail(device_id: int, db: AsyncSession = Depends(get_db)):
    d = await get_device(db, device_id)
    if not d:
        raise HTTPException(status_code=404, detail="设备不存在")
    return d


@router.post("/", response_model=DeviceInDB)
async def create_device_item(payload: DeviceCreate, db: AsyncSession = Depends(get_db)):
    """创建设备
    
    - user_id: 可选，不提供则创建设备为未绑定状态
    - model_id: 必填，设备型号ID
    - name: 必填，设备名称
    - sn: 必填，设备序列号（全局唯一）
    - status: 可选，默认为 unconfigured（未配网）
    """
    # 验证 user 存在（如果提供了 user_id）
    if payload.user_id is not None:
        owner = await get_user(db, payload.user_id)
        if not owner:
            raise HTTPException(status_code=400, detail="归属的用户不存在")
    # 验证 device_model 存在
    model = await get_device_model(db, payload.model_id)
    if not model:
        raise HTTPException(status_code=400, detail="设备型号不存在")
    # SN 唯一
    existed = await get_device_by_sn(db, payload.sn)
    if existed:
        raise HTTPException(status_code=400, detail="设备序列号已存在")
    return await create_device(db, payload)


@router.put("/{device_id}", response_model=DeviceInDB)
async def update_device_item(device_id: int, payload: DeviceUpdate, db: AsyncSession = Depends(get_db)):
    """更新设备信息
    
    - name: 可选，设备名称
    - sn: 可选，设备序列号（全局唯一）
    - status: 可选，设备状态
    - user_id: 可选，绑定用户ID（设为null可解绑设备）
    """
    # 如果修改了 user_id，需要验证用户存在
    if payload.user_id is not None:
        owner = await get_user(db, payload.user_id)
        if not owner:
            raise HTTPException(status_code=400, detail="归属的用户不存在")
    
    # 如果修改了 sn，需要校验唯一
    if payload.sn is not None:
        existed = await get_device_by_sn(db, payload.sn)
        if existed and existed.id != device_id:
            raise HTTPException(status_code=400, detail="设备序列号已存在")
    
    updated = await update_device(db, device_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="设备不存在")
    return updated


@router.patch("/{device_id}/name", response_model=DeviceInDB)
async def update_device_name(device_id: int, payload: DeviceNameUpdate, db: AsyncSession = Depends(get_db)):
    """修改设备名称
    
    - name: 新的设备名称
    """
    # 检查设备是否存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 更新设备名称
    updated = await update_device(db, device_id, DeviceUpdate(name=payload.name))
    return updated


@router.delete("/{device_id}")
async def delete_device_item(device_id: int, db: AsyncSession = Depends(get_db)):
    ok = await delete_device(db, device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="设备不存在")
    return {"message": "删除成功"}


@router.post("/bind-by-sn/", response_model=DeviceInDB)
async def bind_device_by_sn(
    payload: DeviceBindRequest,
    db: AsyncSession = Depends(get_db)
):
    """通过序列号绑定设备到用户
    
    - sn: 设备序列号
    - user_id: 要绑定的用户ID
    """
    # 通过序列号查找设备
    device = await get_device_by_sn(db, payload.sn)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 验证用户存在
    user = await get_user(db, payload.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")
    
    # 检查设备状态是否允许绑定
    if device.user_id is not None:
        raise HTTPException(status_code=400, detail="设备已被其他用户绑定")
    
    if device.status not in ['unconfigured', 'configured', 'unbound']:
        raise HTTPException(status_code=400, detail="设备状态不允许激活，当前状态：" + device.status)
    
    # 绑定设备：绑定用户并更新状态
    device.user_id = payload.user_id
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
                    "bound_user_id": payload.user_id,
                    "device_status": device.status
                }
            ),
            account_id=user.account_id
        )
    except Exception as e:
        # 记录操作失败不影响绑定流程
        print(f"记录设备绑定操作失败: {e}")

    return device



@router.delete("/unbind-by-sn/{sn}", response_model=DeviceInDB)
async def unbind_device_by_sn(sn: str, db: AsyncSession = Depends(get_db)):
    """通过序列号解绑设备，将设备从用户中移除
    
    - sn: 设备序列号
    """
    # 通过序列号查找设备
    device = await get_device_by_sn(db, sn)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查设备是否已绑定
    if device.user_id is None:
        raise HTTPException(status_code=400, detail="设备未绑定，无需解绑")
    
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


 