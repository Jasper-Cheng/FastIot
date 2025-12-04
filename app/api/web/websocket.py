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
from app.crud.family_member import get_family_members_by_account

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
            role: str | None = payload.get("role")
            platform: str | None = payload.get("platform", "web")  # 从token中获取平台信息，默认为"web"

            if not account_id or not role:
                await websocket.close(code=4001, reason="身份验证失败")
                return

            # 验证role是否为有效值
            if role not in ["user", "admin"]:
                await websocket.close(code=4001, reason="未知用户类型")
                return

            if role == "admin":
                # 管理员不允许连接（如果需要支持管理员，可以后续添加）
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
            
            # 使用token中的role和account_id构建client_id
            client_id = f"{role}_{account_id}"

            # 检查是否已经连接，如果已连接则先发送family消息并断开旧连接
            if websocket_tool.is_client_connected(client_id):
                print(f"⚠️ [WebSocket] 客户端 {client_id} 已存在连接，正在发送强制退出family消息并断开旧连接")
                
                # 发送family消息给所有family成员（包括旧连接）
                try:
                    await websocket_tool.send_family_message(
                        client_id=client_id,
                        message_type="force.logout",
                        data={
                            "senderId": account_id,
                            "senderRole": role,
                            "title": "强制退出",
                            "message": f"{account.nickname or account.phone} 的账号登录，当前将被强制退出",
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
            
            # 获取family相关的所有client_id（账号所在的所有家庭的成员）
            family_clients = []
            
            # 添加当前账号的client_id
            family_clients.append(f"user_{account_id}")
            
            # 获取账号所在的所有家庭
            from app.crud.family import get_families_by_account
            families = await get_families_by_account(db, account_id)
            
            # 获取所有家庭成员
            for family in families:
                from app.crud.family_member import get_family_members_by_family
                members = await get_family_members_by_family(db, family.id)
                for member in members:
                    member_client_id = f"user_{member.account_id}"
                    if member_client_id not in family_clients:
                        family_clients.append(member_client_id)
            
            # 连接成功，设置客户端ID和元数据
            metadata = {
                "client_id": client_id,
                "role": role,
                "real_id": account_id,
                "family_clients": family_clients
            }
            
            await websocket_tool.connect(websocket, client_id, metadata)

            # 活跃的family_clients_ids
            active_family_clients_ids = []
            for family_client_id in family_clients:
                if family_client_id in websocket_tool.active_connections:
                    active_family_clients_ids.append(family_client_id.split("_")[1])

            # 发送用户连接消息给所有family_clients
            try:
                await websocket_tool.send_family_message(
                    client_id=client_id,
                    message_type="connect",
                    data={
                        "senderId": account_id,
                        "senderRole": role,
                        "title": "用户连接",
                        "message": f"{account.nickname or account.phone} 已连接",
                        "level": "normal",
                        "connectUserIds": active_family_clients_ids
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
                            "senderId": account_id,
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
                            "senderId": account_id,
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
