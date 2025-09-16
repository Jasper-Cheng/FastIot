from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_db
from app.crud.device_network import (
    get_device_networks,
    get_device_networks_by_device,
    get_device_network_by_type,
    get_device_networks_by_type,
    get_connected_device_networks,
    get_device_network,
    create_device_network,
    update_device_network,
    update_device_network_by_type,
    delete_device_network,
    delete_device_network_by_type,
)
from app.crud.device import get_device
from app.models.device_network import (
    DeviceNetworkCreate,
    DeviceNetworkUpdate,
    DeviceNetworkInDB,
    NetworkType,
    ConnectState,
)

router = APIRouter()


@router.get("/", response_model=List[DeviceNetworkInDB])
async def list_device_networks(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    device_id: Optional[int] = Query(None, description="按设备ID筛选"),
    net_type: Optional[NetworkType] = Query(None, description="按网络类型筛选"),
    connected_only: bool = Query(False, description="只显示已连接的网络"),
):
    """获取设备网络信息列表"""
    if connected_only:
        return await get_connected_device_networks(db, device_id=device_id, skip=skip, limit=limit)
    elif device_id is not None:
        return await get_device_networks_by_device(db, device_id=device_id, skip=skip, limit=limit)
    elif net_type is not None:
        return await get_device_networks_by_type(db, net_type=net_type, skip=skip, limit=limit)
    else:
        return await get_device_networks(db, skip=skip, limit=limit)


@router.get("/{network_id}", response_model=DeviceNetworkInDB)
async def get_device_network_detail(network_id: int, db: AsyncSession = Depends(get_db)):
    """获取设备网络信息详情"""
    network = await get_device_network(db, network_id)
    if not network:
        raise HTTPException(status_code=404, detail="设备网络信息不存在")
    return network


@router.get("/device/{device_id}", response_model=DeviceNetworkInDB)
async def get_device_network_by_device(device_id: int, db: AsyncSession = Depends(get_db)):
    """根据设备ID获取网络信息（设备与网络一对一）。"""
    network = await get_device_network_by_type(db, device_id, None)
    if not network:
        raise HTTPException(status_code=404, detail="设备网络信息不存在")
    return network


@router.post("/", response_model=DeviceNetworkInDB)
async def create_device_network_item(payload: DeviceNetworkCreate, db: AsyncSession = Depends(get_db)):
    """创建设备网络信息
    
    示例请求体：
    {
      "device_id": 1,
      "net_type": "wifi",
      "name": "MyWiFi",
      "ip": "192.168.1.100",
      "mac": "00:11:22:33:44:55",
      "rssi": -45,
      "connect_state": 2,
      "extra": {
        "gateway": "192.168.1.1",
        "frequency": "2.4G"
      }
    }
    """
    # 验证设备存在
    device = await get_device(db, payload.device_id)
    if not device:
        raise HTTPException(status_code=400, detail="设备不存在")
    
    return await create_device_network(db, payload)


@router.put("/{network_id}", response_model=DeviceNetworkInDB)
async def update_device_network_item(network_id: int, payload: DeviceNetworkUpdate, db: AsyncSession = Depends(get_db)):
    """更新设备网络信息
    
    示例请求体：
    {
      "name": "MyWiFi",
      "ip": "192.168.1.100",
      "rssi": -45,
      "connect_state": 2,
      "extra": {
        "gateway": "192.168.1.1"
      }
    }
    """
    updated = await update_device_network(db, network_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="设备网络信息不存在")
    return updated


@router.put("/device/{device_id}", response_model=DeviceNetworkInDB)
async def update_device_network_by_device(
    device_id: int,
    payload: DeviceNetworkUpdate,
    db: AsyncSession = Depends(get_db)
):
    """根据设备ID更新网络信息（设备与网络一对一）。"""
    updated = await update_device_network_by_type(db, device_id, "", payload)
    if not updated:
        raise HTTPException(status_code=404, detail="设备网络信息不存在")
    return updated


@router.delete("/{network_id}")
async def delete_device_network_item(network_id: int, db: AsyncSession = Depends(get_db)):
    """删除设备网络信息"""
    ok = await delete_device_network(db, network_id)
    if not ok:
        raise HTTPException(status_code=404, detail="设备网络信息不存在")
    return {"message": "删除成功"}


@router.delete("/device/{device_id}")
async def delete_device_network_by_device(
    device_id: int,
    db: AsyncSession = Depends(get_db)
):
    """根据设备ID删除网络信息（设备与网络一对一）。"""
    ok = await delete_device_network_by_type(db, device_id, "")
    if not ok:
        raise HTTPException(status_code=404, detail="设备网络信息不存在")
    return {"message": "删除成功"}


# 按设备一对一关系，不再提供删除所有网络信息的批量接口
