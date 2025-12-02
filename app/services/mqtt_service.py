"""
MQTT服务工具类（服务端）- 使用 gmqtt 实现
服务端被动监听设备连接,根据设备SN区分消息处理和控制
采用分层化 topic:
- 设备控制: device/{sn}/control   # 后台 -> 设备
- 设备数据: device/{sn}/data       # 设备 -> 后台
- 设备状态: device/{sn}/status     # 设备 -> 后台
- 系统通知: system/notice          # 广播消息
- 家庭消息: home/{home_id}/event    # 家庭事件
"""
import asyncio
import json
from typing import Dict, Any, Optional
from gmqtt import Client as MQTTClient
from app.core.config import settings


class MQTTService:
    def __init__(self):
        self.host = settings.MQTT_HOST
        self.port = settings.MQTT_PORT
        self.username = settings.MQTT_USERNAME
        self.password = settings.MQTT_PASSWORD

        # 分层化 topic
        self.topic_control_template = "device/{sn}/control"  # 后台 -> 设备
        self.topic_data_template = "device/{sn}/data"        # 设备 -> 后台
        self.topic_status_template = "device/{sn}/status"    # 设备 -> 后台
        self.topic_system_notice = "system/notice"           # 系统通知
        self.topic_home_event_template = "home/{home_id}/event"  # 家庭事件

        self.client: Optional[MQTTClient] = None
        self.running = False
        self._connect_event = asyncio.Event()

    def on_connect(self, client, flags, rc, properties):
        """连接成功回调"""
        if rc == 0:
            print("[MQTT] 后台已连接到 Broker")
            self._connect_event.set()
        else:
            print(f"❌ [MQTT] 连接失败，返回码: {rc}")

    def on_disconnect(self, client, packet, exc=None):
        """断开连接回调"""
        print(f"💔 [MQTT] 与 Broker 断开连接")
        self.running = False
        self._connect_event.clear()

    def on_message(self, client, topic, payload, qos, properties):
        """消息接收回调"""
        try:
            parsed_payload = self.parse_payload(payload.decode())
            sn = self.extract_sn(topic)

            if topic.endswith("/data"):
                asyncio.create_task(self._on_data(sn, parsed_payload))
            elif topic.endswith("/status"):
                asyncio.create_task(self._on_status(sn, parsed_payload))

        except Exception as e:
            print(f"❌ [MQTT] 处理消息时发生错误: {e}")

    async def connect(self):
        """后台作为客户端，连接到 MQTT Broker"""
        self.client = MQTTClient(client_id="jasper_backend")
        
        # 设置回调函数
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        # 设置用户名和密码
        if self.username and self.password:
            self.client.set_auth_credentials(self.username, self.password)

        # 连接到 Broker
        await self.client.connect(self.host, self.port)
        
        # 等待连接成功
        await asyncio.wait_for(self._connect_event.wait(), timeout=10.0)
        self.running = True

    async def subscribe_topics(self):
        """订阅所有设备数据和状态"""
        # 订阅所有设备数据
        self.client.subscribe("device/+/data", qos=1)
        # 订阅所有设备状态
        self.client.subscribe("device/+/status", qos=1)
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
        """持续监听消息（gmqtt会自动处理消息回调）"""
        try:
            # 订阅主题
            await self.subscribe_topics()
            
            # 保持运行状态，gmqtt 会在后台自动处理消息
            while self.running:
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            print("[MQTT] 监听任务被取消")
            raise
        except Exception as e:
            print(f"❌ [MQTT] 监听消息时发生错误: {e}")
            self.running = False

    async def publish_control(self, sn: str, payload: dict):
        """后台 -> 设备，给某个 SN 发布控制指令"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.topic_control_template.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送控制命令给 {sn}: {message}")

    async def disconnect(self):
        """断开 MQTT 连接"""
        if self.client:
            await self.client.disconnect()
            self.running = False
            print("[MQTT] 已断开连接")

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