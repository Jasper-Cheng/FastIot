from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db
from app.crud.device_data import get_device_data_list, get_device_data_by_device, get_device_data
from app.crud.device import get_device
from app.models.device_data import DeviceData
from app.models.user import User
from app.api.endpoints.auth import get_current_user
from typing import List

router = APIRouter()

@router.get("/", response_model=List[DeviceData], tags=["device-data"])
async def read_device_data(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的设备数据列表"""
    # 这里可以添加更复杂的逻辑来获取用户所有设备的数据
    data = await get_device_data_list(db, skip=skip, limit=limit)
    return data

@router.get("/device/{device_id}", response_model=List[DeviceData], tags=["device-data"])
async def read_device_data_by_device(
    device_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """根据设备ID获取设备数据"""
    # 检查设备所有权
    device = await get_device(db, device_id=device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this device's data")
    
    data = await get_device_data_by_device(db, device_id=device_id, skip=skip, limit=limit)
    return data
