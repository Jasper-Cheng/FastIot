from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from app.db.models.room_device import RoomDevice as RoomDeviceORM
from app.models.room_device import RoomDeviceBatchSortItem


async def get_room_devices_by_room(db: AsyncSession, room_id: int) -> List[RoomDeviceORM]:
    result = await db.execute(select(RoomDeviceORM).filter(RoomDeviceORM.room_id == room_id).order_by(RoomDeviceORM.sort_order, RoomDeviceORM.id))
    return result.scalars().all()


async def batch_update_room_devices(
    db: AsyncSession, 
    room_id: int, 
    devices: List[RoomDeviceBatchSortItem],
    user_id: int
) -> List[RoomDeviceORM]:
    """
    批量更新房间设备关联
    
    Args:
        db: 数据库会话
        room_id: 房间ID
        devices: 设备排序列表
        user_id: 用户ID（用于权限验证）
    
    Returns:
        更新后的房间设备关联列表
    """
    # 获取当前房间的所有设备关联
    current_room_devices = await get_room_devices_by_room(db, room_id)
    current_device_ids = {rd.device_id for rd in current_room_devices}
    
    # 获取新的设备ID列表
    new_device_ids = {device.device_id for device in devices}
    
    # 验证所有设备都属于当前用户
    from app.crud.device import get_device
    for device_id in new_device_ids:
        device = await get_device(db, device_id)
        if not device or device.user_id != user_id:
            raise ValueError(f"设备 {device_id} 不存在或不属于当前用户")
    
    # 验证房间属于当前用户
    from app.crud.room import get_room
    room = await get_room(db, room_id)
    if not room or room.user_id != user_id:
        raise ValueError(f"房间 {room_id} 不存在或不属于当前用户")
    
    # 需要删除的设备关联（存在于当前但不在新列表中）
    devices_to_delete = current_device_ids - new_device_ids
    if devices_to_delete:
        await db.execute(
            delete(RoomDeviceORM).where(
                RoomDeviceORM.room_id == room_id,
                RoomDeviceORM.device_id.in_(devices_to_delete)
            )
        )
    
    # 需要添加的设备关联（存在于新列表但不在当前中）
    devices_to_add = new_device_ids - current_device_ids
    for device_id in devices_to_add:
        # 找到对应的排序信息
        device_info = next((d for d in devices if d.device_id == device_id), None)
        sort_order = device_info.sort_order if device_info else 0
        
        new_room_device = RoomDeviceORM(
            room_id=room_id,
            device_id=device_id,
            sort_order=sort_order
        )
        db.add(new_room_device)
    
    # 需要更新的设备关联（既存在于当前也存在于新列表中）
    devices_to_update = current_device_ids & new_device_ids
    for device_id in devices_to_update:
        # 找到对应的排序信息
        device_info = next((d for d in devices if d.device_id == device_id), None)
        if device_info:
            # 找到现有的房间设备关联
            existing_rd = next((rd for rd in current_room_devices if rd.device_id == device_id), None)
            if existing_rd:
                existing_rd.sort_order = device_info.sort_order
    
    await db.commit()
    
    # 返回更新后的房间设备关联列表
    return await get_room_devices_by_room(db, room_id)


