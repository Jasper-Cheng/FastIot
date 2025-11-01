"""
WebSocket API端点
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_tool import websocket_tool
from jose import JWTError, jwt
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.crud.account import get_account
from typing import List

router = APIRouter()


async def get_family_clients(user_id: int, db: AsyncSession) -> List[str]:
    """根据user_id获取family相关的所有client_id"""
    family_clients = []
    
    # 获取owner的client_id (user的role固定为"owner")
    from app.crud.user import get_user
    owner = await get_user(db, user_id)
    if owner:
        owner_client_id = f"owner_{owner.id}"
        family_clients.append(owner_client_id)
    
    # 获取所有member的client_id (member的role固定为"member")
    from app.crud.member import get_members_by_user
    members = await get_members_by_user(db, user_id)
    for member in members:
        member_client_id = f"member_{member.id}"
        family_clients.append(member_client_id)
    
    return family_clients



@router.websocket("/user")
async def user_websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """用户专用WebSocket连接端点（需要身份验证）"""
    # 获取数据库会话
    async for db in get_db():
        # 解析token
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            account_id: int | None = payload.get("account_id")
            real_id: int | None = payload.get("id")
            role: str | None = payload.get("role")
            user_id: int | None = payload.get("user_id")

            if not account_id or not real_id or not role:
                await websocket.close(code=4001, reason="身份验证失败")
                return

            # 验证role是否为有效值
            if role not in ["owner", "member", "admin"]:
                await websocket.close(code=4001, reason="未知用户类型")
                return

            if user_id is None or role == "admin":
                #管理员没有user_id
                await websocket.close(code=4001, reason="管理员不允许连接")
                return
            
            # 验证account是否存在
            account = await get_account(db, account_id)
            if not account:
                await websocket.close(code=4001, reason="身份验证失败")
                return
            
            # 验证token中的role是否与account的role匹配（转换为字符串比较）
            if str(account.role) != role:
                await websocket.close(code=4001, reason="角色不匹配")
                return
            
            # 使用token中的role和id构建client_id
            client_id = f"{role}_{real_id}"
            
            # 获取family相关的所有client_id
            family_clients = await get_family_clients(user_id, db)
            
            # 连接成功，设置客户端ID和元数据
            metadata = {
                "client_id": client_id,
                "connection_type": role,
                "family_clients": family_clients
            }
            
            await websocket_tool.connect(websocket, client_id, metadata)
            
            # 输出连接成功信息
            print(f"✅ [WebSocket] 连接成功!")
            print(f"   Metadata: {metadata}")
            
            # 更新当前连接的family_clients活跃状态
            websocket_tool.update_family_clients_for_client(client_id)
           
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
            
        except JWTError:
            await websocket.close(code=4001, reason="身份验证失败")
            return
