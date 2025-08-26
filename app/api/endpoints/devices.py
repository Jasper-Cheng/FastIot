from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db
from app.crud.device import get_devices, get_device, create_device, update_device, delete_device
from app.models.device import Device, DeviceCreate, DeviceUpdate
from typing import List

router = APIRouter()

@router.get("/", response_model=List[Device], tags=["devices"])
async def read_devices(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """获取设备列表"""
    devices = await get_devices(db, skip=skip, limit=limit)
    return devices

@router.get("/{device_id}", response_model=Device, tags=["devices"])
async def read_device(device_id: int, db: AsyncSession = Depends(get_db)):
    """根据ID获取设备"""
    device = await get_device(db, device_id=device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.post("/", response_model=Device, status_code=status.HTTP_201_CREATED, tags=["devices"])
async def create_new_device(device: DeviceCreate, db: AsyncSession = Depends(get_db)):
    """创建新设备"""
    return await create_device(db=db, device=device)

@router.put("/{device_id}", response_model=Device, tags=["devices"])
async def update_existing_device(device_id: int, device: DeviceUpdate, db: AsyncSession = Depends(get_db)):
    """更新设备信息"""
    updated_device = await update_device(db, device_id=device_id, device=device)
    if updated_device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return updated_device

@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["devices"])
async def delete_existing_device(device_id: int, db: AsyncSession = Depends(get_db)):
    """删除设备"""
    success = await delete_device(db, device_id=device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"message": "Device deleted successfully"}