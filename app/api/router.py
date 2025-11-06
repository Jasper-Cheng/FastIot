from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_token

api_router = APIRouter()

# 创建 web 路由器，用于统一管理所有 web API
web_router = APIRouter(tags=["web"])

# 注册端点路由
from app.api.web import auth as auth_endpoints
from app.api.web import users as users_endpoints
from app.api.web import members as members_endpoints
from app.api.web import rooms as rooms_endpoints
from app.api.web import devices as devices_endpoints
from app.api.web import room_devices as room_devices_endpoints
from app.api.web import device_messages as device_messages_endpoints
from app.api.web import member_device_permissions as member_device_permissions_endpoints
from app.api.web import check_in as check_in_endpoints
from app.api.web import points as points_endpoints
from app.api.web import system_message as system_message_endpoints
from app.api.web import version_info as version_info_endpoints
from app.api.web import feedback as feedback_endpoints
from app.api.web import websocket as websocket_endpoints

# 将所有路由添加到 web_router
web_router.include_router(auth_endpoints.router, prefix="/auth")
web_router.include_router(users_endpoints.router, prefix="/users", dependencies=[Depends(get_current_token)])
web_router.include_router(members_endpoints.router, prefix="/members", dependencies=[Depends(get_current_token)])
web_router.include_router(rooms_endpoints.router, prefix="/rooms", dependencies=[Depends(get_current_token)])
web_router.include_router(devices_endpoints.router, prefix="/devices", dependencies=[Depends(get_current_token)])
web_router.include_router(room_devices_endpoints.router, prefix="/room-devices", dependencies=[Depends(get_current_token)])
web_router.include_router(device_messages_endpoints.router, prefix="/device-messages", dependencies=[Depends(get_current_token)])
web_router.include_router(member_device_permissions_endpoints.router, prefix="/member-device-permissions", dependencies=[Depends(get_current_token)])
web_router.include_router(check_in_endpoints.router, prefix="/check-in", dependencies=[Depends(get_current_token)])
web_router.include_router(points_endpoints.router, prefix="/points", dependencies=[Depends(get_current_token)])
web_router.include_router(system_message_endpoints.router, prefix="/system-messages", dependencies=[Depends(get_current_token)])
web_router.include_router(version_info_endpoints.router, prefix="/version-info", dependencies=[Depends(get_current_token)])
web_router.include_router(feedback_endpoints.router, prefix="/feedback", dependencies=[Depends(get_current_token)])
web_router.include_router(websocket_endpoints.router, prefix="/ws")

# 将 web_router 添加到 api_router，添加 /web 前缀
api_router.include_router(web_router, prefix="/web")