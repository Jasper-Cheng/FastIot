from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.api.endpoints.auth import get_current_user
from app.crud.device import (
    get_device, create_device, update_device, delete_device,
    get_devices_by_owner_with_count, update_device_last_active
)
from app.models.device import (
    Device, DeviceCreate, DeviceUpdate, DeviceControl, DeviceControlResponse,
    DeviceStatusResponse, DeviceListResponse
)
from app.models.user import User
from app.services.redis_service import redis_service
from app.services.mqtt_client import mqtt_service

router = APIRouter()

@router.get("/", response_model=DeviceListResponse, tags=["devices"])
async def read_devices(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的设备列表（包含在线状态）"""
    devices, total = await get_devices_by_owner_with_count(
        db, owner_id=current_user.id, skip=skip, limit=limit
    )
    
    # 获取在线设备数量
    online_count = 0
    for device in devices:
        is_online = await redis_service.is_device_online(device.id)
        if is_online:
            online_count += 1
    
    return DeviceListResponse(
        devices=devices,
        total=total,
        online_count=online_count
    )

@router.get("/{device_id}", response_model=Device, tags=["devices"])
async def read_device(
    device_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """根据ID获取设备"""
    device = await get_device(db, device_id=device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 检查设备所有权
    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this device")
    
    return device

@router.get("/{device_id}/status", response_model=DeviceStatusResponse, tags=["devices"])
async def get_device_status(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备状态"""
    device = await get_device(db, device_id=device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 检查设备所有权
    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this device")
    
    # 检查在线状态
    is_online = await redis_service.is_device_online(device_id)
    
    # 获取设备状态数据
    status_data = await redis_service.get_device_status(device_id)
    
    return DeviceStatusResponse(
        device_id=device_id,
        online=is_online,
        status=status_data,
        last_active=device.last_active
    )

@router.post("/", response_model=Device, status_code=status.HTTP_201_CREATED, tags=["devices"])
async def create_new_device(
    device: DeviceCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新设备"""
    # 确保设备属于当前用户
    device.owner_id = current_user.id
    return await create_device(db=db, device=device)

@router.put("/{device_id}", response_model=Device, tags=["devices"])
async def update_existing_device(
    device_id: int, 
    device: DeviceUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新设备信息"""
    # 检查设备所有权
    existing_device = await get_device(db, device_id=device_id)
    if existing_device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if existing_device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this device")
    
    updated_device = await update_device(db, device_id=device_id, device=device)
    return updated_device

@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["devices"])
async def delete_existing_device(
    device_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除设备"""
    # 检查设备所有权
    existing_device = await get_device(db, device_id=device_id)
    if existing_device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if existing_device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this device")
    
    success = await delete_device(db, device_id=device_id)
    return {"message": "Device deleted successfully"}

# 设备控制接口
@router.post("/{device_id}/control", response_model=DeviceControlResponse, tags=["devices"])
async def control_device(
    device_id: int,
    control: DeviceControl,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """控制设备"""
    # 检查设备是否存在
    device = await get_device(db, device_id=device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 检查设备所有权
    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to control this device")
    
    # 检查设备是否在线
    is_online = await redis_service.is_device_online(device_id)
    if not is_online:
        return DeviceControlResponse(
            success=False,
            message="Device is offline",
            data=None
        )
    
    # 设置控制命令到Redis
    command_data = {
        "command": control.command,
        "parameters": control.parameters,
        "timestamp": control.timestamp.isoformat() if control.timestamp else None,
        "user_id": current_user.id
    }
    
    success = await redis_service.set_device_control(device_id, command_data)
    # 通过MQTT下发控制命令
    mqtt_service.publish_json(
        topic=f"devices/{device_id}/control",
        payload={
            "device_id": device_id,
            **command_data,
        },
        qos=1,
        retain=False,
    )
    
    if success:
        return DeviceControlResponse(
            success=True,
            message="Control command sent successfully",
            data=command_data
        )
    else:
        return DeviceControlResponse(
            success=False,
            message="Failed to send control command",
            data=None
        )

@router.post("/{device_id}/heartbeat", tags=["devices"])
async def device_heartbeat(
    device_id: int,
    status_data: dict = None,
    db: AsyncSession = Depends(get_db)
):
    """设备心跳接口（设备端调用）"""
    # WebSocket 推送改为 MQTT 推送
    
    # 更新设备在线状态
    await redis_service.set_device_online(device_id)
    
    # 更新最后活跃时间
    await update_device_last_active(db, device_id)
    
    # 如果有状态数据，保存到Redis
    if status_data:
        await redis_service.set_device_status(device_id, status_data)
        # 推送状态到 MQTT
        mqtt_service.publish_json(
            topic=f"devices/{device_id}/status",
            payload={
                "device_id": device_id,
                "status": status_data,
            },
            qos=0,
            retain=False,
        )
    
    # 推送在线状态到 MQTT
    mqtt_service.publish_json(
        topic=f"devices/{device_id}/online",
        payload={"device_id": device_id, "online": True},
        qos=0,
        retain=False,
    )
    
    # 检查是否有待执行的控制命令
    control_command = await redis_service.get_device_control(device_id)
    
    return {
        "success": True,
        "message": "Heartbeat received",
        "control_command": control_command
    }