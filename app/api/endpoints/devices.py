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
):
    if user_id is not None:
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


