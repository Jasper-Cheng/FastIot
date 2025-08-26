import redis.asyncio as redis
from typing import Optional, Dict, List
from app.core.config import settings
import json
import logging

logger = logging.getLogger(__name__)

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
            logger.info("Redis连接成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise
            
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            
    async def set_device_status(self, device_id: int, status: Dict) -> bool:
        """设置设备状态"""
        try:
            key = f"device:status:{device_id}"
            await self.redis_client.setex(
                key, 
                300,  # 5分钟过期
                json.dumps(status, ensure_ascii=False)
            )
            return True
        except Exception as e:
            logger.error(f"设置设备状态失败: {e}")
            return False
            
    async def get_device_status(self, device_id: int) -> Optional[Dict]:
        """获取设备状态"""
        try:
            key = f"device:status:{device_id}"
            data = await self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"获取设备状态失败: {e}")
            return None
            
    async def set_device_online(self, device_id: int, is_online: bool = True) -> bool:
        """设置设备在线状态"""
        try:
            key = f"device:online:{device_id}"
            if is_online:
                await self.redis_client.setex(key, 300, "1")  # 5分钟过期
            else:
                await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"设置设备在线状态失败: {e}")
            return False
            
    async def is_device_online(self, device_id: int) -> bool:
        """检查设备是否在线"""
        try:
            key = f"device:online:{device_id}"
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"检查设备在线状态失败: {e}")
            return False
            
    async def get_all_online_devices(self) -> List[int]:
        """获取所有在线设备ID"""
        try:
            pattern = "device:online:*"
            keys = await self.redis_client.keys(pattern)
            device_ids = []
            for key in keys:
                device_id = key.split(":")[-1]
                device_ids.append(int(device_id))
            return device_ids
        except Exception as e:
            logger.error(f"获取在线设备列表失败: {e}")
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
            return True
        except Exception as e:
            logger.error(f"设置设备控制命令失败: {e}")
            return False
            
    async def get_device_control(self, device_id: int) -> Optional[Dict]:
        """获取设备控制命令"""
        try:
            key = f"device:control:{device_id}"
            data = await self.redis_client.get(key)
            if data:
                await self.redis_client.delete(key)  # 获取后删除
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"获取设备控制命令失败: {e}")
            return None

# 全局Redis服务实例
redis_service = RedisService()
