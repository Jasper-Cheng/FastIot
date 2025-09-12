from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.dependencies import get_db
from app.crud.room import (
    get_room, get_rooms_by_user, create_room, update_room, delete_room
)
from app.models.room import Room, RoomCreate, RoomUpdate, RoomWithDevices
from app.models.user import User
from app.api.endpoints.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[Room], tags=["rooms"])
async def read_rooms(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的房间列表"""
    rooms = await get_rooms_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return rooms

@router.post("/", response_model=Room, tags=["rooms"])
async def create_new_room(
    room: RoomCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新房间"""
    # 确保房间属于当前用户
    if room.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能为其他用户创建房间"
        )
    
    return await create_room(db=db, room=room)

@router.get("/{room_id}", response_model=Room, tags=["rooms"])
async def read_room(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定房间信息"""
    room = await get_room(db, room_id=room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    # 检查房间是否属于当前用户
    if room.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问该房间信息"
        )
    
    return room

@router.put("/{room_id}", response_model=Room, tags=["rooms"])
async def update_room_info(
    room_id: int,
    room: RoomUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新房间信息"""
    db_room = await get_room(db, room_id=room_id)
    if db_room is None:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    # 检查房间是否属于当前用户
    if db_room.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改该房间信息"
        )
    
    updated_room = await update_room(db=db, room_id=room_id, room=room)
    if updated_room is None:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    return updated_room

@router.delete("/{room_id}", tags=["rooms"])
async def delete_room_info(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除房间"""
    db_room = await get_room(db, room_id=room_id)
    if db_room is None:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    # 检查房间是否属于当前用户
    if db_room.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除该房间"
        )
    
    success = await delete_room(db=db, room_id=room_id)
    if not success:
        raise HTTPException(status_code=404, detail="房间不存在")
    
    return {"message": "房间删除成功"}
