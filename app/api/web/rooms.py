from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.session import get_db
from app.crud.room import get_room, get_rooms_by_user, create_room, delete_room
from app.models.room import RoomCreate, RoomInDB
from app.crud.user import get_user
from app.crud.user_operation_log import user_operation_log
from app.models.user_operation_log import UserOperationLogCreate, OperationTypeEnum
from app.api.dependencies import get_current_token
from app.models.account import AccountRole
from app.services.websocket_tool import websocket_tool
router = APIRouter()

@router.get("/", response_model=List[RoomInDB])
async def get_rooms(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """
    获取当前用户的房间列表
    """
    user_id = token_info["user_id"]
    rooms = await get_rooms_by_user(db, user_id, skip, limit)
    return rooms

@router.post("/", response_model=RoomInDB)
async def create_new_room(
    room: RoomCreate,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token)
):
    """
    创建新房间
    """
    # 从 token 中获取 user_id
    user_id = token_info["user_id"]

    if token_info["role"] != AccountRole.owner:
        raise HTTPException(status_code=403, detail="无权创建房间")

    # 验证用户ID是否存在
    owner = await get_user(db, user_id)
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="归属的用户不存在"
        )
    
    # 创建房间，直接传入 user_id
    db_room = await create_room(db, room, user_id)
    
    # 记录创建房间操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.room_add,
                description=f"创建房间：{db_room.name}",
                extra={
                    "room_id": db_room.id,
                    "room_name": db_room.name,
                    "user_id": user_id
                }
            ),
            account_id=owner.account_id
        )
    except Exception as e:
        # 记录操作失败不影响创建流程
        print(f"记录创建房间操作失败: {e}")
    
    # 发送family消息通知创建房间
    try:
        role = token_info.get("role")
        real_id = token_info.get("id")
        platform = token_info.get("platform", "web")
        if role and real_id is not None:
            client_id = f"{role}_{real_id}_{platform}"
            await websocket_tool.send_family_message(
                client_id=client_id,
                message_type="room.create",
                data={
                    "senderId": real_id,
                    "senderRole": role,
                    "title": "创建房间",
                    "message": f"已创建房间：{db_room.name}",
                    "level": "normal",
                    "roomData": {
                        "name": db_room.name,
                        "id": db_room.id,
                        "user_id": db_room.user_id,
                        "created_at": db_room.created_at.isoformat() if db_room.created_at else None,
                        "devices": []
                    }
                }
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送创建房间通知失败: {e}")
    
    return db_room

@router.delete("/{room_id}")
async def delete_room_by_id(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    token_info: dict = Depends(get_current_token),
):
    """
    删除房间
    """
    if token_info["role"] != AccountRole.owner:
        raise HTTPException(status_code=403, detail="无权删除房间")
    
    # 检查房间是否存在
    existing_room = await get_room(db, room_id)
    if not existing_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 记录删除前的房间信息
    room_name = existing_room.name
    user_id = existing_room.user_id
    
    if user_id != token_info["user_id"]:
        raise HTTPException(status_code=403, detail="无权删除此房间")
    
    success = await delete_room(db, room_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除房间失败"
        )
    
    # 记录删除房间操作
    try:
        await user_operation_log.create(
            db=db,
            obj_in=UserOperationLogCreate(
                operation_type=OperationTypeEnum.room_delete,
                description=f"删除房间：{room_name}",
                extra={
                    "room_id": room_id,
                    "room_name": room_name,
                    "user_id": user_id
                }
            ),
            account_id=token_info["account_id"]
        )
    except Exception as e:
        # 记录操作失败不影响删除流程
        print(f"记录删除房间操作失败: {e}")
    
    # 发送family消息通知删除房间
    try:
        role = token_info.get("role")
        real_id = token_info.get("id")
        platform = token_info.get("platform", "web")
        if role and real_id is not None:
            client_id = f"{role}_{real_id}_{platform}"
            await websocket_tool.send_family_message(
                client_id=client_id,
                message_type="room.delete",
                data={
                    "senderId": real_id,
                    "senderRole": role,
                    "title": "删除房间",
                    "message": f"已删除房间：{room_name}",
                    "level": "normal",
                    "roomId": room_id,
                    "roomName": room_name
                }
            )
    except Exception as e:
        # 发送消息失败不影响业务流程
        print(f"发送删除房间通知失败: {e}")
    
    return {"message": "房间删除成功"}