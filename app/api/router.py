from fastapi import APIRouter

api_router = APIRouter()

# 基础路由 - 可以在这里添加简单的健康检查等
@api_router.get("/health")
async def health_check():
    return {"status": "ok", "message": "Service is running"}