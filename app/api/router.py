from fastapi import APIRouter
from app.api.endpoints import auth, devices, device_data, ws_connections, alerts, alert_rules

api_router = APIRouter()

# 认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# 设备路由
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])

# 设备数据路由
api_router.include_router(device_data.router, prefix="/device-data", tags=["device-data"])

# 告警路由
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])

# 告警规则路由
api_router.include_router(alert_rules.router, prefix="/alert-rules", tags=["alert-rules"])

# WebSocket连接路由
api_router.include_router(ws_connections.router, prefix="/ws", tags=["websocket"])
