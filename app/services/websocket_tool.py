"""
WebSocket工具类
支持收发信息、心跳机制、连接管理
支持标准请求-响应模式：property.get, service.invoke, event.subscribe
支持模拟响应功能
"""
import json
import asyncio
import uuid
import random
from datetime import datetime, timedelta
from typing import Dict, Set, Callable, Any, Optional, List
from fastapi import WebSocket, WebSocketDisconnect
from app.utils.time_utils import get_local_time


class WebSocketTool:
    """WebSocket工具类"""
    
    def __init__(self):
        # 活跃连接管理
        self.active_connections: Dict[str, WebSocket] = {}
        # 连接元数据
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        # 方法处理器
        self.method_handlers: Dict[str, Callable] = {}
        # 事件订阅管理
        self.event_subscriptions: Dict[str, Set[str]] = {}  # device_id -> set of client_ids
        # 待处理请求
        self.pending_requests: Dict[str, Dict[str, Any]] = {}  # request_id -> request_info
        # 心跳超时时间（秒）
        self.heartbeat_timeout = 60  # 默认60秒超时
        
        # 模拟功能相关
        self.mock_mode = False  # 是否启用模拟模式
        self.mock_devices: Dict[str, Dict[str, Any]] = {}  # 模拟设备数据
        self.mock_history: Dict[str, List[Dict[str, Any]]] = {
            "property": [],
            "service": [],
            "event": []
        }
        
    async def connect(self, websocket: WebSocket, client_id: str, metadata: Optional[Dict[str, Any]] = None):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = {
            "connected_at": get_local_time(),
            "last_heartbeat": get_local_time(),
            "metadata": metadata or {}
        }
        
        print(f"✅ [WebSocket] 客户端 {client_id} 已连接")
        
    def disconnect(self, client_id: str):
        """断开WebSocket连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
            
        # 清理事件订阅
        for device_id in list(self.event_subscriptions.keys()):
            self.event_subscriptions[device_id].discard(client_id)
            if not self.event_subscriptions[device_id]:
                del self.event_subscriptions[device_id]
            
        print(f"❌ [WebSocket] 客户端 {client_id} 已断开")
        
    async def send_message(self, client_id: str, message: Dict[str, Any]) -> bool:
        """发送消息给指定客户端"""
        if client_id not in self.active_connections:
            print(f"❌ [WebSocket] 客户端 {client_id} 未连接")
            return False
            
        try:
            websocket = self.active_connections[client_id]
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
            print(f"✅ [WebSocket] 消息已发送给客户端 {client_id}: {message}")
            return True
        except Exception as e:
            print(f"❌ [WebSocket] 发送消息失败: {e}")
            self.disconnect(client_id)
            return False
            
    async def broadcast_message(self, message: Dict[str, Any], exclude_clients: Optional[Set[str]] = None):
        """广播消息给所有客户端"""
        exclude_clients = exclude_clients or set()
        disconnected_clients = []
        
        for client_id in list(self.active_connections.keys()):
            if client_id not in exclude_clients:
                success = await self.send_message(client_id, message)
                if not success:
                    disconnected_clients.append(client_id)
                    
        # 清理断开的连接
        for client_id in disconnected_clients:
            self.disconnect(client_id)
            
        
    def register_method_handler(self, method: str, handler: Callable):
        """注册方法处理器"""
        self.method_handlers[method] = handler
        print(f"✅ [WebSocket] 注册方法处理器: {method}")
        
    async def send_response(self, client_id: str, request_id: str, method: str, params: Dict[str, Any], success: bool = True, error: Optional[str] = None):
        """发送响应消息"""
        response = {
            "id": request_id,
            "method": method,
            "params": params,
            "timestamp": int(get_local_time().timestamp() * 1000)
        }
        
        if not success and error:
            response["error"] = {
                "code": -1,
                "message": error
            }
            
        await self.send_message(client_id, response)
        
    async def send_event_notification(self, device_id: str, event_type: str, data: Dict[str, Any]):
        """发送事件通知给订阅的客户端"""
        if device_id not in self.event_subscriptions:
            return
            
        event_id = f"evt_{uuid.uuid4().hex[:8]}"
        event_message = {
            "id": event_id,
            "method": "event.notify",
            "params": {
                "deviceId": device_id,
                "eventType": event_type,
                "data": data,
                "occurredAt": int(get_local_time().timestamp() * 1000)
            },
            "timestamp": int(get_local_time().timestamp() * 1000)
        }
        
        # 发送给所有订阅该设备的客户端
        for client_id in self.event_subscriptions[device_id]:
            await self.send_message(client_id, event_message)
            
    def subscribe_to_device_events(self, client_id: str, device_id: str, event_types: List[str]):
        """订阅设备事件"""
        if device_id not in self.event_subscriptions:
            self.event_subscriptions[device_id] = set()
        self.event_subscriptions[device_id].add(client_id)
        print(f"✅ [WebSocket] 客户端 {client_id} 订阅设备 {device_id} 事件: {event_types}")
        
    def unsubscribe_from_device_events(self, client_id: str, device_id: str):
        """取消订阅设备事件"""
        if device_id in self.event_subscriptions:
            self.event_subscriptions[device_id].discard(client_id)
            if not self.event_subscriptions[device_id]:
                del self.event_subscriptions[device_id]
        print(f"❌ [WebSocket] 客户端 {client_id} 取消订阅设备 {device_id} 事件")
        
    async def handle_message(self, client_id: str, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            
            # 处理心跳包
            if data.get("method") == "ping":
                await self._handle_ping(client_id, data)
                return
            
            # 处理标准请求格式
            if "method" in data and "id" in data:
                await self._handle_standard_request(client_id, data)
            else:
                print(f"⚠️ [WebSocket] 不支持的消息格式，需要包含 method 和 id 字段")
                
        except json.JSONDecodeError:
            print(f"❌ [WebSocket] 无效的JSON消息: {message}")
        except Exception as e:
            print(f"❌ [WebSocket] 处理消息失败: {e}")
            
    async def _handle_ping(self, client_id: str, data: Dict[str, Any]):
        """处理心跳包"""
        request_id = data.get("id", "ping")
        
        # 更新最后心跳时间
        if client_id in self.connection_metadata:
            self.connection_metadata[client_id]["last_heartbeat"] = get_local_time()
        
        # 发送pong响应
        pong_response = {
            "id": request_id,
            "method": "pong",
            "timestamp": int(get_local_time().timestamp() * 1000)
        }
        
        await self.send_message(client_id, pong_response)
        print(f"💓 [WebSocket] 客户端 {client_id} 心跳包已响应")
            
    async def _handle_standard_request(self, client_id: str, data: Dict[str, Any]):
        """处理标准请求格式"""
        request_id = data.get("id")
        method = data.get("method")
        params = data.get("params", {})
        
        print(f"📨 [WebSocket] 客户端 {client_id} 请求: {method} (ID: {request_id})")
        
        # 存储请求信息
        self.pending_requests[request_id] = {
            "client_id": client_id,
            "method": method,
            "timestamp": get_local_time(),
            "params": params
        }
        
        try:
            # 调用对应的方法处理器
            if method in self.method_handlers:
                await self.method_handlers[method](client_id, request_id, params)
            else:
                await self.send_response(
                    client_id, 
                    request_id, 
                    method, 
                    {}, 
                    success=False, 
                    error=f"Unknown method: {method}"
                )
        except Exception as e:
            print(f"❌ [WebSocket] 处理请求失败: {e}")
            await self.send_response(
                client_id, 
                request_id, 
                method, 
                {}, 
                success=False, 
                error=f"Internal error: {str(e)}"
            )
        finally:
            # 清理请求记录
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
            
                
    def get_connection_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """获取连接信息"""
        if client_id not in self.connection_metadata:
            return None
            
        metadata = self.connection_metadata[client_id].copy()
        metadata["is_connected"] = client_id in self.active_connections
        return metadata
        
    def get_all_connections(self) -> Dict[str, Dict[str, Any]]:
        """获取所有连接信息"""
        return {
            client_id: self.get_connection_info(client_id)
            for client_id in self.connection_metadata.keys()
        }
        
    async def check_heartbeat_timeouts(self):
        """检查心跳超时并断开连接"""
        current_time = get_local_time()
        timeout_clients = []
        
        for client_id, metadata in self.connection_metadata.items():
            if client_id not in self.active_connections:
                continue
                
            last_heartbeat = metadata.get("last_heartbeat")
            if last_heartbeat:
                time_since_heartbeat = (current_time - last_heartbeat).total_seconds()
                if time_since_heartbeat > self.heartbeat_timeout:
                    timeout_clients.append(client_id)
        
        # 断开超时的连接
        for client_id in timeout_clients:
            print(f"⚠️ [WebSocket] 客户端 {client_id} 心跳超时，断开连接")
            await self._force_disconnect(client_id)
            
        return len(timeout_clients)
        
    async def _force_disconnect(self, client_id: str):
        """强制断开连接"""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.close(code=1000, reason="Heartbeat timeout")
            except Exception as e:
                print(f"❌ [WebSocket] 强制断开连接失败: {e}")
            finally:
                self.disconnect(client_id)
                
    def set_heartbeat_timeout(self, timeout_seconds: int):
        """设置心跳超时时间"""
        self.heartbeat_timeout = timeout_seconds
        print(f"✅ [WebSocket] 心跳超时设置为 {timeout_seconds} 秒")
    
    # ==================== 模拟功能相关方法 ====================
    
    def enable_mock_mode(self, enabled: bool = True):
        """启用或禁用模拟模式"""
        self.mock_mode = enabled
        print(f"✅ [WebSocket] 模拟模式 {'启用' if enabled else '禁用'}")
    
    def initialize_mock_devices(self, device_configs: List[Dict[str, Any]]):
        """初始化模拟设备数据"""
        for config in device_configs:
            device_id = config.get("deviceId")
            if device_id:
                self.mock_devices[device_id] = {
                    "deviceId": device_id,
                    "name": config.get("name", f"设备_{device_id}"),
                    "type": config.get("type", "sensor"),
                    "status": config.get("status", "online"),
                    "properties": config.get("properties", {}),
                    "services": config.get("services", []),
                    "events": config.get("events", []),
                    "last_update": get_local_time(),
                    "simulation_config": config.get("simulation", {})
                }
        print(f"✅ [WebSocket] 已初始化 {len(device_configs)} 个模拟设备")
    
    def _generate_mock_property_value(self, property_name: str) -> Any:
        """根据属性名生成模拟值"""
        property_name_lower = property_name.lower()
        
        if "temperature" in property_name_lower:
            return round(random.uniform(15.0, 35.0), 1)
        elif "humidity" in property_name_lower:
            return random.randint(30, 90)
        elif "pressure" in property_name_lower:
            return round(random.uniform(950.0, 1050.0), 1)
        elif "voltage" in property_name_lower:
            return round(random.uniform(3.0, 5.0), 2)
        elif "current" in property_name_lower:
            return round(random.uniform(0.1, 2.0), 3)
        elif "power" in property_name_lower:
            return round(random.uniform(0.5, 10.0), 2)
        elif "status" in property_name_lower:
            return random.choice(["online", "offline", "error", "maintenance"])
        elif "battery" in property_name_lower:
            return random.randint(0, 100)
        elif "signal" in property_name_lower:
            return random.randint(-100, -30)
        elif "speed" in property_name_lower:
            return random.randint(0, 100)
        elif "count" in property_name_lower:
            return random.randint(0, 1000)
        elif "level" in property_name_lower:
            return random.randint(0, 100)
        elif "switch" in property_name_lower or "enable" in property_name_lower:
            return random.choice([True, False])
        # 空调相关属性
        elif "mode" in property_name_lower:
            return random.choice(["cool", "heat", "fan", "auto", "dry"])
        elif "fanspeed" in property_name_lower or "fan_speed" in property_name_lower:
            return random.choice(["low", "medium", "high", "auto"])
        elif "swing" in property_name_lower:
            return random.choice([True, False])
        elif "timer" in property_name_lower:
            return random.choice([True, False])
        elif "energy" in property_name_lower and "saving" in property_name_lower:
            return random.choice([True, False])
        elif "indoor" in property_name_lower and "temperature" in property_name_lower:
            return round(random.uniform(18.0, 30.0), 1)
        elif "outdoor" in property_name_lower and "temperature" in property_name_lower:
            return round(random.uniform(25.0, 40.0), 1)
        elif "filter" in property_name_lower and "status" in property_name_lower:
            return random.choice(["good", "need_clean", "need_replace"])
        elif "wifi" in property_name_lower and "signal" in property_name_lower:
            return random.randint(-80, -30)
        elif "consumption" in property_name_lower or "power" in property_name_lower:
            return round(random.uniform(0.5, 3.0), 2)
        else:
            return f"mock_value_{random.randint(1, 100)}"
    
    def _generate_mock_service_result(self, device_id: str, service_name: str, 
                                    arguments: Dict[str, Any]) -> Dict[str, Any]:
        """生成模拟服务调用结果"""
        service_name_lower = service_name.lower()
        
        if "reboot" in service_name_lower:
            delay = arguments.get("delay", 0)
            return {
                "status": "success",
                "message": f"设备将在 {delay} 秒后重启",
                "restartTime": int((get_local_time() + timedelta(seconds=delay)).timestamp() * 1000)
            }
        elif "set" in service_name_lower and "temperature" in service_name_lower:
            temperature = arguments.get("temperature", 20)
            return {
                "status": "success",
                "message": f"温度已设置为 {temperature}°C",
                "newTemperature": temperature
            }
        elif "start" in service_name_lower:
            return {
                "status": "success",
                "message": "服务已启动",
                "startTime": int(get_local_time().timestamp() * 1000)
            }
        elif "stop" in service_name_lower:
            return {
                "status": "success",
                "message": "服务已停止",
                "stopTime": int(get_local_time().timestamp() * 1000)
            }
        elif "reset" in service_name_lower:
            return {
                "status": "success",
                "message": "设备已重置",
                "resetTime": int(get_local_time().timestamp() * 1000)
            }
        elif "update" in service_name_lower:
            version = arguments.get("version", "1.0.0")
            return {
                "status": "success",
                "message": f"固件已更新到版本 {version}",
                "newVersion": version,
                "updateTime": int(get_local_time().timestamp() * 1000)
            }
        # 空调相关服务
        elif "turnon" in service_name_lower or "turn_on" in service_name_lower:
            return {
                "status": "success",
                "message": "空调已开启",
                "powerOnTime": int(get_local_time().timestamp() * 1000)
            }
        elif "turnoff" in service_name_lower or "turn_off" in service_name_lower:
            return {
                "status": "success",
                "message": "空调已关闭",
                "powerOffTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setmode" in service_name_lower or "set_mode" in service_name_lower:
            mode = arguments.get("mode", "cool")
            return {
                "status": "success",
                "message": f"空调模式已设置为 {mode}",
                "newMode": mode,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setfanspeed" in service_name_lower or "set_fan_speed" in service_name_lower:
            fan_speed = arguments.get("fanSpeed", "auto")
            return {
                "status": "success",
                "message": f"风扇速度已设置为 {fan_speed}",
                "newFanSpeed": fan_speed,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setswing" in service_name_lower or "set_swing" in service_name_lower:
            swing = arguments.get("swing", False)
            return {
                "status": "success",
                "message": f"摆风功能已{'开启' if swing else '关闭'}",
                "swingEnabled": swing,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "settimer" in service_name_lower or "set_timer" in service_name_lower:
            timer = arguments.get("timer", False)
            timer_hours = arguments.get("hours", 0)
            return {
                "status": "success",
                "message": f"定时器已{'开启' if timer else '关闭'}{f'，设置为 {timer_hours} 小时' if timer and timer_hours > 0 else ''}",
                "timerEnabled": timer,
                "timerHours": timer_hours,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setenergysaving" in service_name_lower or "set_energy_saving" in service_name_lower:
            energy_saving = arguments.get("energySaving", True)
            return {
                "status": "success",
                "message": f"节能模式已{'开启' if energy_saving else '关闭'}",
                "energySavingEnabled": energy_saving,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "cleanfilter" in service_name_lower or "clean_filter" in service_name_lower:
            return {
                "status": "success",
                "message": "滤网清洁提醒已重置",
                "filterStatus": "good",
                "cleanTime": int(get_local_time().timestamp() * 1000)
            }
        else:
            return {
                "status": "success",
                "message": f"服务 {service_name} 执行成功",
                "executionTime": int(get_local_time().timestamp() * 1000)
            }
    
    def _generate_mock_event_data(self, device_id: str, event_type: str, 
                                base_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成模拟事件数据"""
        event_type_lower = event_type.lower()
        
        # 基础事件数据
        event_data = {
            "deviceId": device_id,
            "eventType": event_type,
            "timestamp": int(get_local_time().timestamp() * 1000),
            **base_data
        }
        
        if "alarm" in event_type_lower or "alert" in event_type_lower:
            event_data.update({
                "severity": random.choice(["low", "medium", "high", "critical"]),
                "description": f"设备 {device_id} 发生 {event_type} 事件",
                "alarmCode": f"ALM_{random.randint(1000, 9999)}"
            })
        elif "status" in event_type_lower:
            event_data.update({
                "oldStatus": random.choice(["online", "offline", "error"]),
                "newStatus": random.choice(["online", "offline", "error"]),
                "reason": random.choice(["manual", "automatic", "scheduled", "error"])
            })
        elif "data" in event_type_lower or "sensor" in event_type_lower:
            event_data.update({
                "sensorData": {
                    "temperature": round(random.uniform(15.0, 35.0), 1),
                    "humidity": random.randint(30, 90),
                    "pressure": round(random.uniform(950.0, 1050.0), 1)
                },
                "quality": random.choice(["good", "fair", "poor"])
            })
        elif "connect" in event_type_lower:
            event_data.update({
                "connectionType": random.choice(["wifi", "ethernet", "cellular"]),
                "signalStrength": random.randint(-100, -30),
                "ipAddress": f"192.168.1.{random.randint(1, 254)}"
            })
        elif "disconnect" in event_type_lower:
            event_data.update({
                "reason": random.choice(["timeout", "manual", "error", "maintenance"]),
                "duration": random.randint(1, 3600)  # 1秒到1小时
            })
        # 空调相关事件
        elif "power_change" in event_type_lower:
            event_data.update({
                "oldPower": random.choice([True, False]),
                "newPower": random.choice([True, False]),
                "reason": random.choice(["manual", "timer", "remote", "app"])
            })
        elif "mode_change" in event_type_lower:
            event_data.update({
                "oldMode": random.choice(["cool", "heat", "fan", "auto", "dry"]),
                "newMode": random.choice(["cool", "heat", "fan", "auto", "dry"]),
                "reason": random.choice(["manual", "auto", "schedule"])
            })
        elif "temperature_change" in event_type_lower:
            event_data.update({
                "oldTemperature": random.randint(16, 30),
                "newTemperature": random.randint(16, 30),
                "indoorTemperature": round(random.uniform(18.0, 30.0), 1),
                "reason": random.choice(["manual", "auto", "schedule"])
            })
        elif "fan_speed_change" in event_type_lower:
            event_data.update({
                "oldFanSpeed": random.choice(["low", "medium", "high", "auto"]),
                "newFanSpeed": random.choice(["low", "medium", "high", "auto"]),
                "reason": random.choice(["manual", "auto", "temperature_based"])
            })
        elif "filter_reminder" in event_type_lower:
            event_data.update({
                "filterStatus": random.choice(["need_clean", "need_replace"]),
                "usageHours": random.randint(100, 2000),
                "lastCleanTime": int((get_local_time() - timedelta(days=random.randint(1, 30))).timestamp() * 1000)
            })
        elif "energy_report" in event_type_lower:
            event_data.update({
                "dailyConsumption": round(random.uniform(5.0, 25.0), 2),
                "monthlyConsumption": round(random.uniform(150.0, 750.0), 2),
                "energyEfficiency": random.choice(["A", "B", "C", "D"]),
                "reportPeriod": "daily"
            })
        elif "wifi_status" in event_type_lower:
            event_data.update({
                "signalStrength": random.randint(-80, -30),
                "connectionStatus": random.choice(["connected", "disconnected", "weak"]),
                "ipAddress": f"192.168.1.{random.randint(1, 254)}"
            })
        elif "maintenance_reminder" in event_type_lower:
            event_data.update({
                "maintenanceType": random.choice(["filter_clean", "system_check", "professional_service"]),
                "daysSinceLastMaintenance": random.randint(30, 365),
                "nextMaintenanceDate": int((get_local_time() + timedelta(days=random.randint(1, 30))).timestamp() * 1000)
            })
        
        return event_data
    
    def get_mock_history(self, history_type: str = "all") -> Dict[str, List[Dict[str, Any]]]:
        """获取模拟历史记录"""
        if history_type == "property":
            return {"property": self.mock_history["property"]}
        elif history_type == "service":
            return {"service": self.mock_history["service"]}
        elif history_type == "event":
            return {"event": self.mock_history["event"]}
        else:
            return self.mock_history.copy()
    
    def clear_mock_history(self, history_type: str = "all"):
        """清除模拟历史记录"""
        if history_type == "property" or history_type == "all":
            self.mock_history["property"].clear()
        if history_type == "service" or history_type == "all":
            self.mock_history["service"].clear()
        if history_type == "event" or history_type == "all":
            self.mock_history["event"].clear()
        print(f"✅ [WebSocket] 已清除 {history_type} 模拟历史记录")
    
    def update_mock_device_property(self, device_id: str, property_name: str, value: Any):
        """更新模拟设备属性"""
        if device_id in self.mock_devices:
            if "properties" not in self.mock_devices[device_id]:
                self.mock_devices[device_id]["properties"] = {}
            self.mock_devices[device_id]["properties"][property_name] = value
            self.mock_devices[device_id]["last_update"] = get_local_time()
            print(f"✅ [WebSocket] 模拟设备 {device_id} 属性 {property_name} 已更新为 {value}")
    
    def get_mock_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取模拟设备信息"""
        return self.mock_devices.get(device_id)
    
    async def send_mock_event_notification(self, device_id: str, event_type: str, 
                                         data: Dict[str, Any] = None):
        """发送模拟事件通知给订阅的客户端"""
        if device_id not in self.event_subscriptions:
            return
            
        data = data or {}
        
        # 生成模拟事件数据
        event_data = self._generate_mock_event_data(device_id, event_type, data)
        
        event_id = f"evt_{uuid.uuid4().hex[:8]}"
        event_message = {
            "id": event_id,
            "method": "event.notify",
            "params": {
                "deviceId": device_id,
                "eventType": event_type,
                "data": event_data,
                "occurredAt": int(get_local_time().timestamp() * 1000)
            },
            "timestamp": int(get_local_time().timestamp() * 1000)
        }
        
        # 记录模拟历史
        self.mock_history["event"].append({
            "device_id": device_id,
            "event_type": event_type,
            "data": event_data,
            "timestamp": get_local_time(),
            "event_id": event_id
        })
        
        # 发送给所有订阅该设备的客户端
        for client_id in self.event_subscriptions[device_id]:
            await self.send_message(client_id, event_message)


# 全局WebSocket工具实例
websocket_tool = WebSocketTool()


# 默认方法处理器
async def property_get_handler(client_id: str, request_id: str, params: Dict[str, Any]):
    """处理 property.get 请求"""
    device_id = params.get("deviceId")
    property_names = params.get("propertyNames", [])
    
    print(f"🔍 [WebSocket] 客户端 {client_id} 查询设备 {device_id} 属性: {property_names}")
    
    # 检查是否启用模拟模式
    if websocket_tool.mock_mode:
        # 使用模拟数据
        properties = {}
        device_properties = {}
        
        # 获取设备属性或生成模拟数据
        if device_id in websocket_tool.mock_devices:
            device_properties = websocket_tool.mock_devices[device_id].get("properties", {})
        
        for prop_name in property_names:
            if prop_name in device_properties:
                properties[prop_name] = device_properties[prop_name]
            else:
                # 根据属性名生成模拟数据
                properties[prop_name] = websocket_tool._generate_mock_property_value(prop_name)
        
        # 记录模拟历史
        websocket_tool.mock_history["property"].append({
            "device_id": device_id,
            "property_names": property_names,
            "response": properties,
            "timestamp": get_local_time(),
            "client_id": client_id
        })
    else:
        # 使用原有逻辑
        properties = {}
        for prop_name in property_names:
            if prop_name == "temperature":
                properties[prop_name] = 25.5
            elif prop_name == "humidity":
                properties[prop_name] = 60
            elif prop_name == "status":
                properties[prop_name] = "online"
            else:
                properties[prop_name] = "unknown"
    
    response_params = {
        "deviceId": device_id,
        "properties": properties
    }
    
    await websocket_tool.send_response(client_id, request_id, "property.get", response_params)


async def service_invoke_handler(client_id: str, request_id: str, params: Dict[str, Any]):
    """处理 service.invoke 请求"""
    device_id = params.get("deviceId")
    service_name = params.get("serviceName")
    arguments = params.get("arguments", {})
    
    print(f"🔧 [WebSocket] 客户端 {client_id} 调用设备 {device_id} 服务: {service_name}")
    
    # 检查是否启用模拟模式
    if websocket_tool.mock_mode:
        # 使用模拟服务调用结果
        result = websocket_tool._generate_mock_service_result(device_id, service_name, arguments)
        
        # 记录模拟历史
        websocket_tool.mock_history["service"].append({
            "device_id": device_id,
            "service_name": service_name,
            "arguments": arguments,
            "result": result,
            "timestamp": get_local_time(),
            "client_id": client_id
        })
    else:
        # 使用原有逻辑
        result = {
            "status": "success",
            "message": f"Service {service_name} executed successfully"
        }
        
        if service_name == "reboot":
            delay = arguments.get("delay", 0)
            result["message"] = f"Device will reboot in {delay} seconds"
        elif service_name == "setTemperature":
            temperature = arguments.get("temperature", 20)
            result["message"] = f"Temperature set to {temperature}°C"
    
    response_params = {
        "deviceId": device_id,
        "serviceName": service_name,
        "result": result
    }
    
    await websocket_tool.send_response(client_id, request_id, "service.invoke", response_params)


async def event_subscribe_handler(client_id: str, request_id: str, params: Dict[str, Any]):
    """处理 event.subscribe 请求"""
    device_id = params.get("deviceId")
    event_types = params.get("eventTypes", [])
    
    print(f"📡 [WebSocket] 客户端 {client_id} 订阅设备 {device_id} 事件: {event_types}")
    
    # 订阅设备事件
    websocket_tool.subscribe_to_device_events(client_id, device_id, event_types)
    
    response_params = {
        "deviceId": device_id,
        "eventTypes": event_types,
        "subscribed": True
    }
    
    await websocket_tool.send_response(client_id, request_id, "event.subscribe", response_params)


# 注册默认方法处理器
websocket_tool.register_method_handler("property.get", property_get_handler)
websocket_tool.register_method_handler("service.invoke", service_invoke_handler)
websocket_tool.register_method_handler("event.subscribe", event_subscribe_handler)

# 默认模拟设备配置
DEFAULT_MOCK_DEVICE_CONFIGS = [
    {
        "deviceId": "sensor_001",
        "name": "温度传感器",
        "type": "sensor",
        "status": "online",
        "properties": {
            "temperature": 25.5,
            "humidity": 60,
            "battery": 85
        },
        "services": ["reboot", "calibrate"],
        "events": ["data", "alarm", "status"]
    },
    {
        "deviceId": "switch_001",
        "name": "智能开关",
        "type": "switch",
        "status": "online",
        "properties": {
            "power": True,
            "voltage": 220.5,
            "current": 1.2
        },
        "services": ["turnOn", "turnOff", "reboot"],
        "events": ["status", "alarm"]
    },
    {
        "deviceId": "camera_001",
        "name": "监控摄像头",
        "type": "camera",
        "status": "online",
        "properties": {
            "recording": True,
            "resolution": "1920x1080",
            "nightVision": True
        },
        "services": ["startRecording", "stopRecording", "reboot"],
        "events": ["motion", "alarm", "status"]
    },
    {
        "deviceId": "ac_001",
        "name": "智能空调",
        "type": "air_conditioner",
        "status": "online",
        "properties": {
            "power": True,
            "mode": "cool",  # cool, heat, fan, auto, dry
            "temperature": 26,
            "fanSpeed": "auto",  # low, medium, high, auto
            "swing": False,
            "timer": False,
            "energySaving": True,
            "indoorTemperature": 28.5,
            "outdoorTemperature": 32.0,
            "filterStatus": "good",  # good, need_clean, need_replace
            "wifiSignal": -45,
            "powerConsumption": 1.5
        },
        "services": [
            "turnOn", "turnOff", "setMode", "setTemperature", 
            "setFanSpeed", "setSwing", "setTimer", "setEnergySaving",
            "cleanFilter", "reboot", "reset"
        ],
        "events": [
            "power_change", "mode_change", "temperature_change", 
            "fan_speed_change", "filter_reminder", "energy_report",
            "wifi_status", "error", "maintenance_reminder"
        ]
    }
]

# 初始化默认模拟设备配置
websocket_tool.initialize_mock_devices(DEFAULT_MOCK_DEVICE_CONFIGS)
