"""
WebSocket API端点
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
from app.services.websocket_tool import websocket_tool
from app.api.dependencies import get_current_user
from app.models.account import Account
from jose import JWTError, jwt
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.crud.user import get_user
from app.crud.member import get_member
from app.crud.admin import get_admin
from app.db.models.user import User
from app.db.models.member import Member
from app.db.models.admin import Admin
from app.utils.time_utils import get_local_time
from typing import Union

router = APIRouter()


async def authenticate_websocket_user(token: str, db: AsyncSession) -> Union[User, Member, Admin, None]:
    """WebSocket专用的用户身份验证函数"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        account_id: int | None = payload.get("account_id")
        user_id: int | None = payload.get("id")
        role: str | None = payload.get("role")
        
        if not account_id or not user_id or not role:
            return None
            
        # 根据role获取对应的用户信息
        if role == "member":
            member = await get_member(db, user_id)
            return member
        elif role == "owner":
            user = await get_user(db, user_id)
            return user
        elif role == "admin":
            admin = await get_admin(db, user_id)
            return admin
        else:
            return None
    except JWTError:
        return None




@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """WebSocket连接端点（需要身份验证）"""
    # 获取数据库会话
    async for db in get_db():
        # 验证用户身份
        current_user = await authenticate_websocket_user(token, db)
        if not current_user:
            await websocket.close(code=4001, reason="身份验证失败")
            return
        
        # 根据用户类型和ID生成client_id
        role = current_user.__class__.__name__.lower()
        client_id = f"{role}_{current_user.id}"
        
        # 连接成功，设置客户端ID和元数据
        metadata = {
            "client_id": client_id,
            "connection_type": role,
            "authenticated_user": {
                "id": current_user.id,
                "role": role
            }
        }
        
        await websocket_tool.connect(websocket, client_id, metadata)
        
        try:
            while True:
                # 接收消息
                data = await websocket.receive_text()
                await websocket_tool.handle_message(client_id, data)
                
        except WebSocketDisconnect:
            websocket_tool.disconnect(client_id)
        except Exception as e:
            print(f"❌ [WebSocket] 连接异常: {e}")
            websocket_tool.disconnect(client_id)
        break


@router.websocket("/device/{device_id}")
async def device_websocket_endpoint(websocket: WebSocket, device_id: str, token: str = Query(...)):
    """设备专用WebSocket连接端点（需要身份验证）"""
    # 获取数据库会话
    async for db in get_db():
        # 验证用户身份
        current_user = await authenticate_websocket_user(token, db)
        if not current_user:
            await websocket.close(code=4001, reason="身份验证失败")
            return
        
        # 根据用户类型和ID生成client_id
        role = current_user.__class__.__name__.lower()
        client_id = f"{role}_{current_user.id}"
        
        # 连接成功，设置客户端ID和元数据
        metadata = {
            "client_id": client_id,
            "connection_type": role,
            "authenticated_user": {
                "id": current_user.id,
                "role": role
            }
        }
        
        await websocket_tool.connect(websocket, client_id, metadata)
        
        try:
            while True:
                data = await websocket.receive_text()
                await websocket_tool.handle_message(client_id, data)
                
        except WebSocketDisconnect:
            websocket_tool.disconnect(client_id)
        except Exception as e:
            print(f"❌ [WebSocket] 设备连接异常: {e}")
            websocket_tool.disconnect(client_id)
        break


@router.websocket("/user/{user_id}")
async def user_websocket_endpoint(websocket: WebSocket, user_id: str, token: str = Query(...)):
    """用户专用WebSocket连接端点（需要身份验证）"""
    # 获取数据库会话
    async for db in get_db():
        # 验证用户身份
        current_user = await authenticate_websocket_user(token, db)
        if not current_user:
            await websocket.close(code=4001, reason="身份验证失败")
            return
        
        # 验证user_id是否与当前用户匹配
        if isinstance(current_user, User):
            if str(current_user.id) != user_id:
                await websocket.close(code=4003, reason="用户ID不匹配")
                return
        elif isinstance(current_user, Member):
            if str(current_user.user_id) != user_id:
                await websocket.close(code=4003, reason="用户ID不匹配")
                return
        elif isinstance(current_user, Admin):
            # 管理员可以连接任何用户的WebSocket
            pass
        else:
            await websocket.close(code=4001, reason="未知用户类型")
            return
        
        # 根据用户类型和ID生成client_id
        role = current_user.__class__.__name__.lower()
        client_id = f"{role}_{current_user.id}"
        
        # 连接成功，设置客户端ID和元数据
        metadata = {
            "client_id": client_id,
            "connection_type": role,
            "authenticated_user": {
                "id": current_user.id,
                "role": role
            }
        }
        
        await websocket_tool.connect(websocket, client_id, metadata)
        
        try:
            while True:
                data = await websocket.receive_text()
                await websocket_tool.handle_message(client_id, data)
                
        except WebSocketDisconnect:
            websocket_tool.disconnect(client_id)
        except Exception as e:
            print(f"❌ [WebSocket] 用户连接异常: {e}")
            websocket_tool.disconnect(client_id)
        break
