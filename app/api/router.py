from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_token
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
# 统一管理依赖：get_db（数据库会话）、get_current_token（认证）
web_router.include_router(auth_endpoints.router, prefix="/auth", dependencies=[Depends(get_db)])
web_router.include_router(families_endpoints.router, prefix="/families", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(family_members_endpoints.router, prefix="/family-members", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(devices_endpoints.router, prefix="/devices", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(device_messages_endpoints.router, prefix="/device-messages", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(check_in_endpoints.router, prefix="/check-in", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(points_endpoints.router, prefix="/points", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(system_message_endpoints.router, prefix="/system-messages", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(version_info_endpoints.router, prefix="/version-info", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(feedback_endpoints.router, prefix="/feedback", dependencies=[Depends(get_db), Depends(get_current_token)])
web_router.include_router(websocket_endpoints.router, prefix="/ws")

# 将 web_router 添加到 api_router，添加 /web 前缀
api_router.include_router(web_router, prefix="/web")

# 创建 iot 路由器，用于统一管理所有 IoT 管理接口
iot_router = APIRouter(tags=["iot"])

# 注册 IoT 端点路由
from app.api.iot import auth as iot_auth
from app.api.iot import account as iot_account
from app.api.iot import device as iot_device
from app.api.iot import network as iot_network
from app.api.iot import device_message as iot_device_message
from app.api.iot import user as iot_user
from app.api.iot import family as iot_family
from app.api.iot import feedback as iot_feedback
from app.api.iot import log as iot_log
from app.api.iot import notice as iot_notice
from app.api.iot import version as iot_version
from app.api.iot import device_model as iot_device_model
from app.api.iot import thing_model as iot_thing_model

# 将所有 IoT 路由添加到 iot_router
# 登录接口不需要认证依赖，只需要数据库依赖
iot_router.include_router(iot_auth.router, dependencies=[Depends(get_db)])
# 其他接口需要认证：get_db（数据库会话）、get_current_token（认证）
iot_router.include_router(iot_account.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_device.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_network.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_device_message.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_user.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_family.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_feedback.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_log.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_notice.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_version.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_device_model.router, dependencies=[Depends(get_db), Depends(get_current_token)])
iot_router.include_router(iot_thing_model.router, dependencies=[Depends(get_db), Depends(get_current_token)])

# 将 iot_router 添加到 api_router，添加 /iot 前缀
api_router.include_router(iot_router, prefix="/iot")