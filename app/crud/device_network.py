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

async def get_device_network_by_type(db: AsyncSession, device_id: int, net_type: str) -> Optional[DeviceNetwork]:
    """根据设备ID和网络类型获取网络信息"""
    result = await db.execute(
        select(DeviceNetwork).filter(
            and_(
                DeviceNetwork.device_id == device_id,
                DeviceNetwork.net_type == net_type
            )
        )
    )
    return result.scalar_one_or_none()

async def get_device_networks_by_type(db: AsyncSession, net_type: str, skip: int = 0, limit: int = 100) -> List[DeviceNetwork]:
    """根据网络类型获取网络信息"""
    result = await db.execute(
        select(DeviceNetwork)
        .filter(DeviceNetwork.net_type == net_type)
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
    # 检查是否已存在相同设备和网络类型的记录
    existing = await get_device_network_by_type(db, network.device_id, network.net_type)
    if existing:
        # 如果存在，则更新现有记录
        update_data = network.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        # 如果不存在，则创建新记录
        db_network = DeviceNetwork(**network.dict())
        db.add(db_network)
        await db.commit()
        await db.refresh(db_network)
        return db_network

async def update_device_network(db: AsyncSession, network_id: int, network: DeviceNetworkUpdate) -> Optional[DeviceNetwork]:
    """更新设备网络信息"""
    db_network = await get_device_network(db, network_id)
    if not db_network:
        return None
    
    update_data = network.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_network, field, value)
    
    await db.commit()
    await db.refresh(db_network)
    return db_network

async def update_device_network_by_type(db: AsyncSession, device_id: int, net_type: str, network: DeviceNetworkUpdate) -> Optional[DeviceNetwork]:
    """根据设备ID和网络类型更新网络信息"""
    db_network = await get_device_network_by_type(db, device_id, net_type)
    if not db_network:
        return None
    
    update_data = network.dict(exclude_unset=True)
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

async def delete_device_network_by_type(db: AsyncSession, device_id: int, net_type: str) -> bool:
    """根据设备ID和网络类型删除网络信息"""
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
