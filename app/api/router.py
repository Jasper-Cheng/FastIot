from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_token, get_family_clients
from app.db.session import get_db

api_router = APIRouter()

# 创建 web 路由器，用于统一管理所有 web API
web_router = APIRouter(tags=["web"])

# 注册端点路由
from app.api.web import auth as auth_endpoints
from app.api.web import families as families_endpoints
from app.api.web import family_members as family_members_endpoints
from app.api.web import devices as devices_endpoints
from app.api.web import device_messages as device_messages_endpoints
from app.api.web import check_in as check_in_endpoints
from app.api.web import points as points_endpoints
from app.api.web import system_message as system_message_endpoints
from app.api.web import version_info as version_info_endpoints
from app.api.web import feedback as feedback_endpoints
from app.api.web import websocket as websocket_endpoints

# 将所有路由添加到 web_router
# 统一管理依赖：get_db（数据库会话）、get_current_token（认证）、get_family_clients（家庭客户端列表）
web_router.include_router(auth_endpoints.router, prefix="/auth", dependencies=[Depends(get_db), Depends(get_family_clients)])
web_router.include_router(families_endpoints.router, prefix="/families", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(family_members_endpoints.router, prefix="/family-members", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(devices_endpoints.router, prefix="/devices", dependencies=[Depends(get_db), Depends(get_current_token), Depends(get_family_clients)])
web_router.include_router(device_messages_endpoints.router, prefix="/device-messages", dependencies=[Depends(get_db), Depends(get_current_token), Depends(get_family_clients)])
web_router.include_router(check_in_endpoints.router, prefix="/check-in", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(points_endpoints.router, prefix="/points", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(system_message_endpoints.router, prefix="/system-messages", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(version_info_endpoints.router, prefix="/version-info", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(feedback_endpoints.router, prefix="/feedback", dependencies=[Depends(get_db), Depends(get_current_token), Depends(get_family_clients)])
web_router.include_router(websocket_endpoints.router, prefix="/ws")

# 将 web_router 添加到 api_router，添加 /web 前缀
api_router.include_router(web_router, prefix="/web")