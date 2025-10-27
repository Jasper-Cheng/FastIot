from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.room_device import (
    get_room_devices_by_room,
    get_room_devices_by_device,
    create_room_device,
    delete_room_device,
    batch_update_room_devices,
)
from app.crud.device import get_device
from app.crud.room import get_room
from app.crud.user_operation_log import user_operation_log
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.models.room_device import (
    RoomDeviceCreate, 
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
    token_info: dict = Depends(get_current_token)
):
    """批量更新房间设备关联排序
    
    根据用户传来的列表更新room_device表，其中device_id必须要是当前用户所拥有的设备id，
    room_id必须是当前用户所拥有的房间id。
    
    如果之前存在传入的列表不存在则删除，
    如果之前不存在传入的列表存在则添加。
    """
    # 获取用户ID
    from app.crud.member import get_member
    if token_info["role"] == "member":
        # 对于成员，我们需要获取其所属的用户ID
        member = await get_member(db, token_info["id"])
        current_user_id = member.user_id
    else:
        # owner 和 admin 直接返回用户ID
        current_user_id = token_info["id"]
    
    try:
        # 调用CRUD函数进行批量更新
        updated_room_devices = await batch_update_room_devices(
            db=db,
            room_id=payload.room_id,
            devices=payload.devices,
            user_id=current_user_id
        )
        
        # 记录设备排序操作
        try:
            device_count = len(updated_room_devices)
            device_names = [device.device_name if hasattr(device, 'device_name') else f"设备ID:{device.device_id}" for device in updated_room_devices]
            room_name = updated_room_devices[0].room_name if updated_room_devices and hasattr(updated_room_devices[0], 'room_name') else f"房间ID:{payload.room_id}"
            
            await user_operation_log.create(
                db=db,
                obj_in=UserOperationLogCreate(
                    operation_type=OperationTypeEnum.room_device_sort,
                    description=f"调整房间内设备排序：{room_name}（共{device_count}个设备）",
                    extra={
                        "room_id": payload.room_id,
                        "room_name": room_name,
                        "device_count": device_count,
                        "device_names": device_names,
                        "user_id": current_user_id
                    }
                ),
                account_id=token_info["account_id"]
            )
        except Exception as e:
            # 记录操作失败不影响排序流程
            print(f"记录设备排序操作失败: {e}")
        
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



