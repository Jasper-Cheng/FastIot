from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.api.dependencies import get_db
from app.crud.device_param import (
    get_device_param, get_device_param_by_device, create_device_param,
    update_device_param, update_or_create_device_param
)
from app.crud.device import get_device
from app.models.device_param import DeviceParam, DeviceParamCreate, DeviceParamUpdate
from app.models.user import User
from app.api.endpoints.auth import get_current_user

router = APIRouter()

@router.get("/device/{device_id}", response_model=DeviceParam, tags=["device-params"])
async def read_device_param(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备参数"""
    # 检查设备是否属于当前用户
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问该设备参数"
        )
    
    param = await get_device_param_by_device(db, device_id=device_id)
    if param is None:
        raise HTTPException(status_code=404, detail="设备参数不存在")
    
    return param

@router.post("/", response_model=DeviceParam, tags=["device-params"])
async def create_new_device_param(
    param: DeviceParamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建设备参数"""
    # 检查设备是否属于当前用户
    device = await get_device(db, param.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限为该设备创建参数"
        )
    
    return await create_device_param(db=db, param=param)

@router.put("/device/{device_id}", response_model=DeviceParam, tags=["device-params"])
async def update_device_param_info(
    device_id: int,
    params: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新设备参数"""
    # 检查设备是否属于当前用户
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改该设备参数"
        )
    
    updated_param = await update_or_create_device_param(db=db, device_id=device_id, params=params)
    return updated_param

@router.put("/{param_id}", response_model=DeviceParam, tags=["device-params"])
async def update_device_param_by_id(
    param_id: int,
    param: DeviceParamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """根据参数ID更新设备参数"""
    # 先获取参数信息，检查设备权限
    db_param = await get_device_param(db, param_id=param_id)
    if db_param is None:
        raise HTTPException(status_code=404, detail="设备参数不存在")
    
    # 检查设备是否属于当前用户
    device = await get_device(db, db_param.device_id)
    if not device or device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改该设备参数"
        )
    
    updated_param = await update_device_param(db=db, param_id=param_id, param=param)
    if updated_param is None:
        raise HTTPException(status_code=404, detail="设备参数不存在")
    
    return updated_param
