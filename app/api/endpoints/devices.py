from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
from app.models.device import DeviceCreate, DeviceUpdate, DeviceInDB

router = APIRouter()


@router.get("/", response_model=List[DeviceInDB])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    unbound_only: bool = Query(False, description="只显示未绑定设备"),
):
    if unbound_only:
        # 查询未绑定设备
        from sqlalchemy import select
        from app.db.models.device import Device
        result = await db.execute(
            select(Device)
            .filter(Device.user_id.is_(None))
            .filter(Device.status.in_(['unconfigured', 'unbound']))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    elif user_id is not None:
        return await get_devices_by_user(db, user_id=user_id, skip=skip, limit=limit)
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


@router.delete("/{device_id}")
async def delete_device_item(device_id: int, db: AsyncSession = Depends(get_db)):
    ok = await delete_device(db, device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="设备不存在")
    return {"message": "删除成功"}


@router.post("/{device_id}/activate", response_model=DeviceInDB)
async def activate_device(device_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    """激活设备并绑定到用户
    
    - device_id: 设备ID
    - user_id: 要绑定的用户ID
    """
    # 验证设备存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 验证用户存在
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")
    
    # 检查设备状态是否允许激活
    if device.user_id is not None:
        raise HTTPException(status_code=400, detail="设备已被其他用户绑定")
    
    if device.status not in ['unconfigured', 'unbound']:
        raise HTTPException(status_code=400, detail="设备状态不允许激活，当前状态：" + device.status)
    
    # 激活设备：绑定用户并更新状态
    device.user_id = user_id
    device.status = 'bound'  # 激活后状态变为已绑定
    
    await db.commit()
    await db.refresh(device)
    
    return device


@router.post("/activate-by-sn", response_model=DeviceInDB)
async def activate_device_by_sn(sn: str, user_id: int, db: AsyncSession = Depends(get_db)):
    """通过序列号激活设备并绑定到用户
    
    - sn: 设备序列号
    - user_id: 要绑定的用户ID
    """
    # 通过序列号查找设备
    device = await get_device_by_sn(db, sn)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 验证用户存在
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")
    
    # 检查设备状态是否允许激活
    if device.user_id is not None:
        raise HTTPException(status_code=400, detail="设备已被其他用户绑定")
    
    if device.status not in ['unconfigured', 'unbound']:
        raise HTTPException(status_code=400, detail="设备状态不允许激活，当前状态：" + device.status)
    
    # 激活设备：绑定用户并更新状态
    device.user_id = user_id
    device.status = 'bound'  # 激活后状态变为已绑定
    
    await db.commit()
    await db.refresh(device)
    
    return device


