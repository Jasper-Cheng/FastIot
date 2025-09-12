from fastapi import APIRouter

api_router = APIRouter()

# 注册端点路由
from app.api.endpoints import auth as auth_endpoints
from app.api.endpoints import users as users_endpoints

api_router.include_router(auth_endpoints.router, prefix="/auth", tags=["auth"])
api_router.include_router(users_endpoints.router, prefix="/users", tags=["users"])

# 基础路由 - 可以在这里添加简单的健康检查等
@api_router.get("/health")
async def health_check():
    return {"status": "ok", "message": "Service is running"}