from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.room import Room
from app.models.room import RoomCreate, RoomUpdate
from typing import Optional, List

async def get_room(db: AsyncSession, room_id: int) -> Optional[Room]:
    """根据ID获取房间"""
    result = await db.execute(select(Room).filter(Room.id == room_id))
    return result.scalar_one_or_none()

async def get_rooms_by_user(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> List[Room]:
    """获取用户下的所有房间"""
    result = await db.execute(
        select(Room).filter(Room.user_id == user_id).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def create_room(db: AsyncSession, room: RoomCreate, user_id: int) -> Room:
    """创建新房间"""
    db_room = Room(
        user_id=user_id,
        name=room.name
    )
    db.add(db_room)
    await db.commit()
    await db.refresh(db_room)
    return db_room

async def update_room(db: AsyncSession, room_id: int, room: RoomUpdate) -> Optional[Room]:
    """更新房间信息"""
    db_room = await get_room(db, room_id)
    if not db_room:
        return None
    
    update_data = room.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_room, field, value)
    
    await db.commit()
    await db.refresh(db_room)
    return db_room

async def delete_room(db: AsyncSession, room_id: int) -> bool:
    """删除房间"""
    db_room = await get_room(db, room_id)
    if not db_room:
        return False
    
    await db.delete(db_room)
    await db.commit()
    return True
