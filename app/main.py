from fastapi import FastAPI
from app.core.config import settings
from app.services.redis_service import redis_service

# ----------------------
# 创建 FastAPI 实例
# ----------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    version=settings.VERSION,
)

# ----------------------
# 启动事件
# ----------------------
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化Redis连接"""
    try:
        await redis_service.connect()
        print("✅ Redis连接成功")
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")

# ----------------------
# 关闭事件
# ----------------------
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时断开Redis连接"""
    await redis_service.disconnect()
    print("🔌 Redis连接已断开")

# ----------------------
# 健康检查路由
# ----------------------
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}

# ----------------------
# API 路由
# ----------------------
from app.api.router import api_router

app.include_router(api_router, prefix=settings.API_V1_STR)
