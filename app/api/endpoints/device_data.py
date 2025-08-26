from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db
from app.crud.device_data import get_device_data_list, get_device_data_by_device, get_device_data
from app.models.device_data import DeviceData
from typing import List

router = APIRouter()

@router.get("/", response_model=List[DeviceData], tags=["device-data"])
async def read_device_data(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """获取设备数据列表"""
    data = await get_device_data_list(db, skip=skip, limit=limit)
    return data

@router.get("/device/{device_id}", response_model=List[DeviceData], tags=["device-data"])
async def read_device_data_by_device(device_id: int, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """根据设备ID获取设备数据"""
    data = await get_device_data_by_device(db, device_id=device_id, skip=skip, limit=limit)
    return data

@router.get("/{data_id}", response_model=DeviceData, tags=["device-data"])
async def read_specific_device_data(data_id: int, db: AsyncSession = Depends(get_db)):
    """根据ID获取特定的设备数据"""
    data = await get_device_data(db, data_id=data_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Device data not found")
    return data