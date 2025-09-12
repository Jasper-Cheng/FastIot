from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.api.dependencies import get_db
from app.crud.device_log import (
    get_device_log, get_device_logs_by_device, get_device_logs_by_event_type,
    create_device_log, update_device_log, delete_device_log
)
from app.crud.device import get_device
from app.models.device_log import DeviceLog, DeviceLogCreate, DeviceLogUpdate
from app.models.user import User
from app.api.endpoints.auth import get_current_user

router = APIRouter()

@router.get("/device/{device_id}", response_model=List[DeviceLog], tags=["device-logs"])
async def read_device_logs(
    device_id: int,
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取设备日志列表"""
    # 检查设备是否属于当前用户
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问该设备日志"
        )
    
    if event_type:
        logs = await get_device_logs_by_event_type(db, device_id=device_id, event_type=event_type, skip=skip, limit=limit)
    else:
        logs = await get_device_logs_by_device(db, device_id=device_id, skip=skip, limit=limit)
    
    return logs

@router.post("/", response_model=DeviceLog, tags=["device-logs"])
async def create_new_device_log(
    log: DeviceLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建设备日志"""
    # 检查设备是否属于当前用户
    device = await get_device(db, log.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限为该设备创建日志"
        )
    
    return await create_device_log(db=db, log=log)

@router.get("/{log_id}", response_model=DeviceLog, tags=["device-logs"])
async def read_device_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定设备日志信息"""
    log = await get_device_log(db, log_id=log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="设备日志不存在")
    
    # 检查设备是否属于当前用户
    device = await get_device(db, log.device_id)
    if not device or device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问该设备日志"
        )
    
    return log

@router.put("/{log_id}", response_model=DeviceLog, tags=["device-logs"])
async def update_device_log_info(
    log_id: int,
    log: DeviceLogUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新设备日志信息"""
    # 先获取日志信息，检查设备权限
    db_log = await get_device_log(db, log_id=log_id)
    if db_log is None:
        raise HTTPException(status_code=404, detail="设备日志不存在")
    
    # 检查设备是否属于当前用户
    device = await get_device(db, db_log.device_id)
    if not device or device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改该设备日志"
        )
    
    updated_log = await update_device_log(db=db, log_id=log_id, log=log)
    if updated_log is None:
        raise HTTPException(status_code=404, detail="设备日志不存在")
    
    return updated_log

@router.delete("/{log_id}", tags=["device-logs"])
async def delete_device_log_info(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除设备日志"""
    # 先获取日志信息，检查设备权限
    db_log = await get_device_log(db, log_id=log_id)
    if db_log is None:
        raise HTTPException(status_code=404, detail="设备日志不存在")
    
    # 检查设备是否属于当前用户
    device = await get_device(db, db_log.device_id)
    if not device or device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除该设备日志"
        )
    
    success = await delete_device_log(db=db, log_id=log_id)
    if not success:
        raise HTTPException(status_code=404, detail="设备日志不存在")
    
    return {"message": "设备日志删除成功"}
