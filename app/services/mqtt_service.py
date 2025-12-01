"""
MQTT服务工具类（服务端）
服务端被动监听设备连接，根据设备SN区分消息处理和控制
"""
import asyncio
import json
from typing import Dict, Any, Optional, Callable
from asyncio_mqtt import Client, MqttError
from app.core.config import settings


class MQTTService:
    def __init__(self):
        self.host = settings.MQTT_HOST
        self.port = settings.MQTT_PORT
        self.username = settings.MQTT_USERNAME
        self.password = settings.MQTT_PASSWORD

        # 三个固定的 topic
        self.topic_control = "jasper/control"   # 后台 -> 设备
        self.topic_data = "jasper/data"         # 设备 -> 后台
        self.topic_status = "jasper/status"     # 设备 -> 后台

        self.client = None
        self.running = False

    async def connect(self):
        """后台作为客户端，连接到 MQTT Broker"""
        self.client = Client(
            self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            client_id="jasper_backend"
        )

        await self.client.connect()
        print("[MQTT] 后台已连接到 Broker")
        self.running = True

    async def subscribe_topics(self):
        """订阅固定的三个 topic"""
        await self.client.subscribe(self.topic_data)
        await self.client.subscribe(self.topic_status)
        print("[MQTT] 后台已订阅: data / status")

    async def _on_data(self, sn: Optional[str], payload: Dict[str, Any]):
        """处理设备数据消息（内部方法）"""
        if not sn:
            print(f"⚠️ [MQTT] 收到数据消息但缺少SN: {payload}")
            return
        
        print(f"📊 [MQTT] 收到设备 {sn} 的数据: {payload}")
        # TODO: 在这里添加数据处理逻辑，例如：
        # - 保存到数据库
        # - 通过WebSocket推送给前端
        # - 触发告警等
    
    async def _on_status(self, sn: Optional[str], payload: Dict[str, Any]):
        """处理设备状态消息（内部方法）"""
        if not sn:
            print(f"⚠️ [MQTT] 收到状态消息但缺少SN: {payload}")
            return
        
        print(f"📡 [MQTT] 收到设备 {sn} 的状态: {payload}")
        # TODO: 在这里添加状态处理逻辑，例如：
        # - 更新设备在线状态
        # - 记录设备连接时间
        # - 通过WebSocket通知前端设备上线/下线
    
    async def listen(self):
        """
        持续监听消息并内部处理
        """
        try:
            async with self.client.unfiltered_messages() as messages:
                await self.subscribe_topics()

                async for msg in messages:
                    topic = msg.topic
                    payload = msg.payload.decode()

                    if topic == self.topic_data:
                        data = self.parse_payload(payload)
                        sn = data.get("sn")
                        try:
                            await self._on_data(sn, data)
                        except Exception as e:
                            print(f"❌ [MQTT] 处理数据消息失败: {e}")

                    elif topic == self.topic_status:
                        data = self.parse_payload(payload)
                        sn = data.get("sn")
                        try:
                            await self._on_status(sn, data)
                        except Exception as e:
                            print(f"❌ [MQTT] 处理状态消息失败: {e}")
        except MqttError as e:
            print(f"❌ [MQTT] 监听消息时发生错误: {e}")
            self.running = False
        except Exception as e:
            print(f"❌ [MQTT] 监听消息时发生未知错误: {e}")
            self.running = False

    async def publish_control(self, sn: str, payload: dict):
        """后台 -> 设备，给某个 SN 发布控制指令"""
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        await self.client.publish(self.topic_control, message_json)
        print(f"✅ [MQTT] 已发送控制命令给 {sn}: {message}")

    @staticmethod
    def parse_payload(payload: str) -> Dict[str, Any]:
        """解析payload为dict"""
        try:
            return json.loads(payload)
        except:
            return {"raw": payload}


# 全局MQTT服务实例
mqtt_service = MQTTService()
