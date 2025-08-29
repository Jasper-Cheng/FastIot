from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.api.endpoints.auth import get_current_user_claims, CurrentUserClaims
from app.crud.device import (
    get_device, create_device, update_device, delete_device,
    get_devices_by_owner_with_count
)
from app.models.device import (
    Device, DeviceCreate, DeviceUpdate, DeviceListResponse, DeviceCreateInput
)
from app.models.device_data import DeviceDataCreate
from app.crud.device_data import create_device_data
from app.services.redis_service import redis_service

router = APIRouter()

@router.get("/", response_model=DeviceListResponse, tags=["devices"])
async def read_devices(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserClaims = Depends(get_current_user_claims)
):
    """获取当前用户的设备列表（包含在线状态）"""
    owner_device_ids = await redis_service.get_owner_device_ids(current_user.id)
    devices = []
    online_count = 0

    if owner_device_ids:
        page_ids = owner_device_ids[skip:skip+limit]
        for did in page_ids:
            info = await redis_service.get_device_info(did)
            if not info:
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

            from app.models.device import Device as DeviceModel

            device_obj = DeviceModel(
                id=info.get("id", did),
                name=info.get("name", ""),
                serial_number=info.get("serial_number", ""),
                owner_id=info.get("owner_id", current_user.id),
                status=info.get("status", "offline"),
                last_active=info.get("last_active", datetime.now()),
                created_at=info.get("created_at")
            )
            devices.append(device_obj)

            if device_obj.status == 'online':
                online_count += 1
    else:
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

            if d.status == 'online':
                online_count += 1

    return DeviceListResponse(
        devices=devices,
        total=len(devices),
        online_count=online_count
    )

@router.get("/{device_id}", response_model=Device, tags=["devices"])
async def read_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserClaims = Depends(get_current_user_claims)
):
    """根据ID获取设备"""
    cached_info = await redis_service.get_device_info(device_id)
    if cached_info and cached_info.get("owner_id") is not None:
        if cached_info["owner_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this device")
        from app.models.device import Device as DeviceModel
        device = DeviceModel(
            id=cached_info.get("id", device_id),
            name=cached_info.get("name", ""),
            serial_number=cached_info.get("serial_number", ""),
            owner_id=cached_info.get("owner_id", current_user.id),
            status=cached_info.get("status", "offline"),
            last_active=cached_info.get("last_active", datetime.now()),
            created_at=cached_info.get("created_at")
        )
    else:
        device = await get_device(db, device_id=device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        if device.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this device")
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

@router.post("/", response_model=Device, status_code=status.HTTP_201_CREATED, tags=["devices"])
async def create_new_device(
    device_input: DeviceCreateInput,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserClaims = Depends(get_current_user_claims)
):
    """创建新设备（owner_id 不由前端传入；需要 data JSON）"""
    device = DeviceCreate(
        name=device_input.name,
        serial_number=device_input.serial_number,
        device_type=device_input.device_type,
        owner_id=current_user.id,
    )
    created = await create_device(db=db, device=device)

    # 创建初始设备数据记录
    await create_device_data(db=db, device_data=DeviceDataCreate(device_id=created.id, data=device_input.data))
    await redis_service.set_device_info(created.id, {
        "id": created.id,
        "name": created.name,
        "serial_number": created.serial_number,
        "owner_id": created.owner_id,
        "status": created.status,
        "last_active": created.last_active.isoformat() if created.last_active else None,
        "created_at": created.created_at.isoformat() if created.created_at else None,
    })
    await redis_service.add_device_to_owner(created.owner_id, created.id)
    return created

@router.put("/{device_id}", response_model=Device, tags=["devices"])
async def update_existing_device(
    device_id: int,
    device: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserClaims = Depends(get_current_user_claims)
):
    """更新设备信息"""
    existing_device = await get_device(db, device_id=device_id)
    if existing_device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    if existing_device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this device")

    updated_device = await update_device(db, device_id=device_id, device=device)
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
        # 如请求包含 data，追加写入 DeviceData
        if device.data is not None:
            await create_device_data(db=db, device_data=DeviceDataCreate(device_id=updated_device.id, data=device.data))
    return updated_device

@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["devices"])
async def delete_existing_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserClaims = Depends(get_current_user_claims)
):
    """删除设备"""
    existing_device = await get_device(db, device_id=device_id)
    if existing_device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    if existing_device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this device")

    success = await delete_device(db, device_id=device_id)
    if success:
        await redis_service.delete_device_info(device_id)
        await redis_service.remove_device_from_owner(current_user.id, device_id)
    return {"message": "Device deleted successfully"}

@router.post("/cache/clear", tags=["devices"])
async def clear_device_cache(
    current_user: CurrentUserClaims = Depends(get_current_user_claims)
):
    """清除设备缓存（需要管理员权限）"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can clear cache")

    success = await redis_service.clear_device_cache()
    if success:
        return {"message": "Device cache cleared successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear device cache")

@router.post("/cache/clear-all", tags=["devices"])
async def clear_all_cache(
    current_user: CurrentUserClaims = Depends(get_current_user_claims)
):
    """清除所有Redis缓存（需要管理员权限）"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can clear cache")

    success = await redis_service.clear_all_cache()
    if success:
        return {"message": "All cache cleared successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear all cache")

 