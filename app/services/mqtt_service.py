"""
MQTT服务工具类
支持设备状态监控、传感器数据接收、设备控制等功能
基于设备SN（序列号）的主题结构
"""
import json
import threading
import time
from typing import Callable, Dict, Any, Optional
import paho.mqtt.client as mqtt
from app.core.config import settings


# 设备SN定义
class DeviceSN:
    """设备序列号常量"""
    LED_SN = "LED001"
    SENSOR_SN = "M701001"


class MqttService:
    """MQTT服务类"""
    
    def __init__(self):
        self._client: Optional[mqtt.Client] = None
        self._connected: bool = False
        self._lock = threading.Lock()
        
        # MQTT Broker配置
        self._host = settings.MQTT_HOST
        self._port = settings.MQTT_PORT
        self._username = settings.MQTT_USERNAME
        self._password = settings.MQTT_PASSWORD
        self._client_id = settings.MQTT_CLIENT_ID  # 必传，用于区分不同设备
        self._keepalive = settings.MQTT_KEEPALIVE
        self._prefix = settings.MQTT_PREFIX
        
        # 消息处理器
        self._message_handlers: Dict[str, Callable[[str, Dict[str, Any]], None]] = {}
        
    def connect(self) -> None:
        """连接到MQTT Broker"""
        with self._lock:
            if self._connected:
                return
                
            client = mqtt.Client(client_id=self._client_id, clean_session=True)
            
            # 设置认证
            if self._username:
                client.username_pw_set(self._username, self._password or None)
            
            # 设置回调函数
            def on_connect(cli: mqtt.Client, userdata, flags, rc):
                if rc == 0:
                    self._connected = True
                    print(f"✅ [MQTT] 连接成功: {self._host}:{self._port}")
                    # 订阅所有需要的主题
                    self._subscribe_all_topics(cli)
                else:
                    print(f"❌ [MQTT] 连接失败，返回码: {rc}")
                    self._connected = False
            
            def on_disconnect(cli: mqtt.Client, userdata, rc):
                self._connected = False
                print(f"⚠️ [MQTT] 连接断开，返回码: {rc}")
            
            def on_message(cli: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
                try:
                    topic = msg.topic
                    payload = msg.payload.decode("utf-8")
                    data = json.loads(payload) if payload else {}
                    
                    # 调用对应的消息处理器
                    if topic in self._message_handlers:
                        self._message_handlers[topic](topic, data)
                    else:
                        # 尝试匹配通配符主题
                        for pattern, handler in self._message_handlers.items():
                            if self._topic_matches(pattern, topic):
                                handler(topic, data)
                                break
                except json.JSONDecodeError:
                    # 如果不是JSON格式，尝试作为字符串处理
                    data = {"raw": msg.payload.decode("utf-8", errors="ignore")}
                    if topic in self._message_handlers:
                        self._message_handlers[topic](topic, data)
                except Exception as e:
                    print(f"❌ [MQTT] 处理消息失败: {e}")
            
            client.on_connect = on_connect
            client.on_disconnect = on_disconnect
            client.on_message = on_message
            
            # 连接到Broker
            try:
                client.connect(self._host, self._port, keepalive=self._keepalive)
                client.loop_start()
                
                # 等待连接建立
                for _ in range(20):
                    if self._connected:
                        break
                    time.sleep(0.05)
                
                self._client = client
            except Exception as e:
                print(f"❌ [MQTT] 连接异常: {e}")
                self._connected = False
    
    def _subscribe_all_topics(self, client: mqtt.Client):
        """订阅所有需要的主题"""
        # 订阅设备状态主题
        status_topic = f"{self._prefix}/status"
        client.subscribe(status_topic, qos=0)
        print(f"📡 [MQTT] 订阅主题: {status_topic}")
        
        # 订阅传感器数据主题
        sensor_data_topic = f"{self._prefix}/{DeviceSN.SENSOR_SN}/data"
        client.subscribe(sensor_data_topic, qos=0)
        print(f"📡 [MQTT] 订阅主题: {sensor_data_topic}")
    
    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """检查主题是否匹配模式（支持+和#通配符）"""
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")
        
        if len(pattern_parts) != len(topic_parts):
            # 检查是否有#通配符
            if "#" in pattern:
                pattern_idx = pattern_parts.index("#")
                return pattern_parts[:pattern_idx] == topic_parts[:pattern_idx]
            return False
        
        for p, t in zip(pattern_parts, topic_parts):
            if p == "+" or p == "#":
                continue
            if p != t:
                return False
        return True
    
    def disconnect(self) -> None:
        """断开MQTT连接"""
        with self._lock:
            if not self._client:
                return
            try:
                self._client.loop_stop()
                self._client.disconnect()
                print("🔌 [MQTT] 连接已断开")
            except Exception as e:
                print(f"❌ [MQTT] 断开连接异常: {e}")
            finally:
                self._client = None
                self._connected = False
    
    def ensure_connected(self) -> None:
        """确保已连接"""
        if not self._connected or not self._client:
            self.connect()
    
    def publish_json(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> bool:
        """发布JSON消息到指定主题"""
        self.ensure_connected()
        if not self._client:
            return False
        
        try:
            message = json.dumps(payload, ensure_ascii=False)
            result = self._client.publish(topic, message, qos=qos, retain=retain)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✅ [MQTT] 发布消息到 {topic}: {payload}")
                return True
            else:
                print(f"❌ [MQTT] 发布消息失败，返回码: {result.rc}")
                return False
        except Exception as e:
            print(f"❌ [MQTT] 发布消息异常: {e}")
            return False
    
    def subscribe(self, topic: str, handler: Callable[[str, Dict[str, Any]], None], qos: int = 0) -> None:
        """订阅主题并设置消息处理器"""
        self.ensure_connected()
        if not self._client:
            return
        
        # 注册消息处理器
        self._message_handlers[topic] = handler
        
        # 订阅主题
        try:
            self._client.subscribe(topic, qos=qos)
            print(f"📡 [MQTT] 订阅主题: {topic}")
        except Exception as e:
            print(f"❌ [MQTT] 订阅主题失败: {e}")
    
    # ==================== 主题构建方法 ====================
    
    def get_status_topic(self) -> str:
        """获取设备状态主题"""
        return f"{self._prefix}/status"
    
    def get_sensor_data_topic(self, sensor_sn: str = DeviceSN.SENSOR_SN) -> str:
        """获取传感器数据主题"""
        return f"{self._prefix}/{sensor_sn}/data"
    
    def get_led_control_topic(self, led_sn: str = DeviceSN.LED_SN) -> str:
        """获取LED控制主题"""
        return f"{self._prefix}/{led_sn}/control"
    
    def get_sensor_query_topic(self, sensor_sn: str = DeviceSN.SENSOR_SN) -> str:
        """获取传感器查询主题"""
        return f"{self._prefix}/{sensor_sn}/query"
    
    def get_sensor_control_topic(self, sensor_sn: str = DeviceSN.SENSOR_SN) -> str:
        """获取传感器控制主题"""
        return f"{self._prefix}/{sensor_sn}/control"
    
    # ==================== 便捷发布方法 ====================
    
    def publish_led_control(self, led_sn: str, command: Dict[str, Any], qos: int = 0) -> bool:
        """发布LED控制命令"""
        topic = self.get_led_control_topic(led_sn)
        return self.publish_json(topic, command, qos=qos)
    
    def publish_sensor_query(self, sensor_sn: str, query: Dict[str, Any], qos: int = 0) -> bool:
        """发布传感器查询命令"""
        topic = self.get_sensor_query_topic(sensor_sn)
        return self.publish_json(topic, query, qos=qos)
    
    def publish_sensor_control(self, sensor_sn: str, command: Dict[str, Any], qos: int = 0) -> bool:
        """发布传感器控制命令"""
        topic = self.get_sensor_control_topic(sensor_sn)
        return self.publish_json(topic, command, qos=qos)
    
    # ==================== 便捷订阅方法 ====================
    
    def subscribe_status(self, handler: Callable[[str, Dict[str, Any]], None]) -> None:
        """订阅设备状态主题"""
        topic = self.get_status_topic()
        self.subscribe(topic, handler)
    
    def subscribe_sensor_data(self, sensor_sn: str, handler: Callable[[str, Dict[str, Any]], None]) -> None:
        """订阅传感器数据主题"""
        topic = self.get_sensor_data_topic(sensor_sn)
        self.subscribe(topic, handler)
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
    
    @property
    def prefix(self) -> str:
        """获取MQTT主题前缀"""
        return self._prefix


# 全局MQTT服务实例
mqtt_service = MqttService()

