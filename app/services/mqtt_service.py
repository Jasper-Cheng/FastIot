"""
MQTT服务工具类（服务端）- 设备在线状态监控
支持：
1. LWT (Last Will) 机制：设备异常断开时通过 status 主题自动发送离线消息
2. 心跳超时检测：定期检查设备最后上报时间
3. 状态消息检测：订阅设备 status 主题，处理在线/离线状态
4. 基于 SN 前缀的处理器分发：根据设备型号前缀分发到不同处理器
"""
import asyncio
import json
import time
from typing import Dict, Any, Optional, Callable, Awaitable, Tuple
from gmqtt import Client as MQTTClient
from app.core.config import settings

# 定义处理器类型
DataHandler = Callable[[str, Dict[str, Any]], Awaitable[None]]
StatusHandler = Callable[[str, Dict[str, Any]], Awaitable[None]]
ControlHandler = Callable[[str, Dict[str, Any]], Awaitable[None]]  # sn, payload


class MQTTService:
    def __init__(self):
        self.host = settings.MQTT_HOST
        self.port = settings.MQTT_PORT
        self.username = settings.MQTT_USERNAME
        self.password = settings.MQTT_PASSWORD

        # 分层化 topic
        # 设备跟后台相关的topic
        self.device_sn_control = "device/{sn}/control"  # 后台 -> 设备（设备控制）
        self.device_sn_data = "device/{sn}/data"        # 设备 -> 后台（设备数据）
        self.device_sn_status = "device/{sn}/status"    # 设备 -> 后台（设备状态，包含 LWT 离线消息）
        self.device_sn_config = "device/{sn}/config"    # 设备 -> 后台（设备配置信息）
        # 设备跟客户端相关的topic
        # 消息相关
        self.device_sn_notice = "device/{sn}/notice"    # 后台 -> 客户端（设备消息）
        self.system_notice = "system/notice"           # 后台 -> 客户端（系统消息）
        self.home_notice = "home/{home_id}/notice"     # 后台 -> 客户端（家庭消息）
        self.client_account_notice = "client/{account_id}/notice"  # 后台 -> 客户端（个人通知）
        # 数据控制相关
        self.client_sn_data = "client/{sn}/data"       # 后台 -> 客户端（设备数据）
        self.client_sn_status = "client/{sn}/status"   # 后台 -> 客户端（设备状态）
        self.client_sn_control = "client/{sn}/control" # 客户端（web/app）-> 后台（设备控制）

        self.client: Optional[MQTTClient] = None
        self.running = False
        self._connect_event = asyncio.Event()
        
        # 设备处理器注册表（按 SN 前缀）
        self.data_handlers: Dict[str, DataHandler] = {}
        self.status_handlers: Dict[str, StatusHandler] = {}
        self.control_handlers: Dict[str, ControlHandler] = {}  # 按 SN 前缀注册
        
        # 默认处理器
        self.default_data_handler: Optional[DataHandler] = None
        self.default_status_handler: Optional[StatusHandler] = None
        self.default_control_handler: Optional[ControlHandler] = None

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
            
            # 处理不同类型的消息
            if topic.endswith("/data"):
                sn = self.extract_sn(topic)
                asyncio.create_task(self._on_data(sn, parsed_payload))
            elif topic.endswith("/status"):
                sn = self.extract_sn(topic)
                asyncio.create_task(self._on_status(sn, parsed_payload))
            elif topic.endswith("/config"):
                sn = self.extract_sn(topic)
                asyncio.create_task(self._on_config(sn, parsed_payload))
            elif topic.endswith("/control"):
                # 处理客户端（web/app）-> 后台的控制消息
                sn = self.extract_client_sn(topic)
                if sn:
                    asyncio.create_task(self._on_control(sn, parsed_payload))
                else:
                    print(f"⚠️ [MQTT] 无法从 topic {topic} 中提取SN")

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
            ("device/+/config", 1),    # 设备配置信息
            ("client/+/control", 1),   # 客户端（web/app）-> 后台控制
        ]
        
        for topic, qos in topics:
            self.client.subscribe(topic, qos=qos)
            print(f"[MQTT] 已订阅: {topic}")
        
        await asyncio.sleep(0.5)

    def register_data_handler(self, sn_prefix: str, handler: DataHandler):
        """注册数据处理器（按 SN 前缀）
        
        Args:
            sn_prefix: 设备 SN 前缀，如 "M70"、"AIR" 等
            handler: 异步处理函数，签名为 async def handler(sn: str, payload: dict)
        """
        self.data_handlers[sn_prefix] = handler
        print(f"[MQTT] ✅ 已注册数据处理器: {sn_prefix}")

    def register_status_handler(self, sn_prefix: str, handler: StatusHandler):
        """注册状态处理器（按 SN 前缀）
        
        Args:
            sn_prefix: 设备 SN 前缀，如 "M70"、"AIR" 等
            handler: 异步处理函数，签名为 async def handler(sn: str, payload: dict)
        """
        self.status_handlers[sn_prefix] = handler
        print(f"[MQTT] ✅ 已注册状态处理器: {sn_prefix}")

    def set_default_data_handler(self, handler: DataHandler):
        """设置默认数据处理器（当没有匹配的前缀处理器时使用）"""
        self.default_data_handler = handler
        print("[MQTT] ✅ 已设置默认数据处理器")

    def set_default_status_handler(self, handler: StatusHandler):
        """设置默认状态处理器（当没有匹配的前缀处理器时使用）"""
        self.default_status_handler = handler
        print("[MQTT] ✅ 已设置默认状态处理器")

    def register_control_handler(self, sn_prefix: str, handler: ControlHandler):
        """注册控制处理器（按 SN 前缀）
        
        Args:
            sn_prefix: 设备 SN 前缀，如 "M70"、"AIR" 等
            handler: 异步处理函数，签名为 async def handler(sn: str, payload: dict)
        """
        self.control_handlers[sn_prefix] = handler
        print(f"[MQTT] ✅ 已注册控制处理器: {sn_prefix}")

    def set_default_control_handler(self, handler: ControlHandler):
        """设置默认控制处理器（当没有匹配的前缀处理器时使用）"""
        self.default_control_handler = handler
        print("[MQTT] ✅ 已设置默认控制处理器")

    def _get_handler_for_sn(self, sn: str, handlers: Dict[str, Callable]) -> Optional[Callable]:
        """根据 SN 前缀匹配处理器
        
        按前缀长度降序排列，优先匹配更具体的前缀
        例如：SN="M701001" 会优先匹配 "M701" 而不是 "M70"
        """
        for prefix in sorted(handlers.keys(), key=len, reverse=True):
            if sn.startswith(prefix):
                return handlers[prefix]
        return None

    async def _on_data(self, sn: Optional[str], payload: Dict[str, Any]):
        """处理设备数据消息"""
        if not sn:
            print(f"⚠️ [MQTT] 收到数据消息但缺少SN: {payload}")
            return
        
        # 查找匹配的处理器
        handler = self._get_handler_for_sn(sn, self.data_handlers)
        if handler:
            try:
                await handler(sn, payload)
            except Exception as e:
                print(f"❌ [MQTT] 数据处理器执行失败 ({sn}): {e}")
                import traceback
                traceback.print_exc()
        elif self.default_data_handler:
            try:
                await self.default_data_handler(sn, payload)
            except Exception as e:
                print(f"❌ [MQTT] 默认数据处理器执行失败 ({sn}): {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ [MQTT] 未找到设备 {sn} 的数据处理器")

    async def _on_status(self, sn: Optional[str], payload: Dict[str, Any]):
        """处理设备状态消息（包括 LWT 离线消息）"""
        if not sn:
            print(f"⚠️ [MQTT] 收到状态消息但缺少SN: {payload}")
            return
        
        # 查找匹配的处理器
        handler = self._get_handler_for_sn(sn, self.status_handlers)
        if handler:
            try:
                await handler(sn, payload)
            except Exception as e:
                print(f"❌ [MQTT] 状态处理器执行失败 ({sn}): {e}")
                import traceback
                traceback.print_exc()
        elif self.default_status_handler:
            try:
                await self.default_status_handler(sn, payload)
            except Exception as e:
                print(f"❌ [MQTT] 默认状态处理器执行失败 ({sn}): {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ [MQTT] 未找到设备 {sn} 的状态处理器")

    async def _on_config(self, sn: Optional[str], payload: Dict[str, Any]):
        """处理设备配置信息消息，保存到 device_network 表"""
        if not sn:
            print(f"⚠️ [MQTT] 收到配置消息但缺少SN: {payload}")
            return
        
        # print(f"⚙️ [MQTT] 处理设备 {sn} 的配置信息: {payload}")
        
        try:
            from app.db.session import AsyncSessionLocal
            from app.crud.device import get_device_by_sn
            from app.db.models.device_network import DeviceNetwork
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as db:
                # 验证设备是否存在
                device = await get_device_by_sn(db, sn)
                if not device:
                    print(f"⚠️ [MQTT] 设备 {sn} 不存在于数据库中，无法保存配置信息")
                    return
                
                # 查询是否已存在网络信息记录
                result = await db.execute(
                    select(DeviceNetwork).filter(DeviceNetwork.sn == sn)
                )
                device_network = result.scalar_one_or_none()
                
                # 提取配置信息（只更新 payload 中提供的字段）
                update_data = {}
                if "ip" in payload:
                    update_data["ip"] = payload.get("ip")
                if "mac" in payload:
                    update_data["mac"] = payload.get("mac")
                if "ble_name" in payload or "bleName" in payload:
                    update_data["ble_name"] = payload.get("ble_name") or payload.get("bleName")
                if "wifi_name" in payload or "wifiName" in payload:
                    update_data["wifi_name"] = payload.get("wifi_name") or payload.get("wifiName")
                if "wifi_password" in payload or "wifiPassword" in payload:
                    update_data["wifi_password"] = payload.get("wifi_password") or payload.get("wifiPassword")
                if "mqtt_broker" in payload or "mqttBroker" in payload:
                    update_data["mqtt_broker"] = payload.get("mqtt_broker") or payload.get("mqttBroker")
                if "mqtt_port" in payload or "mqttPort" in payload:
                    mqtt_port = payload.get("mqtt_port") or payload.get("mqttPort")
                    if mqtt_port is not None:
                        try:
                            update_data["mqtt_port"] = int(mqtt_port)
                        except (ValueError, TypeError):
                            print(f"⚠️ [MQTT] 无效的 mqtt_port 值: {mqtt_port}")
                if "firmware" in payload:
                    update_data["firmware"] = payload.get("firmware")
                
                if device_network:
                    # 更新现有记录
                    for key, value in update_data.items():
                        setattr(device_network, key, value)
                    # print(f"✅ [MQTT] 已更新设备 {sn} 的网络配置信息")
                else:
                    # 创建新记录
                    device_network = DeviceNetwork(
                        sn=sn,
                        ip=update_data.get("ip"),
                        mac=update_data.get("mac"),
                        ble_name=update_data.get("ble_name"),
                        wifi_name=update_data.get("wifi_name"),
                        wifi_password=update_data.get("wifi_password"),
                        mqtt_broker=update_data.get("mqtt_broker"),
                        mqtt_port=update_data.get("mqtt_port"),
                        firmware=update_data.get("firmware")
                    )
                    db.add(device_network)
                    # print(f"✅ [MQTT] 已创建设备 {sn} 的网络配置信息")
                
                await db.commit()
                print(f"📝 [MQTT] 设备 {sn} 配置信息已保存: {update_data}")
                
        except Exception as e:
            print(f"❌ [MQTT] 保存设备配置信息失败 ({sn}): {e}")
            import traceback
            traceback.print_exc()

    async def _on_control(self, sn: str, payload: Dict[str, Any]):
        """处理客户端（web/app）-> 后台的控制消息"""
        # 查找匹配的处理器
        handler = self._get_handler_for_sn(sn, self.control_handlers)
        if handler:
            try:
                await handler(sn, payload)
            except Exception as e:
                print(f"❌ [MQTT] 控制处理器执行失败 ({sn}): {e}")
                import traceback
                traceback.print_exc()
        elif self.default_control_handler:
            try:
                await self.default_control_handler(sn, payload)
            except Exception as e:
                print(f"❌ [MQTT] 默认控制处理器执行失败 ({sn}): {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ [MQTT] 未找到设备 {sn} 的控制处理器")

    async def listen(self):
        """持续监听消息"""
        try:
            # 订阅主题
            await self.subscribe_topics()
            
            print("[MQTT] 🎧 进入监听循环...")
            
            # 保持运行
            while self.running:
                await asyncio.sleep(1)
                
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

        topic = self.device_sn_control.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送控制命令给 {sn}: {message}")

    async def publish_home_notice(self, home_id: str, payload: dict):
        """后台 -> 家庭，发布家庭通知"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.home_notice.format(home_id=home_id)
        message = {**payload, "home_id": home_id}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送家庭通知给 {home_id}: {message}")

    async def publish_system_notice(self, payload: dict):
        """后台 -> 系统，发布系统通知"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.system_notice
        message_json = json.dumps(payload, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送系统通知: {payload}")

    async def publish_client_notice(self, account_id: int, payload: dict):
        """后台 -> 客户端，发布个人消息"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.client_account_notice.format(account_id=account_id)
        message = {**payload, "account_id": account_id}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送个人消息给账号 {account_id}: {message}")

    async def publish_device_notice(self, sn: str, payload: dict):
        """后台 -> 客户端，发布设备消息"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.device_sn_notice.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送设备消息 ({sn}): {message}")

    async def publish_client_data(self, sn: str, payload: dict):
        """后台 -> 客户端（web/app），发布设备数据"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.client_sn_data.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送设备数据给客户端 ({sn}): {message}")

    async def publish_client_status(self, sn: str, payload: dict):
        """后台 -> 客户端（web/app），发布设备状态"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.client_sn_status.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送设备状态给客户端 ({sn}): {message}")

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
        except Exception as e:
            return {"raw": payload}

    @staticmethod
    def extract_sn(topic: str) -> Optional[str]:
        """从 topic 中提取设备 SN（用于 device topic）"""
        parts = topic.split("/")
        if len(parts) >= 2 and parts[0] == "device":
            return parts[1]
        return None
    
    @staticmethod
    def extract_client_sn(topic: str) -> Optional[str]:
        """从 topic 中提取设备 SN（用于 client topic）"""
        parts = topic.split("/")
        if len(parts) >= 3 and parts[0] == "client":
            return parts[1]
        return None


# 全局 MQTT 服务实例
mqtt_service = MQTTService()


# 导入所有设备处理器（自动注册）
# 注意：必须在 mqtt_service 实例创建后导入，以确保处理器可以访问 mqtt_service
from app.services.mqtt_handlers import *  # noqa: F401, F403