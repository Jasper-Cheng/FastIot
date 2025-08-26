import json
import logging
from datetime import datetime
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# 存储活跃的WebSocket连接
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}  # user_id -> WebSocket
        self.device_connections: Dict[int, List[int]] = {}  # device_id -> [user_ids]

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected to WebSocket")

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        # 从设备连接中移除用户
        for device_id, user_ids in self.device_connections.items():
            if user_id in user_ids:
                user_ids.remove(user_id)
        logger.info(f"User {user_id} disconnected from WebSocket")

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

    async def broadcast(self, message: str):
        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                # 移除断开的连接
                self.disconnect(user_id)

    async def send_to_device_users(self, device_id: int, message: str):
        """向关注特定设备的用户发送消息"""
        if device_id in self.device_connections:
            for user_id in self.device_connections[device_id]:
                await self.send_personal_message(message, user_id)

    def subscribe_to_device(self, user_id: int, device_id: int):
        """用户订阅设备状态"""
        if device_id not in self.device_connections:
            self.device_connections[device_id] = []
        if user_id not in self.device_connections[device_id]:
            self.device_connections[device_id].append(user_id)
        logger.info(f"User {user_id} subscribed to device {device_id}")

    def unsubscribe_from_device(self, user_id: int, device_id: int):
        """用户取消订阅设备状态"""
        if device_id in self.device_connections and user_id in self.device_connections[device_id]:
            self.device_connections[device_id].remove(user_id)
        logger.info(f"User {user_id} unsubscribed from device {device_id}")

# 全局连接管理器实例
manager = ConnectionManager()

# 设备状态推送函数（供其他模块调用）
async def push_device_status(device_id: int, status_data: dict):
    """推送设备状态到订阅的用户"""
    message = json.dumps({
        "type": "device_status_update",
        "device_id": device_id,
        "status": status_data,
        "timestamp": status_data.get("timestamp")
    })
    await manager.send_to_device_users(device_id, message)

async def push_device_online_status(device_id: int, is_online: bool):
    """推送设备在线状态到订阅的用户"""
    message = json.dumps({
        "type": "device_online_status",
        "device_id": device_id,
        "online": is_online,
        "timestamp": datetime.now().isoformat()
    })
    await manager.send_to_device_users(device_id, message)
