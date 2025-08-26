from fastapi import APIRouter
from app.api.endpoints import auth, devices, device_data, ws_connections

api_router = APIRouter()

# 认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# 设备路由
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])

# 设备数据路由
api_router.include_router(device_data.router, prefix="/device-data", tags=["device-data"])

# WebSocket连接路由
api_router.include_router(ws_connections.router, prefix="/ws", tags=["websocket"])
