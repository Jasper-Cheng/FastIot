from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select, func, and_, or_
from datetime import datetime

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.crud.device_message import get_device_messages_with_pagination
from app.db.models.device_message import DeviceMessage
from app.db.models.device import Device

router = APIRouter()


@router.get("/device-message/list")
async def get_device_message_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    deviceId: Optional[int] = Query(None, description="设备ID筛选"),
    level: Optional[str] = Query(None, description="消息级别筛选"),
    type: Optional[str] = Query(None, description="消息类型筛选"),
    status: Optional[str] = Query(None, description="消息状态筛选"),
    startDate: Optional[str] = Query(None, description="开始日期（格式：YYYY-MM-DD）"),
    endDate: Optional[str] = Query(None, description="结束日期（格式：YYYY-MM-DD）"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取设备消息列表"""
    skip = (page - 1) * pageSize
    
    # 处理日期参数
    start_date = None
    end_date = None
    if startDate:
        try:
            start_date = datetime.strptime(startDate, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始日期格式不正确，应为 YYYY-MM-DD")
    if endDate:
        try:
            end_date = datetime.strptime(endDate, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="结束日期格式不正确，应为 YYYY-MM-DD")
    
    messages, total = await get_device_messages_with_pagination(
        db=db,
        skip=skip,
        limit=pageSize,
        device_id=deviceId,
        level=level,
        type=type,
        status=status,
        start_date=start_date,
        end_date=end_date
    )
    
    items = []
    for message in messages:
        # 获取设备信息
        device_result = await db.execute(
            select(Device).filter(Device.id == message.device_id)
        )
        device = device_result.scalar_one_or_none()
        
        items.append({
            "id": message.id,
            "deviceId": message.device_id,
            "deviceSn": device.sn if device else None,
            "deviceName": device.name if device else None,
            "level": message.level,
            "status": message.status,
            "message": message.message,
            "detail": message.detail or {},
            "createdAt": message.created_at.strftime("%Y-%m-%d %H:%M:%S") if message.created_at else None,
            "updatedAt": message.updated_at.strftime("%Y-%m-%d %H:%M:%S") if message.updated_at else None
        })
    
    return {
        "items": items,
        "total": total
    }


@router.get("/device-message/today-alerts")
async def get_today_alerts(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    deviceId: Optional[int] = Query(None, description="设备ID筛选"),
    status: Optional[str] = Query(None, description="消息状态筛选"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取今日告警列表
    
    返回今日（当天）创建的错误级别（error）和严重错误级别（fatal）的设备消息
    """
    skip = (page - 1) * pageSize
    
    # 查询今日创建的消息（level 为 'error' 或 'fatal'）
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    query = select(DeviceMessage).where(
        and_(
            DeviceMessage.created_at >= today_start,
            DeviceMessage.created_at <= today_end,
            or_(
                DeviceMessage.level == 'error',
                DeviceMessage.level == 'fatal'
            )
        )
    )
    count_query = select(func.count(DeviceMessage.id)).where(
        and_(
            DeviceMessage.created_at >= today_start,
            DeviceMessage.created_at <= today_end,
            or_(
                DeviceMessage.level == 'error',
                DeviceMessage.level == 'fatal'
            )
        )
    )
    
    # 如果提供了设备ID筛选
    if deviceId:
        query = query.where(DeviceMessage.device_id == deviceId)
        count_query = count_query.where(DeviceMessage.device_id == deviceId)
    
    # 如果提供了状态筛选
    if status:
        query = query.where(DeviceMessage.status == status)
        count_query = count_query.where(DeviceMessage.status == status)
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 获取分页数据，按创建时间倒序
    result = await db.execute(
        query.order_by(DeviceMessage.created_at.desc())
        .offset(skip)
        .limit(pageSize)
    )
    messages = result.scalars().all()
    
    items = []
    for message in messages:
        # 获取设备信息
        device_result = await db.execute(
            select(Device).filter(Device.id == message.device_id)
        )
        device = device_result.scalar_one_or_none()
        
        items.append({
            "id": message.id,
            "deviceId": message.device_id,
            "deviceSn": device.sn if device else None,
            "deviceName": device.name if device else None,
            "level": message.level,
            "status": message.status,
            "message": message.message,
            "detail": message.detail or {},
            "createdAt": message.created_at.strftime("%Y-%m-%d %H:%M:%S") if message.created_at else None,
            "updatedAt": message.updated_at.strftime("%Y-%m-%d %H:%M:%S") if message.updated_at else None
        })
    
    return {
        "items": items,
        "total": total,
        "date": datetime.now().strftime("%Y-%m-%d")
    }

