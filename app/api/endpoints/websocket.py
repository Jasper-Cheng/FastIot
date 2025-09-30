"""
WebSocket API端点
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
from app.services.websocket_tool import websocket_tool
from app.api.dependencies import get_current_user
from app.models.account import Account

router = APIRouter()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket连接端点"""
    await websocket_tool.connect(websocket, client_id)
    
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


@router.websocket("/ws/device/{device_id}")
async def device_websocket_endpoint(websocket: WebSocket, device_id: str):
    """设备专用WebSocket连接端点"""
    client_id = f"device_{device_id}"
    metadata = {
        "device_id": device_id,
        "connection_type": "device"
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


@router.websocket("/ws/user/{user_id}")
async def user_websocket_endpoint(websocket: WebSocket, user_id: str):
    """用户专用WebSocket连接端点"""
    client_id = f"user_{user_id}"
    metadata = {
        "user_id": user_id,
        "connection_type": "user"
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
