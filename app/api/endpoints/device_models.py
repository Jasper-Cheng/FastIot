from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.dependencies import get_db
from app.crud.device_model import (
    get_device_model, get_device_models, get_device_models_by_vendor,
    create_device_model, update_device_model, delete_device_model
)
from app.models.device_model import DeviceModel, DeviceModelCreate, DeviceModelUpdate
from app.models.user import User
from app.api.endpoints.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[DeviceModel], tags=["device-models"])
async def read_device_models(
    skip: int = 0,
    limit: int = 100,
    vendor: str = None,
    db: AsyncSession = Depends(get_db)
):
    """获取设备型号列表"""
    if vendor:
        models = await get_device_models_by_vendor(db, vendor=vendor, skip=skip, limit=limit)
    else:
        models = await get_device_models(db, skip=skip, limit=limit)
    return models

@router.post("/", response_model=DeviceModel, tags=["device-models"])
async def create_new_device_model(
    model: DeviceModelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建设备型号"""
    return await create_device_model(db=db, model=model)

@router.get("/{model_id}", response_model=DeviceModel, tags=["device-models"])
async def read_device_model(
    model_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取指定设备型号信息"""
    model = await get_device_model(db, model_id=model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    
    return model

@router.put("/{model_id}", response_model=DeviceModel, tags=["device-models"])
async def update_device_model_info(
    model_id: int,
    model: DeviceModelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新设备型号信息"""
    updated_model = await update_device_model(db=db, model_id=model_id, model=model)
    if updated_model is None:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    
    return updated_model

@router.delete("/{model_id}", tags=["device-models"])
async def delete_device_model_info(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除设备型号"""
    success = await delete_device_model(db=db, model_id=model_id)
    if not success:
        raise HTTPException(status_code=404, detail="设备型号不存在")
    
    return {"message": "设备型号删除成功"}
