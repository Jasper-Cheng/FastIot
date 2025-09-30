from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from sqlalchemy import text
from app.core.config import settings
from app.services.mqtt_client import mqtt_service
from app.services.mqtt_handlers import register_mqtt_subscriptions
from app.db.session import engine
from app.services.redis_service import redis_service
from app.services.websocket_tool import websocket_tool

async def heartbeat_checker():
    """心跳超时检查任务"""
    while True:
        try:
            timeout_count = await websocket_tool.check_heartbeat_timeouts()
            if timeout_count > 0:
                print(f"💔 [WebSocket] 已断开 {timeout_count} 个超时连接")
        except Exception as e:
            print(f"❌ [WebSocket] 心跳检查异常: {e}")
        
        # 每30秒检查一次
        await asyncio.sleep(30)

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

    # 数据库就绪检查
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ 数据库连接正常")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")

    # Redis 就绪检查（仅验证，不启用缓存持久连接）
    try:
        await redis_service.connect()
        print("✅ Redis就绪检测通过")
    except Exception as e:
        print(f"❌ Redis就绪检测失败: {e}")
    finally:
        try:
            await redis_service.disconnect()
        except Exception:
            pass
    
    # 启动心跳检查任务
    heartbeat_task = asyncio.create_task(heartbeat_checker())
    print("✅ WebSocket心跳检查任务已启动")
    
    yield
    
    # shutdown
    print("🔄 应用关闭中...")
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    print("💔 WebSocket心跳检查任务已停止")
    
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
        "Sec-WebSocket-Protocol",
        "Sec-WebSocket-Version",
        "Sec-WebSocket-Key",
        "Sec-WebSocket-Extensions",
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