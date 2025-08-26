from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db
from app.crud.device import get_devices, get_device, create_device, update_device, delete_device, get_devices_by_owner
from app.models.device import Device, DeviceCreate, DeviceUpdate
from app.models.user import User
from app.api.endpoints.auth import get_current_user
from typing import List

router = APIRouter()

@router.get("/", response_model=List[Device], tags=["devices"])
async def read_devices(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的设备列表"""
    devices = await get_devices_by_owner(db, owner_id=current_user.id, skip=skip, limit=limit)
    return devices

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