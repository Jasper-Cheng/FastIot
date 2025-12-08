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
from typing import Dict, Any, Optional, Callable, Awaitable
from gmqtt import Client as MQTTClient
from app.core.config import settings

# 定义处理器类型
DataHandler = Callable[[str, Dict[str, Any]], Awaitable[None]]
StatusHandler = Callable[[str, Dict[str, Any]], Awaitable[None]]


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
        
        # 设备处理器注册表（按 SN 前缀）
        self.data_handlers: Dict[str, DataHandler] = {}
        self.status_handlers: Dict[str, StatusHandler] = {}
        
        # 默认处理器
        self.default_data_handler: Optional[DataHandler] = None
        self.default_status_handler: Optional[StatusHandler] = None

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


# ==================== M701001 室内空气质量监测器处理器 ====================

async def handle_m701001_data(sn: str, payload: Dict[str, Any]):
    """处理 M701001 室内空气质量监测器数据
    
    数据格式示例:
    {'sn': 'M701001-220403-000001', 'co2': 485, 'hcho': 17, 'tvoc': 27, 'pm25': 21, 'pm10': 26, 'temp': 26.1, 'humi': 41.0}
    SN 格式: M701001-{生产日期}-{流水号}
    """
    print(f"🌡️ [M701001] 处理设备 {sn} 的空气质量数据")
    
    # 提取数据
    co2 = payload.get("co2")      # 二氧化碳 (ppm)
    hcho = payload.get("hcho")    # 甲醛 (μg/m³)
    tvoc = payload.get("tvoc")    # 总挥发性有机化合物 (μg/m³)
    pm25 = payload.get("pm25")    # PM2.5 (μg/m³)
    pm10 = payload.get("pm10")    # PM10 (μg/m³)
    temp = payload.get("temp")    # 温度 (°C)
    humi = payload.get("humi")    # 湿度 (%)
    
    print(f"   CO2: {co2} ppm, HCHO: {hcho} μg/m³, TVOC: {tvoc} μg/m³")
    print(f"   PM2.5: {pm25} μg/m³, PM10: {pm10} μg/m³")
    print(f"   温度: {temp} °C, 湿度: {humi} %")
    
    # TODO: 保存到数据库
    # from app.crud.device_data import save_device_data
    # await save_device_data(sn, payload)
    
    # 通过 WebSocket 推送给前端
    try:
        from app.services.websocket_tool import websocket_tool
        
        # 构建数据对象（移除 sn 字段，因为 deviceSn 会在 params 中）
        device_data = {
            "co2": co2,
            "hcho": hcho,
            "tvoc": tvoc,
            "pm25": pm25,
            "pm10": pm10,
            "temp": temp,
            "humi": humi
        }
        
        # 发送设备数据事件通知
        await websocket_tool.send_event_notification(
            device_sn=sn,
            data=device_data
        )
    except Exception as e:
        print(f"❌ [M701001] WebSocket 推送数据失败 ({sn}): {e}")
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
            from app.services.websocket_tool import websocket_tool
            
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
                
                # 发送 websocket message 给所有订阅了该设备的客户端，此消息为家庭消息
                await websocket_tool.send_device_alert_message(
                    device_sn=sn,
                    message_type="device.alert",
                    data={
                        "title": "设备告警",
                        "message": alert_message,
                        "level": "error",
                        "deviceId": device.id,
                        "deviceSn": sn,
                        "deviceName": device.name,
                        "messageId": created_message.id,
                        "alerts": alert_details
                    }
                )
                    
        except Exception as e:
            print(f"❌ [M701001] 处理告警失败 ({sn}): {e}")
            import traceback
            traceback.print_exc()


async def handle_m701001_status(sn: str, payload: Dict[str, Any]):
    """处理 M701001 室内空气质量监测器状态"""
    print(f"📡 [M701001] 处理设备 {sn} 的状态: {payload}")
    
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
            
            # 检查设备是否属于账号或家庭
            from app.crud.family_device import get_device_families
            device_families = await get_device_families(db, device.id)
            if device.account_id is None and len(device_families) == 0:
                print(f"⚠️ [M701001] 设备 {sn} 未绑定账号或家庭，无法更新状态")
                return
            
            # 更新设备状态
            device_status = DeviceStatus.online if status == "online" else DeviceStatus.offline
            device_update = DeviceUpdate(status=device_status)
            updated_device = await update_device(db, device.id, device_update)
            
            if updated_device:
                print(f"✅ [M701001] 设备 {sn} 状态已更新为: {device_status.value}")
            else:
                print(f"❌ [M701001] 设备 {sn} 状态更新失败")
    except Exception as e:
        print(f"❌ [M701001] 更新设备状态失败 ({sn}): {e}")
        import traceback
        traceback.print_exc()
    
    # 通过 WebSocket 通知前端
    try:
        from app.services.websocket_tool import websocket_tool
        
        # 发送设备状态变更事件通知
        await websocket_tool.send_event_notification(
            device_sn=sn,
            data={
                "status": status
            }
        )
        # print(f"✅ [M701001] 已通过 WebSocket 通知前端设备 {sn} 状态变更: {status}")
    except Exception as e:
        print(f"❌ [M701001] WebSocket 通知失败 ({sn}): {e}")
        import traceback
        traceback.print_exc()


# 注册 M701001 处理器
mqtt_service.register_data_handler("M701001", handle_m701001_data)
mqtt_service.register_status_handler("M701001", handle_m701001_status)