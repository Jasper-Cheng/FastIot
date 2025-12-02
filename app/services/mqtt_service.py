"""
MQTT服务工具类（服务端）- 设备在线状态监控
支持：
1. LWT (Last Will) 机制：设备异常断开时通过 status 主题自动发送离线消息
2. 心跳超时检测：定期检查设备最后上报时间
3. 状态消息检测：订阅设备 status 主题，处理在线/离线状态
"""
import asyncio
import json
import time
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
        self.topic_status_template = "device/{sn}/status"    # 设备 -> 后台（包含 LWT 离线消息）
        self.topic_system_notice = "system/notice"           # 系统通知
        self.topic_home_event_template = "home/{home_id}/event"  # 家庭事件

        self.client: Optional[MQTTClient] = None
        self.running = False
        self._connect_event = asyncio.Event()
        
        # 设备在线状态管理
        self.device_last_seen: Dict[str, float] = {}  # {sn: timestamp}
        self.device_online_status: Dict[str, bool] = {}  # {sn: True/False}
        self.heartbeat_timeout = 60  # 心跳超时时间（秒），根据设备上报频率调整

    def on_connect(self, client, flags, rc, properties):
        """连接成功回调"""
        if rc == 0:
            print("[MQTT] ✅ 后台已连接到 Broker")
            self._connect_event.set()
        else:
            print(f"❌ [MQTT] 连接失败，返回码: {rc}")

    def on_disconnect(self, client, packet, exc=None):
        """断开连接回调"""
        print(f"💔 [MQTT] 与 Broker 断开连接")
        self.running = False
        self._connect_event.clear()

    def on_subscribe(self, client, mid, qos, properties):
        """订阅成功回调"""
        print(f"[MQTT] ✅ 订阅成功: mid={mid}, qos={qos}")

    def on_message(self, client, topic, payload, qos, properties):
        """消息接收回调"""
        try:
            parsed_payload = self.parse_payload(payload.decode())
            sn = self.extract_sn(topic)

            # 更新设备最后活跃时间
            if sn:
                self.update_device_last_seen(sn)

            # 处理不同类型的消息
            if topic.endswith("/data"):
                asyncio.create_task(self._on_data(sn, parsed_payload))
            elif topic.endswith("/status"):
                asyncio.create_task(self._on_status(sn, parsed_payload))

        except Exception as e:
            print(f"❌ [MQTT] 处理消息时发生错误: {e}")
            import traceback
            traceback.print_exc()

    async def connect(self):
        """后台作为客户端，连接到 MQTT Broker"""
        print(f"[MQTT] 连接到 {self.host}:{self.port}")
        
        self.client = MQTTClient(client_id="jasper_backend")
        
        # 设置回调函数
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe

        # 设置认证
        if self.username and self.password:
            self.client.set_auth_credentials(self.username, self.password)

        # 连接到 Broker
        await self.client.connect(self.host, self.port)
        await asyncio.wait_for(self._connect_event.wait(), timeout=10.0)
        self.running = True

    async def subscribe_topics(self):
        """订阅所有设备相关主题"""
        topics = [
            ("device/+/data", 1),      # 设备数据
            ("device/+/status", 1),    # 设备状态（包含 LWT 离线消息）
        ]
        
        for topic, qos in topics:
            self.client.subscribe(topic, qos=qos)
            print(f"[MQTT] 已订阅: {topic}")
        
        await asyncio.sleep(0.5)

    def update_device_last_seen(self, sn: str):
        """更新设备最后活跃时间"""
        current_time = time.time()
        was_offline = self.device_online_status.get(sn, False) == False
        
        self.device_last_seen[sn] = current_time
        self.device_online_status[sn] = True
        
        # 如果设备从离线变为在线，触发上线事件
        if was_offline:
            asyncio.create_task(self._on_device_online(sn))

    async def _on_device_online(self, sn: str):
        """设备上线事件"""
        print(f"🟢 [MQTT] 设备 {sn} 上线")
        # TODO: 更新数据库状态
        # from app.services.device_service import update_device_status
        # await update_device_status(sn, online=True)
        
        # TODO: WebSocket 通知前端
        # from app.services.websocket_tool import websocket_tool
        # await websocket_tool.broadcast_device_status(sn, online=True)

    async def _on_device_offline(self, sn: str, reason: str = "timeout"):
        """设备离线事件"""
        print(f"🔴 [MQTT] 设备 {sn} 离线 (原因: {reason})")
        self.device_online_status[sn] = False
        
        # TODO: 更新数据库状态
        # from app.services.device_service import update_device_status
        # await update_device_status(sn, online=False)
        
        # TODO: WebSocket 通知前端
        # from app.services.websocket_tool import websocket_tool
        # await websocket_tool.broadcast_device_status(sn, online=False)

    async def _on_data(self, sn: Optional[str], payload: Dict[str, Any]):
        """处理设备数据消息"""
        if not sn:
            print(f"⚠️ [MQTT] 收到数据消息但缺少SN: {payload}")
            return
        print(f"📊 [MQTT] 收到设备 {sn} 的数据: {payload}")
        # TODO: 保存到数据库 / WebSocket 推送前端 / 告警处理

    async def _on_status(self, sn: Optional[str], payload: Dict[str, Any]):
        """处理设备状态消息（包括 LWT 离线消息）"""
        if not sn:
            print(f"⚠️ [MQTT] 收到状态消息但缺少SN: {payload}")
            return
        
        print(f"📡 [MQTT] 收到设备 {sn} 的状态: {payload}")
        
        # 检查是否为离线消息（包括 LWT 消息）
        status = payload.get("status", "").lower()
        if status == "offline":
            # 判断是主动离线还是 LWT（设备异常断开）
            # LWT 消息通常由 broker 在设备异常断开时自动发布
            await self._on_device_offline(sn, reason="lwt_or_offline")
        elif status == "online":
            # 设备上线消息
            pass  # 上线逻辑已在 update_device_last_seen 中处理

    async def check_device_heartbeat(self):
        """检查设备心跳超时"""
        current_time = time.time()
        offline_devices = []
        
        for sn, last_seen in self.device_last_seen.items():
            # 如果设备当前是在线状态，但超时未上报
            if self.device_online_status.get(sn, True):
                if current_time - last_seen > self.heartbeat_timeout:
                    offline_devices.append(sn)
        
        # 批量处理离线设备
        for sn in offline_devices:
            await self._on_device_offline(sn, reason="heartbeat_timeout")
        
        return len(offline_devices)

    async def heartbeat_monitor(self):
        """心跳监控任务"""
        print("[MQTT] ❤️ 心跳监控任务已启动")
        
        while self.running:
            try:
                offline_count = await self.check_device_heartbeat()
                if offline_count > 0:
                    print(f"[MQTT] 💔 检测到 {offline_count} 个设备心跳超时")
            except Exception as e:
                print(f"❌ [MQTT] 心跳检查异常: {e}")
            
            # 每30秒检查一次
            await asyncio.sleep(30)

    async def listen(self):
        """持续监听消息"""
        try:
            # 订阅主题
            await self.subscribe_topics()
            
            # 启动心跳监控任务
            heartbeat_task = asyncio.create_task(self.heartbeat_monitor())
            
            print("[MQTT] 🎧 进入监听循环...")
            
            # 保持运行
            try:
                while self.running:
                    await asyncio.sleep(1)
            finally:
                # 取消心跳监控任务
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                
        except asyncio.CancelledError:
            print("[MQTT] 监听任务被取消")
            raise
        except Exception as e:
            print(f"❌ [MQTT] 监听消息时发生错误: {e}")
            import traceback
            traceback.print_exc()
            self.running = False

    async def publish_control(self, sn: str, payload: dict):
        """后台 -> 设备，发布控制指令"""
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

    def get_device_status(self, sn: str) -> bool:
        """获取设备在线状态"""
        return self.device_online_status.get(sn, False)

    def get_all_online_devices(self) -> list:
        """获取所有在线设备列表"""
        return [sn for sn, online in self.device_online_status.items() if online]

    @staticmethod
    def parse_payload(payload: str) -> Dict[str, Any]:
        """解析 payload 为 dict"""
        try:
            return json.loads(payload)
        except Exception as e:
            return {"raw": payload}

    @staticmethod
    def extract_sn(topic: str) -> Optional[str]:
        """从 topic 中提取设备 SN"""
        parts = topic.split("/")
        if len(parts) >= 2 and parts[0] == "device":
            return parts[1]
        return None


# 全局 MQTT 服务实例
mqtt_service = MQTTService()