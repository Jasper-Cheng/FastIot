from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select, func

from app.db.session import get_db
from app.api.dependencies import get_current_token
from app.db.models.device_network import DeviceNetwork
from app.db.models.device import Device

router = APIRouter()


@router.get("/network/list")
async def get_network_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    pageSize: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """获取设备网络信息列表"""
    skip = (page - 1) * pageSize
    
    # 查询网络信息
    query = select(DeviceNetwork)
    count_query = select(func.count(DeviceNetwork.id))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 获取分页数据
    result = await db.execute(query.offset(skip).limit(pageSize))
    networks = result.scalars().all()
    
    items = []
    for network in networks:
        # 获取设备信息
        device_result = await db.execute(
            select(Device).filter(Device.id == network.device_id)
        )
        device = device_result.scalar_one_or_none()
        
        items.append({
            "id": network.id,
            "deviceId": network.device_id,
            "deviceSn": device.sn if device else None,
            "deviceName": device.name if device else None,
            "netType": network.net_type,
            "name": network.name,
            "ip": network.ip,
            "mac": network.mac,
            "rssi": network.rssi,
            "connectState": network.connect_state,
            "extra": network.extra or {},
            "lastUpdate": network.last_update.strftime("%Y-%m-%d %H:%M:%S") if network.last_update else None
        })
    
    return {
        "items": items,
        "total": total
    }

