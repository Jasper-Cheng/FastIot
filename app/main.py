from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine
from app.services.redis_service import redis_service
from app.services.websocket_tool import websocket_tool
from app.services.wechat_service import wechat_service
from app.services.mqtt_service import mqtt_service

# 导入所有模型以确保 SQLAlchemy 关系映射正确配置
from app.db.models import *  # noqa: F401, F403

# 配置日志级别，关闭SQLAlchemy的SQL语句输出
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

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

async def wechat_qrcode_cleaner():
    """微信二维码清理任务"""
    while True:
        try:
            deleted_count = wechat_service.cleanup_expired_qrcodes()
            if deleted_count > 0:
                print(f"🧹 [WeChat] 已清理 {deleted_count} 个过期二维码记录")
        except Exception as e:
            print(f"❌ [WeChat] 二维码清理异常: {e}")
        
        # 每5分钟清理一次
        await asyncio.sleep(300)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    print("🔄 应用启动中...")
    
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
    
    # 启动微信二维码清理任务
    qrcode_cleaner_task = asyncio.create_task(wechat_qrcode_cleaner())
    print("✅ 微信二维码清理任务已启动")
    
    # MQTT服务初始化
    mqtt_listen_task = None
    try:
        await mqtt_service.connect()
        # 启动MQTT监听任务（消息处理在mqtt_service内部实现）
        mqtt_listen_task = asyncio.create_task(mqtt_service.listen())
        print("✅ MQTT监听任务已启动")
    except Exception as e:
        print(f"❌ MQTT服务初始化失败: {e}")
    
    yield
    
    # shutdown
    print("🔄 应用关闭中...")
    heartbeat_task.cancel()
    qrcode_cleaner_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    print("💔 WebSocket心跳检查任务已停止")
    try:
        await qrcode_cleaner_task
    except asyncio.CancelledError:
        pass
    print("💔 微信二维码清理任务已停止")
    
    # 停止MQTT监听任务并断开连接
    try:
        if mqtt_listen_task is not None:
            mqtt_listen_task.cancel()
            try:
                await mqtt_listen_task
            except asyncio.CancelledError:
                pass
            print("💔 MQTT监听任务已停止")
        
        # 断开 MQTT 连接
        if mqtt_service.client:
            await mqtt_service.disconnect()
    except Exception as e:
        print(f"⚠️ 停止MQTT服务时出现异常（可忽略）: {e}")
    
    # 关闭数据库引擎的连接池
    try:
        await engine.dispose()
        print("✅ 数据库连接池已关闭")
    except Exception as e:
        print(f"⚠️ 关闭数据库连接池时出现异常（可忽略）: {e}")


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