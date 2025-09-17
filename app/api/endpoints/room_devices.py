from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel

from app.db.session import get_db
from app.crud.room_device import (
    get_room_devices_by_room,
    get_room_devices_by_device,
    get_room_device,
    create_room_device,
    update_room_device,
    delete_room_device,
)
from app.crud.room import get_room
from app.crud.device import get_device
from app.models.room_device import RoomDeviceCreate, RoomDeviceUpdate, RoomDeviceInDB
router = APIRouter()


class RoomDeviceOrderItem(BaseModel):
    device_id: int
    sort_order: int


class RoomDeviceBatchSort(BaseModel):
    room_id: int
    orders: List[RoomDeviceOrderItem]


@router.get("/by-room/{room_id}", response_model=List[RoomDeviceInDB])
async def list_by_room(room_id: int, db: AsyncSession = Depends(get_db)):
    # 验证房间存在
    room = await get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    return await get_room_devices_by_room(db, room_id)


@router.get("/by-device/{device_id}", response_model=List[RoomDeviceInDB])
async def list_by_device(device_id: int, db: AsyncSession = Depends(get_db)):
    # 验证设备存在
    dev = await get_device(db, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    return await get_room_devices_by_device(db, device_id)


@router.post("/", response_model=RoomDeviceInDB)
async def create_room_device_item(payload: RoomDeviceCreate, db: AsyncSession = Depends(get_db)):
    # 验证房间和设备存在
    room = await get_room(db, payload.room_id)
    if not room:
        raise HTTPException(status_code=400, detail="房间不存在")
    dev = await get_device(db, payload.device_id)
    if not dev:
        raise HTTPException(status_code=400, detail="设备不存在")
    return await create_room_device(db, payload)


@router.put("/{id}", response_model=RoomDeviceInDB)
async def update_room_device_item(id: int, payload: RoomDeviceUpdate, db: AsyncSession = Depends(get_db)):
    updated = await update_room_device(db, id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="记录不存在")
    return updated


@router.delete("/{id}")
async def delete_room_device_item(id: int, db: AsyncSession = Depends(get_db)):
    ok = await delete_room_device(db, id)
    if not ok:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"message": "删除成功"}


@router.put("/batch-sort", response_model=List[RoomDeviceInDB])
async def batch_update_sort(payload: RoomDeviceBatchSort, db: AsyncSession = Depends(get_db)):
    # 验证房间存在
    room = await get_room(db, payload.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    if not payload.orders:
        return await get_room_devices_by_room(db, payload.room_id)

    # 读取并校验所有 device_id 都属于该房间
    device_ids = [item.device_id for item in payload.orders]
    from sqlalchemy import select
    from app.db.models.room_device import RoomDevice as RoomDeviceORM

    result = await db.execute(
        select(RoomDeviceORM).where(
            RoomDeviceORM.room_id == payload.room_id,
            RoomDeviceORM.device_id.in_(device_ids)
        )
    )
    room_devices_by_device = {rd.device_id: rd for rd in result.scalars().all()}

    if len(room_devices_by_device) != len(device_ids):
        raise HTTPException(status_code=400, detail="存在不属于该房间或不存在的房间设备记录")

    for item in payload.orders:
        rd = room_devices_by_device[item.device_id]
        rd.sort_order = item.sort_order

    await db.commit()

    # 返回更新后的房间设备（按排序）
    return await get_room_devices_by_room(db, payload.room_id)


