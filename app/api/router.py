from fastapi import APIRouter
from app.api.endpoints import (
    auth, devices, ws_connections, alerts, members, rooms, 
    device_models, device_params, device_logs, member_device_permissions
)

api_router = APIRouter()

# 认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# 用户和成员路由
api_router.include_router(members.router, prefix="/members", tags=["members"])

# 房间路由
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])

# 设备型号路由
api_router.include_router(device_models.router, prefix="/device-models", tags=["device-models"])

# 设备路由
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])

# 设备参数路由
api_router.include_router(device_params.router, prefix="/device-params", tags=["device-params"])

# 设备日志路由
api_router.include_router(device_logs.router, prefix="/device-logs", tags=["device-logs"])

# 成员设备权限路由
api_router.include_router(member_device_permissions.router, prefix="/member-device-permissions", tags=["member-device-permissions"])

# 告警路由
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])

# WebSocket连接路由
api_router.include_router(ws_connections.router, prefix="/ws", tags=["websocket"])
