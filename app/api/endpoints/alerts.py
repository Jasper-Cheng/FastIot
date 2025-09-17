from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db
from app.crud.alert import (
    create_alert,
    get_alert,
    get_device_alerts,
    get_user_alerts,
    get_all_alerts,
    update_alert_status,
    update_alert_content,
    update_alert_full,
    get_unread_alerts_count,
    mark_alerts_as_read,
)
from app.crud.device import get_device
from app.models.alert import (
    AlertCreate,
    AlertUpdate,
    AlertInDB,
    AlertLevel,
    AlertStatus,
)
router = APIRouter()


@router.get("/", response_model=List[AlertInDB])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    device_id: Optional[int] = Query(None, description="按设备ID筛选"),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    level: Optional[AlertLevel] = Query(None, description="按告警级别筛选"),
    status: Optional[AlertStatus] = Query(None, description="按告警状态筛选"),
    days: Optional[int] = Query(None, ge=1, le=365, description="最近N天的告警"),
):
    """获取告警列表
    
    支持按设备ID、用户ID、级别、状态、时间范围筛选
    """
    if device_id:
        # 验证设备存在
        device = await get_device(db, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")
        
        alerts = await get_device_alerts(db, device_id, limit)
    elif user_id:
        alerts = await get_user_alerts(db, user_id, limit)
    else:
        alerts = await get_all_alerts(db, limit)
    
    # 应用筛选条件
    filtered_alerts = []
    for alert in alerts:
        # 级别筛选
        if level and alert.level != level:
            continue
        # 状态筛选
        if status and alert.status != status:
            continue
        # 时间筛选
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            if alert.created_at < cutoff_date:
                continue
        
        filtered_alerts.append(alert)
    
    # 应用分页
    return filtered_alerts[skip:skip + limit]


@router.get("/{alert_id}", response_model=AlertInDB)
async def get_alert_detail(alert_id: int, db: AsyncSession = Depends(get_db)):
    """获取告警详情"""
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    return alert


@router.post("/", response_model=AlertInDB)
async def create_alert_item(payload: AlertCreate, db: AsyncSession = Depends(get_db)):
    """创建告警
    
    示例请求体：
    {
      "device_id": 1,
      "level": "high",
      "message": "设备温度过高，请立即检查"
    }
    """
    # 验证设备存在
    device = await get_device(db, payload.device_id)
    if not device:
        raise HTTPException(status_code=400, detail="设备不存在")
    
    return await create_alert(db, payload)


@router.put("/{alert_id}", response_model=AlertInDB)
async def update_alert_item(alert_id: int, payload: AlertUpdate, db: AsyncSession = Depends(get_db)):
    """更新告警信息
    
    示例请求体：
    {
      "level": "medium",
      "message": "设备温度恢复正常",
      "status": "resolved"
    }
    """
    updated = await update_alert_full(db, alert_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="告警不存在")
    return updated


@router.patch("/{alert_id}/status", response_model=AlertInDB)
async def update_alert_status_item(
    alert_id: int, 
    status: AlertStatus, 
    db: AsyncSession = Depends(get_db),
):
    """更新告警状态"""
    updated = await update_alert_status(db, alert_id, status)
    if not updated:
        raise HTTPException(status_code=404, detail="告警不存在")
    return updated


@router.patch("/{alert_id}/content", response_model=AlertInDB)
async def update_alert_content_item(
    alert_id: int,
    level: Optional[AlertLevel] = None,
    message: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """更新告警内容（级别和消息）"""
    updated = await update_alert_content(db, alert_id, level, message)
    if not updated:
        raise HTTPException(status_code=404, detail="告警不存在")
    return updated


@router.delete("/{alert_id}")
async def delete_alert_item(alert_id: int, db: AsyncSession = Depends(get_db)):
    """删除告警"""
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    await db.delete(alert)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/user/{user_id}/unread-count")
async def get_user_unread_count(user_id: int, db: AsyncSession = Depends(get_db)):
    """获取用户未读告警数量"""
    count = await get_unread_alerts_count(db, user_id)
    return {"user_id": user_id, "unread_count": count}


@router.patch("/user/{user_id}/mark-all-read")
async def mark_user_all_alerts_read(user_id: int, db: AsyncSession = Depends(get_db)):
    """一键标记用户所有未读告警为已读"""
    from app.crud.user import get_user
    from sqlalchemy import select, update
    from app.db.models.device import Device
    from app.db.models.alert import Alert
    from app.models.alert import AlertStatus
    
    # 验证用户存在
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新该用户所有设备的未读告警为已读
    result = await db.execute(
        update(Alert)
        .where(
            Alert.device_id.in_(
                select(Device.id).where(Device.user_id == user_id)
            ),
            Alert.status == AlertStatus.new
        )
        .values(status=AlertStatus.read)
    )
    
    await db.commit()
    
    # 返回更新的告警数量
    updated_count = result.rowcount
    return {
        "message": f"成功标记 {updated_count} 条告警为已读",
        "user_id": user_id,
        "updated_count": updated_count
    }


@router.get("/device/{device_id}/stats", response_model=dict)
async def get_device_alert_stats(device_id: int, db: AsyncSession = Depends(get_db)):
    """获取设备告警统计信息"""
    # 验证设备存在
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    from sqlalchemy import select, func
    from app.db.models.alert import Alert
    
    # 总告警数
    total_result = await db.execute(
        select(func.count(Alert.id)).filter(Alert.device_id == device_id)
    )
    total_alerts = total_result.scalar()
    
    # 按级别统计
    level_stats_result = await db.execute(
        select(
            Alert.level,
            func.count(Alert.id).label('count')
        )
        .filter(Alert.device_id == device_id)
        .group_by(Alert.level)
    )
    level_stats = {row[0]: row[1] for row in level_stats_result.fetchall()}
    
    # 按状态统计
    status_stats_result = await db.execute(
        select(
            Alert.status,
            func.count(Alert.id).label('count')
        )
        .filter(Alert.device_id == device_id)
        .group_by(Alert.status)
    )
    status_stats = {row[0]: row[1] for row in status_stats_result.fetchall()}
    
    # 最近24小时告警数
    yesterday = datetime.now() - timedelta(days=1)
    recent_result = await db.execute(
        select(func.count(Alert.id))
        .filter(Alert.device_id == device_id)
        .filter(Alert.created_at >= yesterday)
    )
    recent_alerts = recent_result.scalar()
    
    # 最早和最晚告警时间
    time_range_result = await db.execute(
        select(
            func.min(Alert.created_at).label('earliest'),
            func.max(Alert.created_at).label('latest')
        )
        .filter(Alert.device_id == device_id)
    )
    time_range = time_range_result.fetchone()
    
    return {
        "device_id": device_id,
        "total_alerts": total_alerts,
        "recent_24h_alerts": recent_alerts,
        "level_stats": level_stats,
        "status_stats": status_stats,
        "earliest_alert": time_range[0].isoformat() if time_range[0] else None,
        "latest_alert": time_range[1].isoformat() if time_range[1] else None,
    }


@router.get("/user/{user_id}/stats", response_model=dict)
async def get_user_alert_stats(user_id: int, db: AsyncSession = Depends(get_db)):
    """获取用户告警统计信息"""
    from sqlalchemy import select, func
    from app.db.models.device import Device
    from app.db.models.alert import Alert
    from app.crud.user import get_user
    
    # 验证用户存在
    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 总告警数
    total_result = await db.execute(
        select(func.count(Alert.id))
        .join(Device, Alert.device_id == Device.id)
        .filter(Device.user_id == user_id)
    )
    total_alerts = total_result.scalar()
    
    # 未读告警数
    unread_count = await get_unread_alerts_count(db, user_id)
    
    # 按级别统计
    level_stats_result = await db.execute(
        select(
            Alert.level,
            func.count(Alert.id).label('count')
        )
        .join(Device, Alert.device_id == Device.id)
        .filter(Device.user_id == user_id)
        .group_by(Alert.level)
    )
    level_stats = {row[0]: row[1] for row in level_stats_result.fetchall()}
    
    # 按状态统计
    status_stats_result = await db.execute(
        select(
            Alert.status,
            func.count(Alert.id).label('count')
        )
        .join(Device, Alert.device_id == Device.id)
        .filter(Device.user_id == user_id)
        .group_by(Alert.status)
    )
    status_stats = {row[0]: row[1] for row in status_stats_result.fetchall()}
    
    return {
        "user_id": user_id,
        "total_alerts": total_alerts,
        "unread_alerts": unread_count,
        "level_stats": level_stats,
        "status_stats": status_stats,
    }
