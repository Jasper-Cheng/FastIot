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
    delete_device_network,
)
from app.crud.device import get_device
from app.models.device_network import (
    DeviceNetworkCreate,
    DeviceNetworkUpdate,
    DeviceNetworkInDB,
    NetworkType,
)
from app.api.dependencies import get_current_guard, ensure_owner_or_admin, require_roles

router = APIRouter(dependencies=[Depends(require_roles(["member", "owner", "admin"]))])


@router.get("/", response_model=List[DeviceNetworkInDB])
async def list_device_networks(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    device_id: Optional[int] = Query(None, description="按设备ID筛选"),
    net_type: Optional[NetworkType] = Query(None, description="按网络类型筛选"),
    connected_only: bool = Query(False, description="只显示已连接的网络"),
    guard: dict = Depends(get_current_guard),
):
    """获取设备网络信息列表"""
    if connected_only:
        return await get_connected_device_networks(db, device_id=device_id, skip=skip, limit=limit)
    elif device_id is not None:
        # 校验设备归属
        device = await get_device(db, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")
        if device.user_id is not None:
            ensure_owner_or_admin(device.user_id, guard)
        return await get_device_networks_by_device(db, device_id=device_id, skip=skip, limit=limit)
    elif net_type is not None:
        return await get_device_networks_by_type(db, net_type=net_type, skip=skip, limit=limit)
    else:
        # admin 返回全部；其他按自己的设备
        if guard.get("role") == "admin":
            return await get_device_networks(db, skip=skip, limit=limit)
        # 非 admin：列出当前用户(或成员归属用户)的所有设备网络
        from sqlalchemy import select
        from app.db.models.device import Device
        owner_user_id = guard.get("user_id") or guard.get("owner_user_id")
        result = await db.execute(
            select(Device.id).where(Device.user_id == owner_user_id)
        )
        device_ids = [row[0] for row in result.fetchall()]
        if not device_ids:
            return []
        networks: list[DeviceNetworkInDB] = []
        for d_id in device_ids:
            nets = await get_device_networks_by_device(db, device_id=d_id, skip=0, limit=limit)
            networks.extend(nets)
        return networks


@router.get("/{network_id}", response_model=DeviceNetworkInDB)
async def get_device_network_detail(network_id: int, db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
    """获取设备网络信息详情"""
    network = await get_device_network(db, network_id)
    if not network:
        raise HTTPException(status_code=404, detail="设备网络信息不存在")
    device = await get_device(db, network.device_id)
    if device and device.user_id is not None:
        ensure_owner_or_admin(device.user_id, guard)
    return network


@router.get("/device/{device_id}", response_model=DeviceNetworkInDB)
async def get_device_network_by_device(device_id: int, db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
    """根据设备ID获取网络信息（设备与网络一对一）。"""
    device = await get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.user_id is not None:
        ensure_owner_or_admin(device.user_id, guard)
    network = await get_device_network_by_type(db, device_id, None)
    if not network:
        raise HTTPException(status_code=404, detail="设备网络信息不存在")
    return network


@router.post("/", response_model=DeviceNetworkInDB)
async def create_device_network_item(payload: DeviceNetworkCreate, db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
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
    if device.user_id is not None:
        ensure_owner_or_admin(device.user_id, guard)
    
    return await create_device_network(db, payload)


@router.put("/{network_id}", response_model=DeviceNetworkInDB)
async def update_device_network_item(network_id: int, payload: DeviceNetworkUpdate, db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
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
    device = await get_device(db, updated.device_id)
    if device and device.user_id is not None:
        ensure_owner_or_admin(device.user_id, guard)
    return updated


@router.delete("/{network_id}")
async def delete_device_network_item(network_id: int, db: AsyncSession = Depends(get_db), guard: dict = Depends(get_current_guard)):
    """删除设备网络信息"""
    ok = await delete_device_network(db, network_id)
    if not ok:
        raise HTTPException(status_code=404, detail="设备网络信息不存在")
    # 权限：根据记录所属设备
    network = await get_device_network(db, network_id)
    if network:
        device = await get_device(db, network.device_id)
        if device and device.user_id is not None:
            ensure_owner_or_admin(device.user_id, guard)
    return {"message": "删除成功"}
