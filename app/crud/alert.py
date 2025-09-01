from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from app.db.models.alert import Alert
from app.models.alert import AlertCreate, AlertUpdate, AlertStatus

async def create_alert(db: AsyncSession, alert: AlertCreate) -> Alert:
    """创建新的告警记录"""
    db_alert = Alert(
        device_id=alert.device_id,
        alert_type=alert.alert_type,
        message=alert.message,
        status=AlertStatus.new
    )
    db.add(db_alert)
    await db.commit()
    await db.refresh(db_alert)
    return db_alert

async def get_alert(db: AsyncSession, alert_id: int) -> Optional[Alert]:
    """根据ID获取告警记录"""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    return result.scalar_one_or_none()

async def get_device_alerts(db: AsyncSession, device_id: int, limit: int = 100) -> List[Alert]:
    """获取指定设备的所有告警记录"""
    result = await db.execute(
        select(Alert)
        .where(Alert.device_id == device_id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()

async def get_user_alerts(db: AsyncSession, user_id: int, limit: int = 100) -> List[Alert]:
    """获取指定用户所有设备的告警记录"""
    # 这里需要关联查询用户拥有的设备
    from app.db.models.device import Device
    result = await db.execute(
        select(Alert)
        .join(Device, Alert.device_id == Device.id)
        .where(Device.owner_id == user_id)  # 修复：使用 owner_id 而不是 user_id
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()

async def update_alert_status(db: AsyncSession, alert_id: int, status: AlertStatus) -> Optional[Alert]:
    """更新告警状态"""
    await db.execute(
        update(Alert)
        .where(Alert.id == alert_id)
        .values(status=status)
    )
    await db.commit()
    
    # 返回更新后的告警记录
    return await get_alert(db, alert_id)

async def update_alert_content(db: AsyncSession, alert_id: int, alert_type: Optional[str] = None, message: Optional[str] = None) -> Optional[Alert]:
    """更新告警内容（alert_type和message）"""
    update_data = {}
    if alert_type is not None:
        update_data["alert_type"] = alert_type
    if message is not None:
        update_data["message"] = message
    
    if update_data:
        await db.execute(
            update(Alert)
            .where(Alert.id == alert_id)
            .values(**update_data)
        )
        await db.commit()
    
    # 返回更新后的告警记录
    return await get_alert(db, alert_id)

async def update_alert_full(db: AsyncSession, alert_id: int, alert_update: AlertUpdate) -> Optional[Alert]:
    """完整更新告警信息"""
    update_data = {}
    
    # 收集需要更新的字段
    if alert_update.alert_type is not None:
        update_data["alert_type"] = alert_update.alert_type
    if alert_update.message is not None:
        update_data["message"] = alert_update.message
    if alert_update.status is not None:
        update_data["status"] = alert_update.status
    
    if update_data:
        await db.execute(
            update(Alert)
            .where(Alert.id == alert_id)
            .values(**update_data)
        )
        await db.commit()
    
    # 返回更新后的告警记录
    return await get_alert(db, alert_id)

async def get_unread_alerts_count(db: AsyncSession, user_id: int) -> int:
    """获取用户未读告警数量"""
    from app.db.models.device import Device
    result = await db.execute(
        select(Alert)
        .join(Device, Alert.device_id == Device.id)
        .where(Device.owner_id == user_id, Alert.status == AlertStatus.new)  # 修复：使用 owner_id
    )
    return len(result.scalars().all())

async def mark_alerts_as_read(db: AsyncSession, alert_ids: List[int]) -> bool:
    """批量标记告警为已读"""
    await db.execute(
        update(Alert)
        .where(Alert.id.in_(alert_ids))
        .values(status=AlertStatus.read)
    )
    await db.commit()
    return True
