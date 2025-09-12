from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.services.mqtt_client import mqtt_service
from app.services.mqtt_handlers import register_mqtt_subscriptions

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    print("🔄 应用启动中...")
    try:
        mqtt_service.connect()
        register_mqtt_subscriptions()
        print("✅ MQTT连接成功并已注册订阅")
    except Exception as e:
        print(f"❌ MQTT连接失败: {e}")
    yield
    # shutdown
    print("🔄 应用关闭中...")
    mqtt_service.disconnect()
    print("🔌 MQTT连接已断开")


app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    version=settings.VERSION,
    lifespan=lifespan,
)

# ----------------------
# CORS 配置
# ----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-CSRF-Token",
        "Origin",
        "Cache-Control",
        "Pragma",
        "Expires",
    ],
    expose_headers=[
        "Content-Length",
        "Content-Type",
        "Content-Disposition",
        "X-Total-Count",
        "X-Page-Count",
    ],
)

# ----------------------
# API 路由
# ----------------------
from app.api.router import api_router

app.include_router(api_router, prefix=settings.API_V1_STR)

# ----------------------
# 健康检查和CORS测试
# ----------------------
@app.get("/")
async def root():
    """根路径 - 健康检查"""
    return {
        "message": "FastIoT API is running!",
        "version": settings.VERSION,
        "docs": "/docs",
        "cors_enabled": True
    }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "service": "FastIoT API"
    }