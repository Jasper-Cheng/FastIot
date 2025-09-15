from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from app.db.models.room_device import RoomDevice as RoomDeviceORM
from app.models.room_device import RoomDeviceCreate, RoomDeviceUpdate


async def get_room_device(db: AsyncSession, rd_id: int) -> Optional[RoomDeviceORM]:
    result = await db.execute(select(RoomDeviceORM).filter(RoomDeviceORM.id == rd_id))
    return result.scalar_one_or_none()


async def get_room_devices_by_room(db: AsyncSession, room_id: int) -> List[RoomDeviceORM]:
    result = await db.execute(select(RoomDeviceORM).filter(RoomDeviceORM.room_id == room_id).order_by(RoomDeviceORM.sort_order, RoomDeviceORM.id))
    return result.scalars().all()


async def get_room_devices_by_device(db: AsyncSession, device_id: int) -> List[RoomDeviceORM]:
    result = await db.execute(select(RoomDeviceORM).filter(RoomDeviceORM.device_id == device_id).order_by(RoomDeviceORM.sort_order, RoomDeviceORM.id))
    return result.scalars().all()


async def create_room_device(db: AsyncSession, payload: RoomDeviceCreate) -> RoomDeviceORM:
    rd = RoomDeviceORM(
        room_id=payload.room_id,
        device_id=payload.device_id,
        sort_order=payload.sort_order or 0,
    )
    db.add(rd)
    await db.commit()
    await db.refresh(rd)
    return rd


async def update_room_device(db: AsyncSession, rd_id: int, payload: RoomDeviceUpdate) -> Optional[RoomDeviceORM]:
    rd = await get_room_device(db, rd_id)
    if not rd:
        return None
    data = payload.dict(exclude_unset=True)
    if "sort_order" in data and data["sort_order"] is not None:
        rd.sort_order = data["sort_order"]
    await db.commit()
    await db.refresh(rd)
    return rd


async def delete_room_device(db: AsyncSession, rd_id: int) -> bool:
    rd = await get_room_device(db, rd_id)
    if not rd:
        return False
    await db.delete(rd)
    await db.commit()
    return True


