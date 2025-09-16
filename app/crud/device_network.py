from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.db.models.device_network import DeviceNetwork
from app.models.device_network import DeviceNetworkCreate, DeviceNetworkUpdate
from typing import Optional, List

async def get_device_network(db: AsyncSession, network_id: int) -> Optional[DeviceNetwork]:
    """根据ID获取设备网络信息"""
    result = await db.execute(select(DeviceNetwork).filter(DeviceNetwork.id == network_id))
    return result.scalar_one_or_none()

async def get_device_networks(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DeviceNetwork]:
    """获取所有设备网络信息"""
    result = await db.execute(
        select(DeviceNetwork).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def get_device_networks_by_device(db: AsyncSession, device_id: int, skip: int = 0, limit: int = 100) -> List[DeviceNetwork]:
    """根据设备ID获取网络信息"""
    result = await db.execute(
        select(DeviceNetwork)
        .filter(DeviceNetwork.device_id == device_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_device_network_by_type(db: AsyncSession, device_id: int, net_type) -> Optional[DeviceNetwork]:
    """根据设备ID获取网络信息（兼容旧签名，忽略net_type）。"""
    result = await db.execute(
        select(DeviceNetwork).filter(DeviceNetwork.device_id == device_id)
    )
    return result.scalar_one_or_none()

async def get_device_networks_by_type(db: AsyncSession, net_type, skip: int = 0, limit: int = 100) -> List[DeviceNetwork]:
    """根据网络类型获取网络信息"""
    net_type_value = getattr(net_type, "value", net_type)
    result = await db.execute(
        select(DeviceNetwork)
        .filter(DeviceNetwork.net_type == net_type_value)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_connected_device_networks(db: AsyncSession, device_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[DeviceNetwork]:
    """获取已连接的网络信息"""
    query = select(DeviceNetwork).filter(DeviceNetwork.connect_state == 2)  # 已连接
    
    if device_id is not None:
        query = query.filter(DeviceNetwork.device_id == device_id)
    
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()

async def create_device_network(db: AsyncSession, network: DeviceNetworkCreate) -> DeviceNetwork:
    """创建设备网络信息"""
    # 一对一：检查设备是否已有记录（忽略网络类型）
    existing = await get_device_network_by_type(db, network.device_id, getattr(network.net_type, "value", network.net_type))
    if existing:
        # 如果存在，则更新现有记录
        # 使用 Pydantic v2 的 model_dump 转为可序列化的原始类型，避免 Enum 写入错误
        update_data = network.model_dump(exclude_unset=True, mode="json")
        for field, value in update_data.items():
            setattr(existing, field, value)
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        # 如果不存在，则创建新记录
        payload = network.model_dump(mode="json")
        db_network = DeviceNetwork(**payload)
        db.add(db_network)
        await db.commit()
        await db.refresh(db_network)
        return db_network

async def update_device_network(db: AsyncSession, network_id: int, network: DeviceNetworkUpdate) -> Optional[DeviceNetwork]:
    """更新设备网络信息"""
    db_network = await get_device_network(db, network_id)
    if not db_network:
        return None
    
    update_data = network.model_dump(exclude_unset=True, mode="json")
    for field, value in update_data.items():
        setattr(db_network, field, value)
    
    await db.commit()
    await db.refresh(db_network)
    return db_network

async def update_device_network_by_type(db: AsyncSession, device_id: int, net_type: str, network: DeviceNetworkUpdate) -> Optional[DeviceNetwork]:
    """根据设备ID更新网络信息（兼容旧签名，忽略net_type）。"""
    db_network = await get_device_network_by_type(db, device_id, net_type)
    if not db_network:
        return None
    
    update_data = network.model_dump(exclude_unset=True, mode="json")
    for field, value in update_data.items():
        setattr(db_network, field, value)
    
    await db.commit()
    await db.refresh(db_network)
    return db_network

async def delete_device_network(db: AsyncSession, network_id: int) -> bool:
    """删除设备网络信息"""
    db_network = await get_device_network(db, network_id)
    if not db_network:
        return False
    
    await db.delete(db_network)
    await db.commit()
    return True

async def delete_device_network_by_type(db: AsyncSession, device_id: int, net_type) -> bool:
    """根据设备ID删除网络信息（兼容旧签名，忽略net_type）。"""
    db_network = await get_device_network_by_type(db, device_id, net_type)
    if not db_network:
        return False
    
    await db.delete(db_network)
    await db.commit()
    return True

async def delete_device_networks_by_device(db: AsyncSession, device_id: int) -> int:
    """删除设备的所有网络信息"""
    result = await db.execute(
        select(DeviceNetwork).filter(DeviceNetwork.device_id == device_id)
    )
    networks = result.scalars().all()
    
    count = len(networks)
    for network in networks:
        await db.delete(network)
    
    await db.commit()
    return count
