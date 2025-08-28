from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.models.user import User
from app.api.endpoints.auth import get_current_user
from app.services.websocket_service import manager
import json

router = APIRouter()

@router.get("/status", tags=["websocket"])
async def get_connection_status(current_user: User = Depends(get_current_user)):
    """获取当前WebSocket连接状态"""
    return {
        "active_connections": len(manager.active_connections),
        "status": "running",
        "user": current_user.username,
        "user_id": current_user.id
    }

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket连接端点"""
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 处理不同类型的消息
            msg_type = message.get("type")
            
            if msg_type == "subscribe_device":
                # 订阅设备状态
                device_id = message.get("device_id")
                if device_id:
                    manager.subscribe_to_device(user_id, device_id)
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "subscription_confirmed",
                            "device_id": device_id,
                            "message": f"Subscribed to device {device_id}"
                        }),
                        user_id
                    )
                    
            elif msg_type == "unsubscribe_device":
                # 取消订阅设备状态
                device_id = message.get("device_id")
                if device_id:
                    manager.unsubscribe_from_device(user_id, device_id)
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "unsubscription_confirmed",
                            "device_id": device_id,
                            "message": f"Unsubscribed from device {device_id}"
                        }),
                        user_id
                    )
                    
            elif msg_type == "ping":
                # 心跳检测
                await manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": message.get("timestamp")}),
                    user_id
                )
                
            else:
                # 其他消息类型
                await manager.send_personal_message(
                    json.dumps({
                        "type": "message_received",
                        "original_message": message
                    }),
                    user_id
                )
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        print(f"❌ [WS] 用户 {user_id} 断开连接")