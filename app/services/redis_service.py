import redis.asyncio as redis
from typing import Optional, Dict, Any
import json
from app.core.config import settings

class RedisService:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """连接到Redis服务器"""
        try:
            # settings.REDIS_URL 可能为 Pydantic 的 RedisDsn，需要转为 str
            self.redis = redis.from_url(
                str(settings.REDIS_URL),
                encoding="utf-8",
                decode_responses=True
            )
            # 测试连接
            await self.redis.ping()
            print("✅ Redis连接成功")
        except Exception as e:
            print(f"❌ Redis连接失败: {e}")
            raise e
    
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis:
            await self.redis.close()
            print("🔌 Redis连接已断开")
    
    async def get_device_info(self, device_id: int) -> Optional[Dict[str, Any]]:
        """获取设备信息缓存"""
        if not self.redis:
            return None
        try:
            key = f"device_info:{device_id}"
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"❌ 获取设备信息缓存失败: {e}")
            return None
    
    async def set_device_info(self, device_id: int, info: Dict[str, Any], expire: int = 3600):
        """设置设备信息缓存"""
        if not self.redis:
            return
        try:
            key = f"device_info:{device_id}"
            await self.redis.setex(key, expire, json.dumps(info))
        except Exception as e:
            print(f"❌ 设置设备信息缓存失败: {e}")
    
    async def get_user_device_ids(self, user_id: int) -> Optional[list]:
        """获取用户设备ID列表缓存"""
        if not self.redis:
            return None
        try:
            key = f"user_devices:{user_id}"
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"❌ 获取用户设备ID列表失败: {e}")
            return None
    
    async def set_user_device_ids(self, user_id: int, device_ids: list, expire: int = 1800):
        """设置用户设备ID列表缓存"""
        if not self.redis:
            return
        try:
            key = f"user_devices:{user_id}"
            await self.redis.setex(key, expire, json.dumps(device_ids))
        except Exception as e:
            print(f"❌ 设置用户设备ID列表失败: {e}")
    
    async def delete_device_cache(self, device_id: int):
        """删除设备相关缓存"""
        if not self.redis:
            return
        try:
            # 删除设备信息缓存
            await self.redis.delete(f"device_info:{device_id}")
            # 删除所有用户的设备ID列表缓存（需要重新加载）
            pattern = "user_devices:*"
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
        except Exception as e:
            print(f"❌ 删除设备缓存失败: {e}")

# 创建全局Redis服务实例
redis_service = RedisService()
