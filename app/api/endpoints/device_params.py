from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from app.db.session import get_db
from app.crud.device_param import (
    get_device_param,
    get_device_param_by_device,
    create_device_param,
    update_device_param,
    update_or_create_device_param,
)
from app.crud.device import get_device
from app.models.device_param import DeviceParamCreate, DeviceParamUpdate, DeviceParamInDB
from app.api.dependencies import get_current_guard, ensure_owner_or_admin, require_roles

router = APIRouter(dependencies=[Depends(require_roles(["member", "owner", "admin"]))])


@router.get("/device/{device_id}", response_model=DeviceParamInDB)
async def get_device_params(device_id: int, db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
    """获取设备的当前参数"""
    # 验证设备存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.user_id is not None:
        ensure_owner_or_admin(device.user_id, guard)
    
    param = await get_device_param_by_device(db, device_id)
    if not param:
        raise HTTPException(status_code=404, detail="设备参数不存在")
    
    return param


@router.post("/", response_model=DeviceParamInDB)
async def create_device_param_item(payload: DeviceParamCreate, db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
    """创建设备参数"""
    # 验证设备存在
    device = await get_device(db, payload.device_id)
    if not device:
        raise HTTPException(status_code=400, detail="设备不存在")
    if device.user_id is not None:
        ensure_owner_or_admin(device.user_id, guard)
    
    # 检查是否已存在参数
    existing = await get_device_param_by_device(db, payload.device_id)
    if existing:
        raise HTTPException(status_code=400, detail="设备参数已存在，请使用更新接口")
    
    return await create_device_param(db, payload)


@router.put("/{param_id}", response_model=DeviceParamInDB)
async def update_device_param_item(param_id: int, payload: DeviceParamUpdate, db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
    """更新设备参数"""
    updated = await update_device_param(db, param_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="设备参数不存在")
    # 校验归属：从更新后的记录反查设备
    device = await get_device(db, updated.device_id)
    if device and device.user_id is not None:
        ensure_owner_or_admin(device.user_id, guard)
    return updated


@router.put("/device/{device_id}/upsert", response_model=DeviceParamInDB)
async def upsert_device_param(device_id: int, params: Dict[str, Any], db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
    """更新或创建设备参数（推荐用于设备上报数据）"""
    # 验证设备存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=400, detail="设备不存在")
    if device.user_id is not None:
        ensure_owner_or_admin(device.user_id, guard)
    
    return await update_or_create_device_param(db, device_id, params)


@router.delete("/{param_id}")
async def delete_device_param_item(param_id: int, db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
    """删除设备参数"""
    param = await get_device_param(db, param_id)
    if not param:
        raise HTTPException(status_code=404, detail="设备参数不存在")
    device = await get_device(db, param.device_id)
    if device and device.user_id is not None:
        ensure_owner_or_admin(device.user_id, guard)
    
    from app.crud.device_param import delete_device_param
    ok = await delete_device_param(db, param_id)
    if not ok:
        raise HTTPException(status_code=404, detail="设备参数不存在")
    
    return {"message": "删除成功"}
