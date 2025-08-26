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
