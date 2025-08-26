from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.services.redis_service import redis_service
from app.services.mqtt_client import mqtt_service
from app.services.mqtt_handlers import register_mqtt_subscriptions


@asynccontextmanager
async def lifespan():
    # startup
    try:
        await redis_service.connect()
        print("✅ Redis连接成功")
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
    try:
        mqtt_service.connect()
        register_mqtt_subscriptions()
        print("✅ MQTT连接成功并已注册订阅")
    except Exception as e:
        print(f"❌ MQTT连接失败: {e}")
    yield
    # shutdown
    try:
        await redis_service.disconnect()
        print("🔌 Redis连接已断开")
    finally:
        mqtt_service.disconnect()
        print("🔌 MQTT连接已断开")


app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    version=settings.VERSION,
    lifespan=lifespan,
)

# ----------------------
# API 路由
# ----------------------
from app.api.router import api_router

app.include_router(api_router, prefix=settings.API_V1_STR)
