from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_token
from app.db.session import get_db

api_router = APIRouter()

# ============================================
# Client 路由器 - 统一的客户端 API（App + Web）
# ============================================
client_router = APIRouter(tags=["client"])

# 导入 client 模块
from app.api.client import auth
from app.api.client import devices
from app.api.client import check_in
from app.api.client import points
from app.api.client import system_message
from app.api.client import feedback
from app.api.client import families
from app.api.client import family_members
from app.api.client import device_messages
from app.api.client import version_info

# 注册 client 路由
# 认证接口不需要认证依赖，只需要数据库依赖
client_router.include_router(auth.router, prefix="/auth", dependencies=[Depends(get_db)])
# 其他接口需要认证：get_db（数据库会话）、get_current_token（认证）
client_router.include_router(devices.router, prefix="/devices", dependencies=[Depends(get_db), Depends(get_current_token)])
client_router.include_router(families.router, prefix="/families", dependencies=[Depends(get_db), Depends(get_current_token)])
client_router.include_router(family_members.router, prefix="/family-members", dependencies=[Depends(get_db), Depends(get_current_token)])
client_router.include_router(device_messages.router, prefix="/device-messages", dependencies=[Depends(get_db), Depends(get_current_token)])
client_router.include_router(check_in.router, prefix="/check-in", dependencies=[Depends(get_db), Depends(get_current_token)])
client_router.include_router(points.router, prefix="/points", dependencies=[Depends(get_db), Depends(get_current_token)])
client_router.include_router(system_message.router, prefix="/system-messages", dependencies=[Depends(get_db), Depends(get_current_token)])
client_router.include_router(feedback.router, prefix="/feedback", dependencies=[Depends(get_db), Depends(get_current_token)])
client_router.include_router(version_info.router, prefix="/version-info", dependencies=[Depends(get_db), Depends(get_current_token)])

# 将 client_router 添加到 api_router，添加 /client 前缀
api_router.include_router(client_router, prefix="/client")

# ============================================
# Admin 路由器 - 管理后台 API
# ============================================
admin_router = APIRouter(tags=["admin"])

# 导入 Admin 模块
from app.api.admin import auth as admin_auth
from app.api.admin import account as admin_account
from app.api.admin import device as admin_device
from app.api.admin import network as admin_network
from app.api.admin import device_message as admin_device_message
from app.api.admin import user as admin_user
from app.api.admin import family as admin_family
from app.api.admin import feedback as admin_feedback
from app.api.admin import log as admin_log
from app.api.admin import notice as admin_notice
from app.api.admin import version as admin_version
from app.api.admin import device_model as admin_device_model
from app.api.admin import thing_model as admin_thing_model
from app.api.admin import points as admin_points

# 注册 Admin 路由
# 登录接口不需要认证依赖，只需要数据库依赖
admin_router.include_router(admin_auth.router, dependencies=[Depends(get_db)])
# 其他接口需要认证：get_db（数据库会话）、get_current_token（认证）
admin_router.include_router(admin_account.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_device.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_network.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_device_message.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_user.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_family.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_feedback.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_log.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_notice.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_version.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_device_model.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_thing_model.router, dependencies=[Depends(get_db), Depends(get_current_token)])
admin_router.include_router(admin_points.router, dependencies=[Depends(get_db), Depends(get_current_token)])

# 将 admin_router 添加到 api_router，添加 /admin 前缀
api_router.include_router(admin_router, prefix="/admin")
