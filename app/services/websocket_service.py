import json
from datetime import datetime
from typing import Dict, List, Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.device_subscriptions: Dict[int, Set[int]] = {}  # user_id -> set of device_ids

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"✅ [WS] 用户 {user_id} 连接到 WebSocket")

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.device_subscriptions:
            del self.device_subscriptions[user_id]
        print(f"❌ [WS] 用户 {user_id} 断开 WebSocket 连接")

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
            except Exception as e:
                print(f"❌ [WS] 发送消息给用户 {user_id} 失败: {e}")
                self.disconnect(user_id)

    async def send_to_device_users(self, device_id: int, message: str):
        """向订阅了指定设备的所有用户发送消息"""
        for user_id, device_ids in self.device_subscriptions.items():
            if device_id in device_ids:
                await self.send_personal_message(message, user_id)

    def subscribe_to_device(self, user_id: int, device_id: int):
        """用户订阅设备状态"""
        if user_id not in self.device_subscriptions:
            self.device_subscriptions[user_id] = set()
        self.device_subscriptions[user_id].add(device_id)
        print(f"✅ [WS] 用户 {user_id} 订阅设备 {device_id}")

    def unsubscribe_from_device(self, user_id: int, device_id: int):
        """用户取消订阅设备状态"""
        if user_id in self.device_subscriptions:
            self.device_subscriptions[user_id].discard(device_id)
        print(f"❌ [WS] 用户 {user_id} 取消订阅设备 {device_id}")

# 全局连接管理器实例
manager = ConnectionManager()

async def push_device_status(device_id: int, status_data: dict):
    """推送设备状态到订阅的用户"""
    message = json.dumps({
        "type": "device_status",
        "device_id": device_id,
        "status": status_data,
        "timestamp": datetime.now().isoformat()
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
