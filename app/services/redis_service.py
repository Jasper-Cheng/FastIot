import redis.asyncio as redis
from typing import Optional, Dict, List, Any
from app.core.config import settings
import json

class RedisService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._is_connected = False
        
    async def connect(self):
        """连接Redis"""
        if not settings.REDIS_ENABLED:
            print("⚠️ [REDIS] Redis已禁用，跳过连接")
            return
            
        try:
            self.redis_client = redis.from_url(
                str(settings.REDIS_URL),
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            self._is_connected = True
            print("✅ [REDIS] Redis连接成功")
        except Exception as e:
            print(f"❌ [REDIS] Redis连接失败: {e}")
            self._is_connected = False
            raise
            
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            self._is_connected = False
            
    def is_available(self) -> bool:
        """检查Redis是否可用"""
        return settings.REDIS_ENABLED and self._is_connected and self.redis_client is not None

    async def clear_all_cache(self) -> bool:
        """清除所有Redis缓存"""
        if not self.is_available():
            print("⚠️ [REDIS] Redis不可用，跳过清除所有缓存")
            return False
            
        try:
            # 清除当前数据库的所有键
            await self.redis_client.flushdb()
            print("✅ [REDIS] 已清除所有Redis缓存")
            return True
        except Exception as e:
            print(f"❌ [REDIS] 清除所有缓存失败: {e}")
            return False

    async def clear_device_cache(self) -> bool:
        """清除所有设备相关的缓存"""
        if not self.is_available():
            print("⚠️ [REDIS] Redis不可用，跳过清除设备缓存")
            return False
            
        try:
            # 获取所有设备信息缓存键
            device_info_keys = await self.redis_client.keys("device:info:*")
            # 获取所有用户设备索引键
            owner_devices_keys = await self.redis_client.keys("owner:*:devices")
            
            # 删除所有找到的键
            if device_info_keys or owner_devices_keys:
                all_keys = device_info_keys + owner_devices_keys
                await self.redis_client.delete(*all_keys)
                print(f"✅ [REDIS] 已清除设备缓存 - 设备信息: {len(device_info_keys)}个, 用户索引: {len(owner_devices_keys)}个")
            else:
                print("ℹ️ [REDIS] 没有找到设备相关的缓存")
            return True
        except Exception as e:
            print(f"❌ [REDIS] 清除设备缓存失败: {e}")
            return False

    # ---------- Device Info (metadata) cache ----------
    async def set_device_info(self, device_id: int, info: Dict[str, Any], ttl_seconds: int = 600) -> bool:
        """缓存设备基础信息（相对稳定的元数据），如 name、serial_number、owner_id、status、last_active、created_at 等。

        使用独立的 key：device:info:{id}
        与运行态 state 分开，TTL 默认更长。
        """
        if not self.is_available():
            print(f"⚠️ [REDIS] Redis不可用，跳过设置设备信息缓存: device_id:{device_id}")
            return False
            
        try:
            key = f"device:info:{device_id}"
            await self.redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(info, ensure_ascii=False, default=str)
            )
            print(f"✅ [CACHE] 设置缓存 - 字段:device_info, device_id:{device_id}")
            return True
        except Exception as e:
            print(f"❌ [CACHE] 设置设备信息缓存失败: {e}")
            return False

    async def get_device_info(self, device_id: int) -> Optional[Dict[str, Any]]:
        """读取设备基础信息缓存。"""
        if not self.is_available():
            print(f"⚠️ [REDIS] Redis不可用，跳过获取设备信息缓存: device_id:{device_id}")
            return None
            
        try:
            key = f"device:info:{device_id}"
            raw = await self.redis_client.get(key)
            if not raw:
                print(f"❌ [CACHE] 缓存未命中 - 字段:device_info, device_id:{device_id}")
                return None
            try:
                info = json.loads(raw)
            except Exception:
                info = None
            if isinstance(info, dict):
                print(f"✅ [CACHE] 缓存命中 - 字段:device_info, device_id:{device_id}")
                return info
            return None
        except Exception as e:
            print(f"❌ [CACHE] 获取设备信息缓存失败: {e}")
            return None

    async def delete_device_info(self, device_id: int) -> bool:
        """删除设备基础信息缓存。"""
        if not self.is_available():
            print(f"⚠️ [REDIS] Redis不可用，跳过删除设备信息缓存: device_id:{device_id}")
            return False
            
        try:
            key = f"device:info:{device_id}"
            await self.redis_client.delete(key)
            print(f"✅ [CACHE] 删除缓存 - 字段:device_info, device_id:{device_id}")
            return True
        except Exception as e:
            print(f"❌ [CACHE] 删除设备信息缓存失败: {e}")
            return False

    # ---------- Owner -> devices index ----------
    def _owner_devices_key(self, owner_id: int) -> str:
        return f"owner:{owner_id}:devices"

    async def add_device_to_owner(self, owner_id: int, device_id: int, ttl_seconds: int = 1800) -> bool:
        """添加设备到用户索引"""
        if not self.is_available():
            print(f"⚠️ [REDIS] Redis不可用，跳过添加设备到用户索引: owner_id:{owner_id}, device_id:{device_id}")
            return False
            
        try:
            key = self._owner_devices_key(owner_id)
            await self.redis_client.sadd(key, device_id)
            await self.redis_client.expire(key, ttl_seconds)
            print(f"✅ [CACHE] 索引更新 - owner_devices add, owner_id:{owner_id}, device_id:{device_id}")
            return True
        except Exception as e:
            print(f"❌ [CACHE] 添加设备到用户索引失败: {e}")
            return False

    async def remove_device_from_owner(self, owner_id: int, device_id: int) -> bool:
        """从用户索引移除设备"""
        if not self.is_available():
            print(f"⚠️ [REDIS] Redis不可用，跳过从用户索引移除设备: owner_id:{owner_id}, device_id:{device_id}")
            return False
            
        try:
            key = self._owner_devices_key(owner_id)
            await self.redis_client.srem(key, device_id)
            print(f"✅ [CACHE] 索引更新 - owner_devices remove, owner_id:{owner_id}, device_id:{device_id}")
            return True
        except Exception as e:
            print(f"❌ [CACHE] 从用户索引移除设备失败: {e}")
            return False

    async def get_owner_device_ids(self, owner_id: int) -> List[int]:
        """获取用户的设备ID列表"""
        if not self.is_available():
            print(f"⚠️ [REDIS] Redis不可用，跳过获取用户设备索引: owner_id:{owner_id}")
            return []
            
        try:
            key = self._owner_devices_key(owner_id)
            raw_ids = await self.redis_client.smembers(key)
            if not raw_ids:
                print(f"❌ [CACHE] 缓存未命中 - 字段:owner_devices, owner_id:{owner_id}")
                return []
            ids: List[int] = []
            for rid in raw_ids:
                try:
                    ids.append(int(rid))
                except Exception:
                    continue
            print(f"✅ [CACHE] 缓存命中 - 字段:owner_devices, owner_id:{owner_id}, count:{len(ids)}")
            return ids
        except Exception as e:
            print(f"❌ [CACHE] 获取用户设备索引失败: {e}")
            return []

    async def clear_owner_devices(self, owner_id: int) -> bool:
        """清除用户的所有设备索引"""
        if not self.is_available():
            print(f"⚠️ [REDIS] Redis不可用，跳过清除用户设备索引: owner_id:{owner_id}")
            return False
            
        try:
            key = self._owner_devices_key(owner_id)
            await self.redis_client.delete(key)
            print(f"✅ [CACHE] 清除用户设备索引: owner_id:{owner_id}")
            return True
        except Exception as e:
            print(f"❌ [CACHE] 清除用户设备索引失败: {e}")
            return False

# 全局Redis服务实例
redis_service = RedisService()
