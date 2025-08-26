from fastapi import FastAPI
from app.core.config import settings

# ----------------------
# 创建 FastAPI 实例
# ----------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    version=settings.VERSION,
)

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
