from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.room_device import (
    get_room_devices_by_room,
    batch_update_room_devices,
)
from app.crud.room import get_room
from app.crud.user_operation_log import user_operation_log
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.models.room_device import (
    RoomDeviceInDB,
    RoomDeviceBatchSortRequest,
    RoomDeviceBatchSortResponse
)
from app.models.account import AccountRole
from app.services.websocket_tool import websocket_tool
router = APIRouter()

@router.get("/by-room/{room_id}", response_model=List[RoomDeviceInDB])
async def list_by_room(room_id: int, db: AsyncSession = Depends(get_db), token_info: dict = Depends(get_current_token)):
    # 验证房间存在
    room = await get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    if room.user_id != token_info["user_id"]:
        raise HTTPException(status_code=403, detail="无权查看此房间的设备关联")
    return await get_room_devices_by_room(db, room_id)


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

    user_id = token_info["user_id"]
    
    try:
        # 调用CRUD函数进行批量更新
        updated_room_devices = await batch_update_room_devices(
            db=db,
            room_id=payload.room_id,
            devices=payload.devices,
            user_id=user_id
        )
        
        # 获取房间和设备信息（用于记录操作和发送消息）
        device_count = len(updated_room_devices)
        device_names = [device.device_name if hasattr(device, 'device_name') else f"设备ID:{device.device_id}" for device in updated_room_devices]
        room_name = updated_room_devices[0].room_name if updated_room_devices and hasattr(updated_room_devices[0], 'room_name') else f"房间ID:{payload.room_id}"
        
        # 记录设备排序操作
        try:
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
                        "user_id": user_id
                    }
                ),
                account_id=token_info["account_id"]
            )
        except Exception as e:
            # 记录操作失败不影响排序流程
            print(f"记录设备排序操作失败: {e}")
        
        # 发送family消息通知设备排序更新
        try:
            role = token_info.get("role")
            real_id = token_info.get("id")
            if role and real_id is not None:
                client_id = f"{role}_{real_id}"
                
                # 将 updated_room_devices 转换为字典列表
                room_devices_data = []
                for rd in updated_room_devices:
                    room_devices_data.append({
                        "id": rd.id,
                        "roomId": rd.room_id,
                        "deviceId": rd.device_id,
                        "sortOrder": rd.sort_order
                    })
                
                await websocket_tool.send_family_message(
                    client_id=client_id,
                    message_type="room.device.sort",
                    data={
                        "senderId": real_id,
                        "senderRole": role,
                        "title": "设备排序更新",
                        "message": f"已调整房间 {room_name} 内的设备排序（共{device_count}个设备）",
                        "level": "normal",
                        "roomDevicesData": room_devices_data
                    }
                )
        except Exception as e:
            # 发送消息失败不影响业务流程
            print(f"发送设备排序更新通知失败: {e}")
        
        return RoomDeviceBatchSortResponse(
            success=True,
            message="批量更新成功",
            data=updated_room_devices
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量更新失败: {str(e)}")


