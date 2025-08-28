import redis.asyncio as redis
from typing import Optional, Dict, List, Any
from app.core.config import settings
import json

class RedisService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        
    async def connect(self):
        """连接Redis"""
        try:
            self.redis_client = redis.from_url(
                str(settings.REDIS_URL),
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            print("✅ [REDIS] Redis连接成功")
        except Exception as e:
            print(f"❌ [REDIS] Redis连接失败: {e}")
            raise
            
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            
    async def _merge_and_set_state(self, device_id: int, partial_state: Dict[str, Any], ttl_seconds: int = 300) -> bool:
        """Merge a partial state into the cached device state and persist with TTL.

        State schema in Redis (JSON string):
        {
          "online": bool,
          "status": dict | None,
          "last_active": str | None
        }
        """
        try:
            key = f"device:state:{device_id}"
            existing_raw = await self.redis_client.get(key)
            if existing_raw:
                try:
                    state: Dict[str, Any] = json.loads(existing_raw)
                except Exception:
                    state = {}
            else:
                state = {}

            state.update(partial_state)

            await self.redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(state, ensure_ascii=False)
            )
            print(f"✅ [CACHE] 设置缓存 - 字段:device_state, device_id:{device_id}")
            return True
        except Exception as e:
            print(f"❌ [CACHE] 合并更新设备状态失败: {e}")
            return False
            
    async def set_device_status(self, device_id: int, status: Dict) -> bool:
        """设置设备状态"""
        try:
            # merge into unified state under device:state:{id}
            return await self._merge_and_set_state(device_id, {"status": status})
        except Exception as e:
            print(f"❌ [CACHE] 设置设备状态失败: {e}")
            return False
            
    async def get_device_status(self, device_id: int) -> Optional[Dict]:
        """获取设备状态"""
        try:
            key = f"device:state:{device_id}"
            data = await self.redis_client.get(key)
            if not data:
                print(f"❌ [CACHE] 缓存未命中 - 字段:device_status, device_id:{device_id}")
                return None
            try:
                state = json.loads(data)
            except Exception:
                state = {}
            print(f"✅ [CACHE] 缓存命中 - 字段:device_status, device_id:{device_id}")
            status = state.get("status")
            return status if isinstance(status, dict) else None
        except Exception as e:
            print(f"❌ [CACHE] 获取设备状态失败: {e}")
            return None
            
    async def set_device_online(self, device_id: int, is_online: bool = True) -> bool:
        """设置设备在线状态"""
        try:
            # unify online flag into device state instead of separate key
            return await self._merge_and_set_state(device_id, {"online": bool(is_online)})
        except Exception as e:
            print(f"❌ [CACHE] 设置设备在线状态失败: {e}")
            return False
            
    async def is_device_online(self, device_id: int) -> bool:
        """检查设备是否在线"""
        try:
            key = f"device:state:{device_id}"
            data = await self.redis_client.get(key)
            if not data:
                print(f"❌ [CACHE] 缓存未命中 - 字段:device_online, device_id:{device_id}")
                return False
            try:
                state = json.loads(data)
            except Exception:
                state = {}
            online = bool(state.get("online", False))
            print(f"✅ [CACHE] 缓存命中 - 字段:device_online, device_id:{device_id}")
            return online
        except Exception as e:
            print(f"❌ [CACHE] 检查设备在线状态失败: {e}")
            return False
            
    async def get_all_online_devices(self) -> List[int]:
        """获取所有在线设备ID"""
        try:
            pattern = "device:state:*"
            keys = await self.redis_client.keys(pattern)
            device_ids = []
            for key in keys:
                try:
                    # quick filter by checking online flag
                    raw = await self.redis_client.get(key)
                    if not raw:
                        continue
                    state = json.loads(raw)
                    if not bool(state.get("online", False)):
                        continue
                    device_id = key.split(":")[-1]
                    device_ids.append(int(device_id))
                except Exception:
                    continue
            return device_ids
        except Exception as e:
            print(f"❌ [CACHE] 获取在线设备列表失败: {e}")
            return []
            
    async def set_device_control(self, device_id: int, command: Dict) -> bool:
        """设置设备控制命令"""
        try:
            key = f"device:control:{device_id}"
            await self.redis_client.setex(
                key,
                60,  # 1分钟过期
                json.dumps(command, ensure_ascii=False)
            )
            cmd_name = command.get("command") if isinstance(command, dict) else None
            user_id = command.get("user_id") if isinstance(command, dict) else None
            print(f"✅ [CACHE] 设置缓存 - 字段:device_control, device_id:{device_id}, command:{cmd_name}, user_id:{user_id}")
            # 详细命令内容仅在调试级别打印，避免日志过大/敏感
            print(f"🔍 [CACHE] device_control payload: {command}")
            return True
        except Exception as e:
            print(f"❌ [CACHE] 设置设备控制命令失败: {e}")
            return False
            
    async def get_device_control(self, device_id: int) -> Optional[Dict]:
        """获取设备控制命令"""
        try:
            key = f"device:control:{device_id}"
            data = await self.redis_client.get(key)
            if data:
                await self.redis_client.delete(key)  # 获取后删除
                print(f"✅ [CACHE] 缓存命中并消费 - 字段:device_control, device_id:{device_id}")
                try:
                    payload = json.loads(data)
                except Exception:
                    payload = None
                if isinstance(payload, dict):
                    print(f"🔍 [CACHE] device_control consumed payload: {payload}")
                return payload
            print(f"❌ [CACHE] 缓存未命中 - 字段:device_control, device_id:{device_id}")
            return None
        except Exception as e:
            print(f"❌ [CACHE] 获取设备控制命令失败: {e}")
            return None

    # ---------- Device Info (metadata) cache ----------
    async def set_device_info(self, device_id: int, info: Dict[str, Any], ttl_seconds: int = 600) -> bool:
        """缓存设备基础信息（相对稳定的元数据），如 name、serial_number、owner_id、status、last_active、created_at 等。

        使用独立的 key：device:info:{id}
        与运行态 state 分开，TTL 默认更长。
        """
        try:
            key = f"device:info:{device_id}"
            await self.redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(info, ensure_ascii=False, default=str)
            )
            print(f"✅ [CACHE] 设置缓存 - 字段:device_info, device_id:{device_id}")
            print(f"🔍 [CACHE] device_info payload: {info}")
            return True
        except Exception as e:
            print(f"❌ [CACHE] 设置设备信息缓存失败: {e}")
            return False

    async def get_device_info(self, device_id: int) -> Optional[Dict[str, Any]]:
        """读取设备基础信息缓存。"""
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
        try:
            key = self._owner_devices_key(owner_id)
            await self.redis_client.srem(key, device_id)
            print(f"✅ [CACHE] 索引更新 - owner_devices remove, owner_id:{owner_id}, device_id:{device_id}")
            return True
        except Exception as e:
            print(f"❌ [CACHE] 从用户索引移除设备失败: {e}")
            return False

    async def get_owner_device_ids(self, owner_id: int) -> List[int]:
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

# 全局Redis服务实例
redis_service = RedisService()
