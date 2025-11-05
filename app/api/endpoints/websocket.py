"""
WebSocket API端点
"""
import uuid
import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_tool import websocket_tool
from jose import JWTError, jwt
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.crud.account import get_account
from app.crud.user import get_user
from app.crud.member import get_members_by_user

router = APIRouter()



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

            # 检查是否已经连接，如果已连接则先发送family消息并断开旧连接
            if websocket_tool.is_client_connected(client_id):
                print(f"⚠️ [WebSocket] 客户端 {client_id} 已存在连接，正在发送强制退出family消息并断开旧连接")
                
                # 发送family消息给所有family成员（包括旧连接）
                try:
                    await websocket_tool.send_family_message(
                        client_id=client_id,
                        message_type="force.logout",
                        data={
                            "senderId": real_id,
                            "senderRole": role,
                            "title": "强制退出",
                            "message": f"{account.nickname or account.phone} 的账号在其他web平台登录，当前将被强制退出",
                            "level": "warning",
                            "reason": "新设备登录，当前连接被强制退出"
                        }
                    )
                    # 等待一小段时间确保消息发送完成
                    await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"⚠️ [WebSocket] 发送强制退出family消息失败: {e}")
                
                # 断开旧连接
                await websocket_tool._force_disconnect(client_id)
            
            # 获取family相关的所有client_id
            family_clients = []
            
            # 获取owner的client_id (user的role固定为"owner")
            owner = await get_user(db, user_id)
            if owner:
                owner_client_id = f"owner_{owner.id}"
                family_clients.append(owner_client_id)
            
            # 获取所有member的client_id (member的role固定为"member")
            members = await get_members_by_user(db, user_id)
            for member in members:
                member_client_id = f"member_{member.id}"
                family_clients.append(member_client_id)
            
            # 连接成功，设置客户端ID和元数据
            metadata = {
                "client_id": client_id,
                "role": role,
                "real_id": real_id,
                "family_clients": family_clients
            }
            
            await websocket_tool.connect(websocket, client_id, metadata)
            
            # 更新当前连接的family_clients活跃状态
            websocket_tool.update_family_clients_for_client(client_id)
            
            # 发送用户连接消息给所有family_clients
            try:
                # 获取所有在线的用户ID（从family_clients中筛选出在线的，包括当前用户）
                connect_user_ids = []
                for family_client_id in family_clients:
                    if family_client_id in websocket_tool.active_connections:
                        # 从连接元数据中获取real_id
                        if family_client_id in websocket_tool.connection_metadata:
                            metadata_info = websocket_tool.connection_metadata[family_client_id]
                            if "metadata" in metadata_info:
                                family_real_id = metadata_info["metadata"].get("real_id")
                                if family_real_id is not None:
                                    connect_user_ids.append(family_real_id)
                
                await websocket_tool.send_family_message(
                    client_id=client_id,
                    message_type="connect",
                    data={
                        "senderId": real_id,
                        "senderRole": role,
                        "title": "用户连接",
                        "message": f"{account.nickname or account.phone} 已连接",
                        "level": "normal",
                        "connectUserIds": connect_user_ids
                    }
                )
            except Exception as e:
                # 发送消息失败不影响连接流程
                print(f"发送连接消息失败: {e}")
           
            try:
                while True:
                    data = await websocket.receive_text()
                    await websocket_tool.handle_message(client_id, data)
                    
            except WebSocketDisconnect:
                # 在断开前发送断开连接消息
                try:
                    await websocket_tool.send_family_message(
                        client_id=client_id,
                        message_type="disconnect",
                        data={
                            "senderId": real_id,
                            "senderRole": role,
                            "title": "用户断开连接",
                            "message": f"{account.nickname or account.phone} 已断开连接",
                            "level": "normal"
                        }
                    )
                except Exception as e:
                    # 发送消息失败不影响断开流程
                    print(f"发送断开连接消息失败: {e}")
                
                await websocket_tool.disconnect(client_id)
            except Exception as e:
                print(f"❌ [WebSocket] 用户连接异常: {e}")
                
                # 在断开前发送断开连接消息
                try:
                    await websocket_tool.send_family_message(
                        client_id=client_id,
                        message_type="disconnect",
                        data={
                            "senderId": real_id,
                            "senderRole": role,
                            "title": "用户断开连接",
                            "message": f"{account.nickname or account.phone} 已断开连接",
                            "level": "normal"
                        }
                    )
                except Exception as e2:
                    # 发送消息失败不影响断开流程
                    print(f"发送断开连接消息失败: {e2}")
                
                await websocket_tool.disconnect(client_id)
            break
            
        except JWTError:
            await websocket.close(code=4001, reason="身份验证失败")
            return
