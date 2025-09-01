from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.api.dependencies import get_current_user, get_db
from app.crud.alert import (
    create_alert, get_alert, get_device_alerts, get_user_alerts, get_all_alerts,
    update_alert_status, update_alert_full, get_unread_alerts_count, mark_alerts_as_read
)
from app.models.alert import AlertCreate, AlertUpdate, Alert, AlertStatus
from app.models.user import User, UserRole
from fastapi import status

router = APIRouter()

@router.post("/", response_model=Alert)
async def create_new_alert(
    alert: AlertCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新的告警记录"""
    if current_user.role == UserRole.admin:
        # Admin可以为任何设备创建告警
        try:
            db_alert = await create_alert(db, alert)
            return db_alert
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"创建告警失败: {str(e)}")
    else:
        # 普通用户只能为自己的设备创建告警
        # 检查设备是否属于当前用户
        from app.crud.device import get_device
        device = await get_device(db, alert.device_id)
        if not device or device.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限为该设备创建告警"
            )
        
        try:
            db_alert = await create_alert(db, alert)
            return db_alert
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"创建告警失败: {str(e)}")

@router.get("/", response_model=List[Alert])
async def get_alerts(
    device_id: int = Query(None, description="设备ID，可选"),
    status: AlertStatus = Query(None, description="告警状态，可选"),
    limit: int = Query(100, description="返回数量限制"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取告警列表"""
    if device_id:
        # 如果指定了设备ID
        if current_user.role == UserRole.admin:
            # Admin可以查看任何设备的告警
            alerts = await get_device_alerts(db, device_id, limit)
        else:
            # 普通用户只能查看自己设备的告警
            from app.crud.device import get_device
            device = await get_device(db, device_id)
            if not device or device.owner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="没有权限查看该设备的告警"
                )
            alerts = await get_device_alerts(db, device_id, limit)
    else:
        # 没有指定设备ID
        if current_user.role == UserRole.admin:
            # Admin获取所有告警
            alerts = await get_all_alerts(db, limit)
        else:
            # 普通用户获取自己所有设备的告警
            alerts = await get_user_alerts(db, current_user.id, limit)
    
    # 如果指定了状态，进行过滤
    if status:
        alerts = [alert for alert in alerts if alert.status == status]
    
    return alerts

@router.get("/{alert_id}", response_model=Alert)
async def get_alert_by_id(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """根据ID获取告警详情"""
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    if current_user.role == UserRole.admin:
        # Admin可以查看任何告警
        return alert
    else:
        # 普通用户只能查看自己设备的告警
        from app.crud.device import get_device
        device = await get_device(db, alert.device_id)
        if not device or device.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限查看该告警"
            )
        return alert

@router.put("/{alert_id}", response_model=Alert)
async def update_alert(
    alert_id: int,
    alert_update: AlertUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新告警信息"""
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    if current_user.role == UserRole.admin:
        # Admin可以更新任何告警
        try:
            updated_alert = await update_alert_full(db, alert_id, alert_update)
            return updated_alert
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"更新告警失败: {str(e)}")
    else:
        # 普通用户只能更新自己设备的告警
        from app.crud.device import get_device
        device = await get_device(db, alert.device_id)
        if not device or device.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限更新该告警"
            )
        
        try:
            updated_alert = await update_alert_full(db, alert_id, alert_update)
            return updated_alert
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"更新告警失败: {str(e)}")

@router.put("/{alert_id}/status", response_model=Alert)
async def update_alert_status_endpoint(
    alert_id: int,
    status: AlertStatus,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新告警状态"""
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    if current_user.role == UserRole.admin:
        # Admin可以更新任何告警状态
        try:
            updated_alert = await update_alert_status(db, alert_id, status)
            return updated_alert
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"更新告警状态失败: {str(e)}")
    else:
        # 普通用户只能更新自己设备的告警状态
        from app.crud.device import get_device
        device = await get_device(db, alert.device_id)
        if not device or device.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限更新该告警状态"
            )
        
        try:
            updated_alert = await update_alert_status(db, alert_id, status)
            return updated_alert
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"更新告警状态失败: {str(e)}")

@router.post("/mark-read")
async def mark_alerts_as_read_endpoint(
    alert_ids: List[int],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量标记告警为已读"""
    if current_user.role == UserRole.admin:
        # Admin可以标记所有告警为已读
        try:
            success = await mark_alerts_as_read(db, alert_ids)
            if success:
                return {"message": "告警已标记为已读", "count": len(alert_ids)}
            else:
                raise HTTPException(status_code=400, detail="标记告警失败")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"标记告警失败: {str(e)}")
    else:
        # 普通用户只能标记自己设备的告警为已读
        # 首先获取用户所有设备的告警ID
        user_alerts = await get_user_alerts(db, current_user.id, limit=1000)  # 获取足够多的告警
        user_alert_ids = {alert.id for alert in user_alerts}
        
        # 检查要标记的告警是否都是用户的
        unauthorized_alerts = [aid for aid in alert_ids if aid not in user_alert_ids]
        if unauthorized_alerts:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"没有权限操作告警: {unauthorized_alerts}"
            )
        
        # 只标记用户有权限的告警
        authorized_alert_ids = [aid for aid in alert_ids if aid in user_alert_ids]
        
        try:
            success = await mark_alerts_as_read(db, authorized_alert_ids)
            if success:
                return {
                    "message": "告警已标记为已读", 
                    "count": len(authorized_alert_ids),
                    "unauthorized_count": len(unauthorized_alerts)
                }
            else:
                raise HTTPException(status_code=400, detail="标记告警失败")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"标记告警失败: {str(e)}")

@router.get("/unread/count")
async def get_unread_alerts_count_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户未读告警数量"""
    try:
        count = await get_unread_alerts_count(db, current_user.id)
        return {"unread_count": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取未读告警数量失败: {str(e)}")

@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除告警记录"""
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    
    if current_user.role == UserRole.admin:
        # Admin可以删除任何告警
        # 这里可以实现删除告警的逻辑
        # 通常不建议物理删除，而是标记为已解决或归档
        raise HTTPException(status_code=501, detail="删除告警功能暂未实现，请使用状态更新")
    else:
        # 普通用户只能删除自己设备的告警
        from app.crud.device import get_device
        device = await get_device(db, alert.device_id)
        if not device or device.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限删除该告警"
            )
        
        # 这里可以实现删除告警的逻辑
        # 通常不建议物理删除，而是标记为已解决或归档
        raise HTTPException(status_code=501, detail="删除告警功能暂未实现，请使用状态更新")
