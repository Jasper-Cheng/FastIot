from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user

api_router = APIRouter()

# 注册端点路由
from app.api.endpoints import auth as auth_endpoints
from app.api.endpoints import users as users_endpoints
from app.api.endpoints import members as members_endpoints
from app.api.endpoints import rooms as rooms_endpoints
from app.api.endpoints import device_thing_models as device_thing_models_endpoints
from app.api.endpoints import device_models as device_models_endpoints
from app.api.endpoints import devices as devices_endpoints
from app.api.endpoints import room_devices as room_devices_endpoints
from app.api.endpoints import device_networks as device_networks_endpoints
from app.api.endpoints import device_logs as device_logs_endpoints
from app.api.endpoints import device_messages as device_messages_endpoints
from app.api.endpoints import member_device_permissions as member_device_permissions_endpoints
from app.api.endpoints import admins as admins_endpoints
from app.api.endpoints import check_in as check_in_endpoints
from app.api.endpoints import points as points_endpoints
from app.api.endpoints import websocket as websocket_endpoints

api_router.include_router(auth_endpoints.router, prefix="/auth", tags=["auth"])
api_router.include_router(users_endpoints.router, prefix="/users", tags=["users"], dependencies=[Depends(get_current_user)])
api_router.include_router(members_endpoints.router, prefix="/members", tags=["members"], dependencies=[Depends(get_current_user)])
api_router.include_router(rooms_endpoints.router, prefix="/rooms", tags=["rooms"], dependencies=[Depends(get_current_user)])
api_router.include_router(device_thing_models_endpoints.router, prefix="/device-thing-models", tags=["device-thing-models"], dependencies=[Depends(get_current_user)])
api_router.include_router(device_models_endpoints.router, prefix="/device-models", tags=["device-models"], dependencies=[Depends(get_current_user)])
api_router.include_router(devices_endpoints.router, prefix="/devices", tags=["devices"], dependencies=[Depends(get_current_user)])
api_router.include_router(room_devices_endpoints.router, prefix="/room-devices", tags=["room-devices"], dependencies=[Depends(get_current_user)])
api_router.include_router(device_networks_endpoints.router, prefix="/device-networks", tags=["device-networks"], dependencies=[Depends(get_current_user)])
api_router.include_router(device_logs_endpoints.router, prefix="/device-logs", tags=["device-logs"], dependencies=[Depends(get_current_user)])
api_router.include_router(device_messages_endpoints.router, prefix="/device-messages", tags=["device-messages"], dependencies=[Depends(get_current_user)])
api_router.include_router(member_device_permissions_endpoints.router, prefix="/member-device-permissions", tags=["member-device-permissions"], dependencies=[Depends(get_current_user)])
api_router.include_router(admins_endpoints.router, prefix="/admins", tags=["admins"], dependencies=[Depends(get_current_user)])
api_router.include_router(check_in_endpoints.router, prefix="/check-in", tags=["check-in"], dependencies=[Depends(get_current_user)])
api_router.include_router(points_endpoints.router, prefix="/points", tags=["points"], dependencies=[Depends(get_current_user)])
api_router.include_router(websocket_endpoints.router, prefix="/ws", tags=["websocket"])

# 基础路由 - 可以在这里添加简单的健康检查等
@api_router.get("/health", dependencies=[Depends(get_current_user)])
async def health_check():
    return {"status": "ok", "message": "Service is running"}