"""
MQTT服务工具类（服务端）
服务端被动监听设备连接，根据设备SN区分消息处理和控制
采用分层化 topic：
- 设备控制：device/{sn}           # 后台 -> 设备
- 设备数据：device/{sn}/data       # 设备 -> 后台
- 设备状态：device/{sn}/status     # 设备 -> 后台
- 系统通知：system/notice          # 广播消息
- 家庭消息：home/{home_id}/event    # 家庭事件
"""
import asyncio
import json
from typing import Dict, Any, Optional
from asyncio_mqtt import Client, MqttError
from app.core.config import settings


class MQTTService:
    def __init__(self):
        self.host = settings.MQTT_HOST
        self.port = settings.MQTT_PORT
        self.username = settings.MQTT_USERNAME
        self.password = settings.MQTT_PASSWORD

        # 分层化 topic
        self.topic_control_template = "device/{sn}"         # 后台 -> 设备
        self.topic_data_template = "device/{sn}/data"       # 设备 -> 后台
        self.topic_status_template = "device/{sn}/status"   # 设备 -> 后台
        self.topic_system_notice = "system/notice"          # 系统通知
        self.topic_home_event_template = "home/{home_id}/event"  # 家庭事件

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
        """订阅所有设备数据和状态"""
        # 订阅所有设备数据
        await self.client.subscribe("device/+/data")
        # 订阅所有设备状态
        await self.client.subscribe("device/+/status")
        print("[MQTT] 后台已订阅: device/+/data, device/+/status")

    async def _on_data(self, sn: Optional[str], payload: Dict[str, Any]):
        """处理设备数据消息（内部方法）"""
        if not sn:
            print(f"⚠️ [MQTT] 收到数据消息但缺少SN: {payload}")
            return
        print(f"📊 [MQTT] 收到设备 {sn} 的数据: {payload}")
        # TODO: 保存到数据库 / WebSocket 推送前端 / 告警处理

    async def _on_status(self, sn: Optional[str], payload: Dict[str, Any]):
        """处理设备状态消息（内部方法）"""
        if not sn:
            print(f"⚠️ [MQTT] 收到状态消息但缺少SN: {payload}")
            return
        print(f"📡 [MQTT] 收到设备 {sn} 的状态: {payload}")
        # TODO: 更新设备在线状态 / WebSocket 通知前端

    async def listen(self):
        """持续监听消息并内部处理"""
        try:
            async with self.client.unfiltered_messages() as messages:
                await self.subscribe_topics()
                async for msg in messages:
                    topic = msg.topic
                    payload = self.parse_payload(msg.payload.decode())
                    sn = self.extract_sn(topic)

                    if topic.endswith("/data"):
                        try:
                            await self._on_data(sn, payload)
                        except Exception as e:
                            print(f"❌ [MQTT] 处理数据消息失败: {e}")

                    elif topic.endswith("/status"):
                        try:
                            await self._on_status(sn, payload)
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
        topic = self.topic_control_template.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        await self.client.publish(topic, message_json)
        print(f"✅ [MQTT] 已发送控制命令给 {sn}: {message}")

    @staticmethod
    def parse_payload(payload: str) -> Dict[str, Any]:
        """解析 payload 为 dict"""
        try:
            return json.loads(payload)
        except:
            return {"raw": payload}

    @staticmethod
    def extract_sn(topic: str) -> Optional[str]:
        """
        从 topic 中提取设备 SN
        device/{sn}/data 或 device/{sn}/status
        """
        parts = topic.split("/")
        if len(parts) >= 2 and parts[0] == "device":
            return parts[1]
        return None


# 全局 MQTT 服务实例
mqtt_service = MQTTService()
