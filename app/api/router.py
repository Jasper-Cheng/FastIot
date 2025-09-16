from fastapi import APIRouter

api_router = APIRouter()

# 注册端点路由
from app.api.endpoints import auth as auth_endpoints
from app.api.endpoints import users as users_endpoints
from app.api.endpoints import members as members_endpoints
from app.api.endpoints import rooms as rooms_endpoints
from app.api.endpoints import thing_models as thing_models_endpoints
from app.api.endpoints import device_models as device_models_endpoints
from app.api.endpoints import devices as devices_endpoints
from app.api.endpoints import room_devices as room_devices_endpoints
from app.api.endpoints import device_params as device_params_endpoints
from app.api.endpoints import device_networks as device_networks_endpoints
from app.api.endpoints import device_logs as device_logs_endpoints
from app.api.endpoints import alerts as alerts_endpoints
from app.api.endpoints import member_device_permissions as member_device_permissions_endpoints

api_router.include_router(auth_endpoints.router, prefix="/auth", tags=["auth"])
api_router.include_router(users_endpoints.router, prefix="/users", tags=["users"])
api_router.include_router(members_endpoints.router, prefix="/members", tags=["members"])
api_router.include_router(rooms_endpoints.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(thing_models_endpoints.router, prefix="/thing-models", tags=["thing-models"])
api_router.include_router(device_models_endpoints.router, prefix="/device-models", tags=["device-models"])
api_router.include_router(devices_endpoints.router, prefix="/devices", tags=["devices"])
api_router.include_router(room_devices_endpoints.router, prefix="/room-devices", tags=["room-devices"])
api_router.include_router(device_params_endpoints.router, prefix="/device-params", tags=["device-params"])
api_router.include_router(device_networks_endpoints.router, prefix="/device-networks", tags=["device-networks"])
api_router.include_router(device_logs_endpoints.router, prefix="/device-logs", tags=["device-logs"])
api_router.include_router(alerts_endpoints.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(member_device_permissions_endpoints.router, prefix="/member-device-permissions", tags=["member-device-permissions"])

# 基础路由 - 可以在这里添加简单的健康检查等
@api_router.get("/health")
async def health_check():
    return {"status": "ok", "message": "Service is running"}