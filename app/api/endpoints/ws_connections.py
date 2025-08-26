from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json

router = APIRouter()

# 存储活跃的WebSocket连接
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@router.get("/status", tags=["websocket"])
def get_connection_status():
    """获取当前WebSocket连接状态"""
    return {
        "active_connections": len(manager.active_connections),
        "status": "running"
    }

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    """WebSocket连接端点"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 处理接收到的消息
            message = json.loads(data)
            # 广播消息给所有连接的客户端
            await manager.broadcast(f"Client {client_id}: {message}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client {client_id} left the chat")