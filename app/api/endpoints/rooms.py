from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db.session import get_db
from app.crud.room import get_room, get_rooms_by_user, create_room, update_room, delete_room
from app.models.room import Room, RoomCreate, RoomUpdate, RoomInDB

router = APIRouter()

@router.get("/", response_model=List[RoomInDB])
async def get_rooms(
    user_id: Optional[int] = Query(None, description="用户ID，不指定则获取当前用户的房间"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取房间列表
    
    - 如果不指定user_id，则返回当前用户的房间
    - 如果指定user_id，则返回指定用户的房间（需要权限验证）
    """
    target_user_id = user_id if user_id is not None else None
    
    # 如果指定了其他用户ID，这里可以添加权限验证逻辑
    # 目前简化为允许访问
    
    rooms = await get_rooms_by_user(db, target_user_id, skip, limit)
    return rooms

@router.get("/{room_id}", response_model=RoomInDB)
async def get_room_detail(
    room_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    获取房间详情
    """
    room = await get_room(db, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 这里可以添加权限验证，检查当前用户是否有权限访问该房间
    # 目前简化为允许访问
    
    return room

@router.post("/", response_model=RoomInDB)
async def create_new_room(
    room: RoomCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    创建新房间
    """
    # 验证用户ID是否存在（这里可以添加用户存在性检查）
    # 目前简化为直接创建
    
    db_room = await create_room(db, room)
    return db_room

@router.put("/{room_id}", response_model=RoomInDB)
async def update_room_info(
    room_id: int,
    room_update: RoomUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新房间信息
    """
    # 检查房间是否存在
    existing_room = await get_room(db, room_id)
    if not existing_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 这里可以添加权限验证，检查当前用户是否有权限修改该房间
    # 目前简化为允许修改
    
    updated_room = await update_room(db, room_id, room_update)
    if not updated_room:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新房间失败"
        )
    
    return updated_room

@router.delete("/{room_id}")
async def delete_room_by_id(
    room_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    删除房间
    """
    # 检查房间是否存在
    existing_room = await get_room(db, room_id)
    if not existing_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 这里可以添加权限验证，检查当前用户是否有权限删除该房间
    # 目前简化为允许删除
    
    success = await delete_room(db, room_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除房间失败"
        )
    
    return {"message": "房间删除成功"}
