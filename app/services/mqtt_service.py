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
ControlHandler = Callable[[str, str, Dict[str, Any]], Awaitable[None]]  # platform, sn, payload


class MQTTService:
    def __init__(self):
        self.host = settings.MQTT_HOST
        self.port = settings.MQTT_PORT
        self.username = settings.MQTT_USERNAME
        self.password = settings.MQTT_PASSWORD

        # 分层化 topic
        self.device_sn_control = "device/{sn}/control"  # 后台 -> 设备
        self.device_sn_data = "device/{sn}/data"        # 设备 -> 后台
        self.device_sn_status = "device/{sn}/status"    # 设备 -> 后台（包含 LWT 离线消息）
        self.device_sn_config = "device/{sn}/config"    # 设备 -> 后台（配置信息）
        self.system_notice = "system/notice"           # 系统通知
        self.home_notice = "home/{home_id}/notice"     # 家庭通知
        self.web_sn_data = "web/{sn}/data"             # 后台 -> web
        self.web_sn_status = "web/{sn}/status"         # 后台 -> web
        self.web_sn_control = "web/{sn}/control"       # web -> 后台
        self.app_sn_data = "app/{sn}/data"             # 后台 -> app
        self.app_sn_status = "app/{sn}/status"         # 后台 -> app
        self.app_sn_control = "app/{sn}/control"       # app -> 后台

        self.client: Optional[MQTTClient] = None
        self.running = False
        self._connect_event = asyncio.Event()
        
        # 设备处理器注册表（按 SN 前缀）
        self.data_handlers: Dict[str, DataHandler] = {}
        self.status_handlers: Dict[str, StatusHandler] = {}
        self.control_handlers: Dict[str, ControlHandler] = {}  # 按平台（web/app）注册
        
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
                # 处理 web/app -> 后台的控制消息
                platform, sn = self.extract_platform_and_sn(topic)
                if platform and sn:
                    asyncio.create_task(self._on_control(platform, sn, parsed_payload))
                else:
                    print(f"⚠️ [MQTT] 无法从 topic {topic} 中提取平台和SN")

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
            ("web/+/control", 1),     # web -> 后台控制
            ("app/+/control", 1),     # app -> 后台控制
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

    def register_control_handler(self, platform: str, handler: ControlHandler):
        """注册控制处理器（按平台）
        
        Args:
            platform: 平台名称，如 "web"、"app"
            handler: 异步处理函数，签名为 async def handler(platform: str, sn: str, payload: dict)
        """
        self.control_handlers[platform] = handler
        print(f"[MQTT] ✅ 已注册控制处理器: {platform}")

    def set_default_control_handler(self, handler: ControlHandler):
        """设置默认控制处理器（当没有匹配的平台处理器时使用）"""
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

    async def _on_control(self, platform: str, sn: str, payload: Dict[str, Any]):
        """处理 web/app -> 后台的控制消息"""
        # 查找匹配的处理器
        handler = self.control_handlers.get(platform)
        if handler:
            try:
                await handler(platform, sn, payload)
            except Exception as e:
                print(f"❌ [MQTT] 控制处理器执行失败 ({platform}, {sn}): {e}")
                import traceback
                traceback.print_exc()
        elif self.default_control_handler:
            try:
                await self.default_control_handler(platform, sn, payload)
            except Exception as e:
                print(f"❌ [MQTT] 默认控制处理器执行失败 ({platform}, {sn}): {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ [MQTT] 未找到平台 {platform} 的控制处理器")

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

    async def publish_web_data(self, sn: str, payload: dict):
        """后台 -> web，发布设备数据"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.web_sn_data.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送设备数据给 web ({sn}): {message}")

    async def publish_web_status(self, sn: str, payload: dict):
        """后台 -> web，发布设备状态"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.web_sn_status.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送设备状态给 web ({sn}): {message}")

    async def publish_app_data(self, sn: str, payload: dict):
        """后台 -> app，发布设备数据"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.app_sn_data.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送设备数据给 app ({sn}): {message}")

    async def publish_app_status(self, sn: str, payload: dict):
        """后台 -> app，发布设备状态"""
        if not self.client or not self.running:
            print("❌ [MQTT] 客户端未连接，无法发送消息")
            return

        topic = self.app_sn_status.format(sn=sn)
        message = {**payload, "sn": sn}
        message_json = json.dumps(message, ensure_ascii=False)
        
        self.client.publish(topic, message_json, qos=1)
        print(f"✅ [MQTT] 已发送设备状态给 app ({sn}): {message}")

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
    def extract_platform_and_sn(topic: str) -> Tuple[Optional[str], Optional[str]]:
        """从 topic 中提取平台和设备 SN（用于 web/app control topic）
        
        Returns:
            (platform, sn) 元组，如果无法提取则返回 (None, None)
        """
        parts = topic.split("/")
        if len(parts) >= 3:
            platform = parts[0]  # web 或 app
            sn = parts[1]
            if platform in ["web", "app"]:
                return platform, sn
        return None, None


# 全局 MQTT 服务实例
mqtt_service = MQTTService()


# ==================== M701001 室内空气质量监测器处理器 ====================

async def handle_m701001_data(sn: str, payload: Dict[str, Any]):
    """处理 M701001 室内空气质量监测器数据
    
    数据格式示例:
    {'sn': 'M701001-220403-000001', 'co2': 485, 'hcho': 17, 'tvoc': 27, 'pm25': 21, 'pm10': 26, 'temp': 26.1, 'humi': 41.0}
    SN 格式: M701001-{生产日期}-{流水号}
    """
    # print(f"🌡️ [M701001] 处理设备 {sn} 的空气质量数据")
    
    # 提取数据
    co2 = payload.get("co2")      # 二氧化碳 (ppm)
    hcho = payload.get("hcho")    # 甲醛 (μg/m³)
    tvoc = payload.get("tvoc")    # 总挥发性有机化合物 (μg/m³)
    pm25 = payload.get("pm25")    # PM2.5 (μg/m³)
    pm10 = payload.get("pm10")    # PM10 (μg/m³)
    temp = payload.get("temp")    # 温度 (°C)
    humi = payload.get("humi")    # 湿度 (%)
    
    # print(f"   CO2: {co2} ppm, HCHO: {hcho} μg/m³, TVOC: {tvoc} μg/m³")
    # print(f"   PM2.5: {pm25} μg/m³, PM10: {pm10} μg/m³")
    # print(f"   温度: {temp} °C, 湿度: {humi} %")
    
    # TODO: 保存到数据库
    # from app.crud.device_data import save_device_data
    # await save_device_data(sn, payload)
    
    # 通过 MQTT 推送给 web/app 客户端
    try:
        # 构建数据对象
        device_data = {
            "co2": co2,
            "hcho": hcho,
            "tvoc": tvoc,
            "pm25": pm25,
            "pm10": pm10,
            "temp": temp,
            "humi": humi
        }
        
        # 发送设备数据到 web 和 app
        await mqtt_service.publish_web_data(sn, device_data)
        await mqtt_service.publish_app_data(sn, device_data)
    except Exception as e:
        print(f"❌ [M701001] MQTT 推送数据失败 ({sn}): {e}")
        import traceback
        traceback.print_exc()
    
    # 阈值告警检查
    alerts = []
    alert_details = []
    
    if co2 and co2 > 1000:
        alert_msg = f"CO2 超标: {co2} ppm (阈值: 1000 ppm)"
        alerts.append(alert_msg)
        alert_details.append({"type": "co2", "value": co2, "threshold": 1000, "unit": "ppm"})
    
    if hcho and hcho > 100:
        alert_msg = f"甲醛超标: {hcho} μg/m³ (阈值: 100 μg/m³)"
        alerts.append(alert_msg)
        alert_details.append({"type": "hcho", "value": hcho, "threshold": 100, "unit": "μg/m³"})
    
    if tvoc and tvoc > 600:
        alert_msg = f"TVOC 超标: {tvoc} μg/m³ (阈值: 600 μg/m³)"
        alerts.append(alert_msg)
        alert_details.append({"type": "tvoc", "value": tvoc, "threshold": 600, "unit": "μg/m³"})
    
    if pm25 and pm25 > 75:
        alert_msg = f"PM2.5 超标: {pm25} μg/m³ (阈值: 75 μg/m³)"
        alerts.append(alert_msg)
        alert_details.append({"type": "pm25", "value": pm25, "threshold": 75, "unit": "μg/m³"})
    
    if pm10 and pm10 > 150:
        alert_msg = f"PM10 超标: {pm10} μg/m³ (阈值: 150 μg/m³)"
        alerts.append(alert_msg)
        alert_details.append({"type": "pm10", "value": pm10, "threshold": 150, "unit": "μg/m³"})
    
    if alerts:
        print(f"⚠️ [M701001] 设备 {sn} 告警:")
        for alert in alerts:
            print(f"   - {alert}")
        
        # 插入数据库并发送 family message
        try:
            from app.db.session import AsyncSessionLocal
            from app.crud.device import get_device_by_sn
            from app.crud.device_message import create_device_message
            from app.models.device_message import DeviceMessageCreate, DeviceMessageLevel
            from app.crud.family_device import get_device_families
            
            async with AsyncSessionLocal() as db:
                # 查找设备
                device = await get_device_by_sn(db, sn)
                if not device:
                    print(f"⚠️ [M701001] 设备 {sn} 不存在于数据库中，无法插入告警消息")
                    return
                
                # 构建告警消息
                alert_message = "；".join(alerts)  # 用分号连接多个告警
                
                # 创建设备消息记录
                device_message = DeviceMessageCreate(
                    device_id=device.id,
                    level=DeviceMessageLevel.error,  # 告警使用 error 级别
                    message=alert_message,
                    detail={
                        "alerts": alert_details,
                        "deviceSn": sn,
                        "currentData": {
                            "co2": co2,
                            "hcho": hcho,
                            "tvoc": tvoc,
                            "pm25": pm25,
                            "pm10": pm10,
                            "temp": temp,
                            "humi": humi
                        }
                    }
                )
                
                created_message = await create_device_message(db, device_message)
                print(f"✅ [M701001] 告警消息已插入数据库，消息ID: {created_message.id}")
                
                # 获取设备所属的家庭，发送 MQTT 家庭通知
                device_families = await get_device_families(db, device.id)
                for family in device_families:
                    if family.id is not None:
                        try:
                            await mqtt_service.publish_home_notice(
                                home_id=str(family.id),
                                payload={
                                    "method": "family.message",
                                    "params": {
                                        "type": "device.alert",
                                        "data": {
                                            "title": "设备告警",
                                            "message": alert_message,
                                            "level": "error",
                                            "deviceId": device.id,
                                            "deviceSn": sn,
                                            "deviceName": device.name,
                                            "messageId": created_message.id,
                                            "alerts": alert_details
                                        }
                                    }
                                }
                            )
                        except Exception as e:
                            print(f"❌ [M701001] 发送家庭通知失败 (family_id={family.id}): {e}")
                    
        except Exception as e:
            print(f"❌ [M701001] 处理告警失败 ({sn}): {e}")
            import traceback
            traceback.print_exc()


async def handle_m701001_status(sn: str, payload: Dict[str, Any]):
    """处理 M701001 室内空气质量监测器状态"""
    # print(f"📡 [M701001] 处理设备 {sn} 的状态: {payload}")
    
    status = payload.get("status", "").lower()
    if status not in ["online", "offline"]:
        print(f"⚠️ [M701001] 设备 {sn} 状态值无效: {status}")
        return
    
    # 更新数据库设备状态
    try:
        from app.db.session import AsyncSessionLocal
        from app.crud.device import get_device_by_sn, update_device
        from app.models.device import DeviceUpdate, DeviceStatus
        
        async with AsyncSessionLocal() as db:
            # 查找设备
            device = await get_device_by_sn(db, sn)
            if not device:
                print(f"⚠️ [M701001] 设备 {sn} 不存在于数据库中")
                return
            
            # 检查设备是否绑定账号
            if device.account_id is None:
                print(f"⚠️ [M701001] 设备 {sn} 未绑定账号，跳过状态更新和消息发送")
                return
            
            # 更新设备状态
            device_status = DeviceStatus.online if status == "online" else DeviceStatus.offline
            device_update = DeviceUpdate(status=device_status)
            updated_device = await update_device(db, device.id, device_update)
            
            if updated_device:
                # print(f"✅ [M701001] 设备 {sn} 状态已更新为: {device_status.value}")
                pass
            else:
                print(f"❌ [M701001] 设备 {sn} 状态更新失败")
    except Exception as e:
        print(f"❌ [M701001] 更新设备状态失败 ({sn}): {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 通过 MQTT 通知 web/app 客户端
    try:
        # 发送设备状态变更到 web 和 app
        status_data = {"status": status}
        await mqtt_service.publish_web_status(sn, status_data)
        await mqtt_service.publish_app_status(sn, status_data)
    except Exception as e:
        print(f"❌ [M701001] MQTT 通知失败 ({sn}): {e}")
        import traceback
        traceback.print_exc()


# 注册 M701001 处理器
mqtt_service.register_data_handler("M701001", handle_m701001_data)
mqtt_service.register_status_handler("M701001", handle_m701001_status)