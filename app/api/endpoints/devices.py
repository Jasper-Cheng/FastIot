from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.api.endpoints.auth import get_current_user
from app.crud.device import (
    get_device, create_device, update_device, delete_device,
    get_devices_by_owner_with_count, get_devices_by_owner
)
from app.models.device import (
    Device, DeviceCreate, DeviceUpdate, DeviceControl, DeviceControlResponse,
    DeviceListResponse, DeviceStatusResponse
)
from app.models.user import User
from app.services.redis_service import redis_service
from app.services.mqtt_client import mqtt_service
from datetime import datetime, timedelta
from app.crud.device_data import get_latest_device_data

router = APIRouter()

@router.get("/", response_model=DeviceListResponse, tags=["devices"])
async def read_devices(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的设备列表（包含在线状态）"""
    # 优先从 Redis owner->devices 索引与 device_info 组装返回；未命中时再回退数据库
    owner_device_ids = await redis_service.get_owner_device_ids(current_user.id)
    devices = []
    total = 0
    if owner_device_ids:
        total = len(owner_device_ids)
        # 分页切片（简单基于 id 列表顺序；如需特定排序可在缓存中维护）
        page_ids = owner_device_ids[skip:skip+limit]
        for did in page_ids:
            info = await redis_service.get_device_info(did)
            if not info:
                # 回退到 DB 拿一条补齐缓存
                db_device = await get_device(db, device_id=did)
                if not db_device or db_device.owner_id != current_user.id:
                    continue
                info = {
                    "id": db_device.id,
                    "name": db_device.name,
                    "serial_number": db_device.serial_number,
                    "owner_id": db_device.owner_id,
                    "status": db_device.status,
                    "last_active": db_device.last_active.isoformat() if db_device.last_active else None,
                    "created_at": db_device.created_at.isoformat() if db_device.created_at else None,
                }
                await redis_service.set_device_info(did, info)
            # 命中缓存时直接构造 Pydantic Device 返回，避免 DB ORM 依赖
            from app.models.device import Device as DeviceModel, DeviceStatus
            last_active_dt = None
            try:
                if info.get("last_active"):
                    from datetime import datetime
                    last_active_dt = datetime.fromisoformat(info["last_active"])  # noqa
            except Exception:
                last_active_dt = None
            device_obj = DeviceModel(
                id=info.get("id", did),
                name=info.get("name", ""),
                serial_number=info.get("serial_number", ""),
                owner_id=info.get("owner_id", current_user.id),
                status=info.get("status", "offline"),
                last_active=last_active_dt,
                created_at=info.get("created_at")
            )
            devices.append(device_obj)
    else:
        # 缓存未命中，读取数据库，回填 owner 索引与 info 缓存
        devices, total = await get_devices_by_owner_with_count(db, owner_id=current_user.id, skip=skip, limit=limit)
        for d in devices:
            await redis_service.add_device_to_owner(current_user.id, d.id)
            await redis_service.set_device_info(d.id, {
                "id": d.id,
                "name": d.name,
                "serial_number": d.serial_number,
                "owner_id": d.owner_id,
                "status": d.status,
                "last_active": d.last_active.isoformat() if d.last_active else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            })
    
    # 获取在线设备数量（Redis 优先；缺失时用 last_active 推断并回填缓存）
    online_count = 0
    for device in devices:
        # 尝试读取设备信息缓存，命中则覆盖返回字段，减少后续请求 DB 压力
        cached_info = await redis_service.get_device_info(device.id)
        if cached_info:
            # 仅更新非敏感可覆写字段
            device.name = cached_info.get("name", device.name)
            device.serial_number = cached_info.get("serial_number", device.serial_number)
            device.last_active = cached_info.get("last_active", device.last_active)
            device.created_at = cached_info.get("created_at", device.created_at)

        is_online = await redis_service.is_device_online(device.id)
        if not is_online:
            # fallback: 最近 5 分钟活跃视为在线
            if device.last_active:
                if device.last_active >= datetime.utcnow() - timedelta(seconds=300):
                    is_online = True
                    # 回填缓存
                    await redis_service.set_device_online(device.id, True)
        # 用缓存优先结果覆盖返回中的设备状态
        device.status = 'online' if is_online else 'offline'
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
    # 先尝试设备信息缓存，未命中再查数据库
    cached_info = await redis_service.get_device_info(device_id)
    if cached_info and cached_info.get("owner_id") is not None:
        # 直接基于缓存鉴权
        if cached_info["owner_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this device")
        # 使用缓存直接构造 Pydantic Device 返回
        from app.models.device import Device as DeviceModel
        last_active_dt = None
        try:
            if cached_info.get("last_active"):
                from datetime import datetime
                last_active_dt = datetime.fromisoformat(cached_info["last_active"])  # noqa
        except Exception:
            last_active_dt = None
        device = DeviceModel(
            id=cached_info.get("id", device_id),
            name=cached_info.get("name", ""),
            serial_number=cached_info.get("serial_number", ""),
            owner_id=cached_info.get("owner_id", current_user.id),
            status=cached_info.get("status", "offline"),
            last_active=last_active_dt,
            created_at=cached_info.get("created_at")
        )
    else:
        # 缓存缺失 owner_id 或整条未命中，回退 DB 获取并回填缓存
        device = await get_device(db, device_id=device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 检查设备所有权
    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this device")
    
    # 返回前使用缓存优先的在线状态覆写
    is_online = await redis_service.is_device_online(device_id)
    if not is_online and device.last_active:
        if device.last_active >= datetime.utcnow() - timedelta(seconds=300):
            is_online = True
            await redis_service.set_device_online(device_id, True)
    device.status = 'online' if is_online else 'offline'
    # 缓存回填（把最新 DB 的信息写回缓存，后续读请求直接命中 Redis）
    await redis_service.set_device_info(device_id, {
        "id": getattr(device, 'id', device_id),
        "name": getattr(device, 'name', None),
        "serial_number": getattr(device, 'serial_number', None),
        "owner_id": getattr(device, 'owner_id', current_user.id),
        "status": getattr(device, 'status', 'offline'),
        "last_active": (device.last_active.isoformat() if getattr(device, 'last_active', None) else None),
        "created_at": (device.created_at.isoformat() if getattr(device, 'created_at', None) else None),
    })
    return device

@router.get("/{device_id}/status", response_model=DeviceStatusResponse, tags=["devices"])
async def get_device_status(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备状态（缓存优先，未命中回退 DB 并回填缓存）"""
    # 先以缓存 info 做鉴权，未命中再查 DB
    cached_info = await redis_service.get_device_info(device_id)
    if cached_info and cached_info.get("owner_id") is not None:
        if cached_info["owner_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this device")
        last_active_dt = None
        try:
            if cached_info.get("last_active"):
                last_active_dt = datetime.fromisoformat(cached_info["last_active"])  # noqa
        except Exception:
            last_active_dt = None
        device_owner_id = cached_info["owner_id"]
        device_last_active = last_active_dt
    else:
        db_device = await get_device(db, device_id=device_id)
        if db_device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        if db_device.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this device")
        device_owner_id = db_device.owner_id
        device_last_active = db_device.last_active
        # 回填 info 缓存（只填必要字段避免频繁 DB）
        await redis_service.set_device_info(device_id, {
            "id": db_device.id,
            "name": db_device.name,
            "serial_number": db_device.serial_number,
            "owner_id": db_device.owner_id,
            "status": db_device.status,
            "last_active": db_device.last_active.isoformat() if db_device.last_active else None,
            "created_at": db_device.created_at.isoformat() if db_device.created_at else None,
        })

    # 在线状态与状态负载：Redis 优先
    is_online = await redis_service.is_device_online(device_id)
    status_data = await redis_service.get_device_status(device_id)

    # Fallback：未命中时用 DB 最新设备数据与 last_active 推断
    if status_data is None:
        latest = await get_latest_device_data(db, device_id)
        if latest and latest.data:
            status_data = latest.data
            await redis_service.set_device_status(device_id, status_data)
    if not is_online and device_last_active:
        if device_last_active >= datetime.utcnow() - timedelta(seconds=300):
            is_online = True
            await redis_service.set_device_online(device_id, True)

    return DeviceStatusResponse(
        device_id=device_id,
        online=is_online,
        status=status_data,
        last_active=device_last_active
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
    created = await create_device(db=db, device=device)
    # 写 DB 后，立即写入 Redis 设备信息缓存
    await redis_service.set_device_info(created.id, {
        "id": created.id,
        "name": created.name,
        "serial_number": created.serial_number,
        "owner_id": created.owner_id,
        "status": created.status,
        "last_active": created.last_active.isoformat() if created.last_active else None,
        "created_at": created.created_at.isoformat() if created.created_at else None,
    })
    # 同步 owner 索引
    await redis_service.add_device_to_owner(created.owner_id, created.id)
    return created

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
    # 更新 DB 后，同步更新 Redis 设备信息缓存
    if updated_device:
        await redis_service.set_device_info(updated_device.id, {
            "id": updated_device.id,
            "name": updated_device.name,
            "serial_number": updated_device.serial_number,
            "owner_id": updated_device.owner_id,
            "status": updated_device.status,
            "last_active": updated_device.last_active.isoformat() if updated_device.last_active else None,
            "created_at": updated_device.created_at.isoformat() if updated_device.created_at else None,
        })
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
    if success:
        # 删除 DB 后，清理 Redis 设备信息缓存
        await redis_service.delete_device_info(device_id)
        await redis_service.remove_device_from_owner(current_user.id, device_id)
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

 