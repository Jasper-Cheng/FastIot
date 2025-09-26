from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta
from app.utils.time_utils import get_local_time

from app.db.session import get_db
from app.crud.device_log import (
    get_device_log,
    get_device_logs_by_device,
    get_device_logs_by_type,
    create_device_log,
)
from app.db.models.device_log import DeviceLog
from app.crud.device import get_device
from app.models.device_log import (
    DeviceLogCreate,
    DeviceLogInDB,
)

router = APIRouter()


@router.get("/", response_model=List[DeviceLogInDB])
async def list_device_logs(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    device_id: Optional[int] = Query(None, description="按设备ID筛选"),
    type: Optional[str] = Query(None, description="按类型筛选"),
    days: Optional[int] = Query(None, ge=1, le=365, description="最近N天的日志"),
):
    """获取设备日志列表
    
    支持按设备ID、类型、时间范围筛选
    """
    if device_id:
        # 验证设备存在
        device = await get_device(db, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")
        
        if type:
            return await get_device_logs_by_type(db, device_id, type, skip, limit)
        else:
            return await get_device_logs_by_device(db, device_id, skip, limit)
    else:
        # 如果没有指定设备ID，返回空列表（避免查询所有日志）
        raise HTTPException(status_code=400, detail="必须指定设备ID")


@router.get("/{log_id}", response_model=DeviceLogInDB)
async def get_device_log_detail(log_id: int, db: AsyncSession = Depends(get_db)):
    """获取设备日志详情"""
    log = await get_device_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="设备日志不存在")
    return log


@router.post("/", response_model=DeviceLogInDB)
async def create_device_log_item(payload: DeviceLogCreate, db: AsyncSession = Depends(get_db)):
    """创建设备日志
    
    示例请求体：
    {
      "device_id": 1,
      "type": "properties",
      "params": {
        "timestamp": "2024-01-01T10:00:00Z",
        "voltage": 220.5,
        "current": 1.2
      }
    }
    
    类型支持：properties（属性相关）、services（服务相关）、events（事件相关）
    """
    # 验证设备存在
    device = await get_device(db, payload.device_id)
    if not device:
        raise HTTPException(status_code=400, detail="设备不存在")
    
    return await create_device_log(db, payload)


@router.get("/device/{device_id}/stats", response_model=dict)
async def get_device_log_stats(device_id: int, db: AsyncSession = Depends(get_db)):
    """获取设备日志统计信息"""
    # 验证设备存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    from sqlalchemy import select, func, text
    
    # 总日志数
    total_result = await db.execute(
        select(func.count(DeviceLog.id)).filter(DeviceLog.device_id == device_id)
    )
    total_logs = total_result.scalar()
    
    # 按类型统计
    type_stats_result = await db.execute(
        select(
            DeviceLog.type,
            func.count(DeviceLog.id).label('count')
        )
        .filter(DeviceLog.device_id == device_id)
        .filter(DeviceLog.type.isnot(None))
        .group_by(DeviceLog.type)
    )
    type_stats = {row[0]: row[1] for row in type_stats_result.fetchall()}
    
    # 最近24小时日志数
    yesterday = get_local_time() - timedelta(days=1)
    recent_result = await db.execute(
        select(func.count(DeviceLog.id))
        .filter(DeviceLog.device_id == device_id)
        .filter(DeviceLog.created_at >= yesterday)
    )
    recent_logs = recent_result.scalar()
    
    # 最早和最晚日志时间
    time_range_result = await db.execute(
        select(
            func.min(DeviceLog.created_at).label('earliest'),
            func.max(DeviceLog.created_at).label('latest')
        )
        .filter(DeviceLog.device_id == device_id)
    )
    time_range = time_range_result.fetchone()
    
    return {
        "device_id": device_id,
        "total_logs": total_logs,
        "recent_24h_logs": recent_logs,
        "type_stats": type_stats,
        "earliest_log": time_range[0].isoformat() if time_range[0] else None,
        "latest_log": time_range[1].isoformat() if time_range[1] else None,
    }