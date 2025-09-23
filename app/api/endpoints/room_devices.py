from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Union
from pydantic import BaseModel

from app.db.session import get_db
from app.api.dependencies import get_current_user_id
from app.crud.room_device import (
    get_room_devices_by_room,
    get_room_devices_by_device,
    get_room_device,
    create_room_device,
    update_room_device,
    delete_room_device,
    batch_update_room_devices,
)
from app.crud.room import get_room
from app.crud.device import get_device
from app.models.room_device import (
    RoomDeviceCreate, 
    RoomDeviceUpdate, 
    RoomDeviceInDB,
    RoomDeviceBatchSortRequest,
    RoomDeviceBatchSortResponse
)
router = APIRouter()




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


@router.put("/batch-sort", response_model=RoomDeviceBatchSortResponse)
async def batch_update_sort(
    payload: RoomDeviceBatchSortRequest, 
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """批量更新房间设备关联排序
    
    根据用户传来的列表更新room_device表，其中device_id必须要是当前用户所拥有的设备id，
    room_id必须是当前用户所拥有的房间id。
    
    如果之前存在传入的列表不存在则删除，
    如果之前不存在传入的列表存在则添加。
    """
    try:
        # 调用CRUD函数进行批量更新
        updated_room_devices = await batch_update_room_devices(
            db=db,
            room_id=payload.room_id,
            devices=payload.devices,
            user_id=current_user_id
        )
        
        return RoomDeviceBatchSortResponse(
            success=True,
            message="批量更新成功",
            data=updated_room_devices
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量更新失败: {str(e)}")


@router.delete("/{id}")
async def delete_room_device_item(id: int, db: AsyncSession = Depends(get_db)):
    ok = await delete_room_device(db, id)
    if not ok:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"message": "删除成功"}



