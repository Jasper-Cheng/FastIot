from fastapi import FastAPI
from app.core.config import settings

# ----------------------
# 创建 FastAPI 实例
# ----------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    version="0.1.0"
)

# ----------------------
# 健康检查路由
# ----------------------
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}

# ----------------------
# 示例 API 路由
# 可以把 endpoints 放到 app/api/endpoints
# 然后在这里 include_router
# ----------------------
# from app.api.endpoints import devices
# app.include_router(devices.router, prefix=f"{settings.API_V1_STR}/devices", tags=["Devices"])
