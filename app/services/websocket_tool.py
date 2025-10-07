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
        # 音响相关属性
        elif property_name_lower == "power":
            return random.choice([True, False])
        elif property_name_lower == "volume":
            return random.randint(0, 100)
        elif property_name_lower == "mute":
            return random.choice([True, False])
        elif property_name_lower == "source":
            return random.choice(["bluetooth", "wifi", "aux", "usb"])
        elif property_name_lower == "playing":
            return random.choice([True, False])
        elif property_name_lower == "track":
            return random.choice(["未知歌曲", "随机歌曲", "测试音乐", "背景音乐"])
        elif property_name_lower == "artist":
            return random.choice(["未知艺术家", "测试艺术家", "随机歌手", "背景音乐"])
        elif property_name_lower == "album":
            return random.choice(["未知专辑", "测试专辑", "精选集", "背景音乐"])
        elif property_name_lower == "duration":
            return random.randint(60, 300)  # 1-5分钟
        elif property_name_lower == "position":
            return random.randint(0, 180)   # 0-3分钟
        elif property_name_lower == "repeat":
            return random.choice(["none", "one", "all"])
        elif property_name_lower == "shuffle":
            return random.choice([True, False])
        elif property_name_lower == "equalizer":
            return random.choice(["normal", "pop", "rock", "jazz", "classical"])
        elif property_name_lower == "bass":
            return random.randint(-10, 10)
        elif property_name_lower == "treble":
            return random.randint(-10, 10)
        elif property_name_lower == "battery":
            return random.randint(0, 100)
        elif property_name_lower == "wifisignal":
            return random.randint(-80, -30)
        elif property_name_lower == "bluetoothconnected":
            return random.choice([True, False])
        elif property_name_lower == "bluetoothdevice":
            return random.choice(["iPhone 15", "Samsung Galaxy", "iPad", "MacBook", "Android Phone"])
        elif property_name_lower == "firmwareversion":
            return f"{random.randint(1, 3)}.{random.randint(0, 9)}.{random.randint(0, 9)}"
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
        # 音响相关服务
        elif "turnon" in service_name_lower or "turn_on" in service_name_lower:
            return {
                "status": "success",
                "message": "音响已开启",
                "powerOnTime": int(get_local_time().timestamp() * 1000)
            }
        elif "turnoff" in service_name_lower or "turn_off" in service_name_lower:
            return {
                "status": "success",
                "message": "音响已关闭",
                "powerOffTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setvolume" in service_name_lower or "set_volume" in service_name_lower:
            volume = arguments.get("volume", 50)
            return {
                "status": "success",
                "message": f"音量已设置为 {volume}%",
                "newVolume": volume,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setmute" in service_name_lower or "set_mute" in service_name_lower:
            mute = arguments.get("mute", False)
            return {
                "status": "success",
                "message": f"音响已{'静音' if mute else '取消静音'}",
                "muteEnabled": mute,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setsource" in service_name_lower or "set_source" in service_name_lower:
            source = arguments.get("source", "bluetooth")
            return {
                "status": "success",
                "message": f"音源已切换到 {source}",
                "newSource": source,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "play" in service_name_lower:
            return {
                "status": "success",
                "message": "开始播放",
                "playTime": int(get_local_time().timestamp() * 1000)
            }
        elif "pause" in service_name_lower:
            return {
                "status": "success",
                "message": "暂停播放",
                "pauseTime": int(get_local_time().timestamp() * 1000)
            }
        elif "stop" in service_name_lower:
            return {
                "status": "success",
                "message": "停止播放",
                "stopTime": int(get_local_time().timestamp() * 1000)
            }
        elif "nexttrack" in service_name_lower or "next_track" in service_name_lower:
            return {
                "status": "success",
                "message": "切换到下一首",
                "trackChangeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "previoustrack" in service_name_lower or "previous_track" in service_name_lower:
            return {
                "status": "success",
                "message": "切换到上一首",
                "trackChangeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setrepeat" in service_name_lower or "set_repeat" in service_name_lower:
            repeat = arguments.get("repeat", "none")
            return {
                "status": "success",
                "message": f"重复模式已设置为 {repeat}",
                "newRepeat": repeat,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setshuffle" in service_name_lower or "set_shuffle" in service_name_lower:
            shuffle = arguments.get("shuffle", False)
            return {
                "status": "success",
                "message": f"随机播放已{'开启' if shuffle else '关闭'}",
                "shuffleEnabled": shuffle,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setequalizer" in service_name_lower or "set_equalizer" in service_name_lower:
            equalizer = arguments.get("equalizer", "normal")
            return {
                "status": "success",
                "message": f"均衡器已设置为 {equalizer}",
                "newEqualizer": equalizer,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "setbass" in service_name_lower or "set_bass" in service_name_lower:
            bass = arguments.get("bass", 0)
            return {
                "status": "success",
                "message": f"低音已设置为 {bass}",
                "newBass": bass,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "settreble" in service_name_lower or "set_treble" in service_name_lower:
            treble = arguments.get("treble", 0)
            return {
                "status": "success",
                "message": f"高音已设置为 {treble}",
                "newTreble": treble,
                "changeTime": int(get_local_time().timestamp() * 1000)
            }
        elif "connectbluetooth" in service_name_lower or "connect_bluetooth" in service_name_lower:
            device = arguments.get("device", "未知设备")
            return {
                "status": "success",
                "message": f"已连接到蓝牙设备 {device}",
                "connectedDevice": device,
                "connectTime": int(get_local_time().timestamp() * 1000)
            }
        elif "disconnectbluetooth" in service_name_lower or "disconnect_bluetooth" in service_name_lower:
            return {
                "status": "success",
                "message": "已断开蓝牙连接",
                "disconnectTime": int(get_local_time().timestamp() * 1000)
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
        # 音响相关事件
        elif "power_change" in event_type_lower:
            event_data.update({
                "oldPower": random.choice([True, False]),
                "newPower": random.choice([True, False]),
                "reason": random.choice(["manual", "timer", "remote", "app"])
            })
        elif "volume_change" in event_type_lower:
            event_data.update({
                "oldVolume": random.randint(0, 100),
                "newVolume": random.randint(0, 100),
                "reason": random.choice(["manual", "auto", "remote"])
            })
        elif "mute_change" in event_type_lower:
            event_data.update({
                "oldMute": random.choice([True, False]),
                "newMute": random.choice([True, False]),
                "reason": random.choice(["manual", "auto", "remote"])
            })
        elif "source_change" in event_type_lower:
            event_data.update({
                "oldSource": random.choice(["bluetooth", "wifi", "aux", "usb"]),
                "newSource": random.choice(["bluetooth", "wifi", "aux", "usb"]),
                "reason": random.choice(["manual", "auto", "connection"])
            })
        elif "playback_start" in event_type_lower:
            event_data.update({
                "track": random.choice(["未知歌曲", "随机歌曲", "测试音乐"]),
                "artist": random.choice(["未知艺术家", "测试艺术家", "随机歌手"]),
                "album": random.choice(["未知专辑", "测试专辑", "精选集"]),
                "duration": random.randint(60, 300),
                "startTime": int(get_local_time().timestamp() * 1000)
            })
        elif "playback_pause" in event_type_lower:
            event_data.update({
                "position": random.randint(0, 180),
                "pauseTime": int(get_local_time().timestamp() * 1000)
            })
        elif "playback_stop" in event_type_lower:
            event_data.update({
                "stopTime": int(get_local_time().timestamp() * 1000),
                "reason": random.choice(["manual", "end_of_track", "error"])
            })
        elif "track_change" in event_type_lower:
            event_data.update({
                "oldTrack": random.choice(["上一首歌曲", "随机歌曲", "测试音乐"]),
                "newTrack": random.choice(["下一首歌曲", "随机歌曲", "测试音乐"]),
                "changeTime": int(get_local_time().timestamp() * 1000),
                "reason": random.choice(["manual", "auto", "shuffle"])
            })
        elif "bluetooth_connected" in event_type_lower:
            event_data.update({
                "deviceName": random.choice(["iPhone 15", "Samsung Galaxy", "iPad", "MacBook"]),
                "deviceAddress": f"{random.randint(10, 99)}:{random.randint(10, 99)}:{random.randint(10, 99)}:{random.randint(10, 99)}:{random.randint(10, 99)}:{random.randint(10, 99)}",
                "connectTime": int(get_local_time().timestamp() * 1000)
            })
        elif "bluetooth_disconnected" in event_type_lower:
            event_data.update({
                "deviceName": random.choice(["iPhone 15", "Samsung Galaxy", "iPad", "MacBook"]),
                "disconnectTime": int(get_local_time().timestamp() * 1000),
                "reason": random.choice(["manual", "out_of_range", "low_battery"])
            })
        elif "battery_low" in event_type_lower:
            event_data.update({
                "batteryLevel": random.randint(5, 20),
                "warningTime": int(get_local_time().timestamp() * 1000),
                "estimatedTimeLeft": random.randint(30, 120)  # 分钟
            })
        elif "wifi_status" in event_type_lower:
            event_data.update({
                "signalStrength": random.randint(-80, -30),
                "connectionStatus": random.choice(["connected", "disconnected", "weak"]),
                "ipAddress": f"192.168.1.{random.randint(1, 254)}"
            })
        elif "firmware_update" in event_type_lower:
            event_data.update({
                "oldVersion": f"{random.randint(1, 3)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
                "newVersion": f"{random.randint(1, 3)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
                "updateTime": int(get_local_time().timestamp() * 1000),
                "updateSize": random.randint(10, 100)  # MB
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
    
    # print(f"📡 [WebSocket] 客户端 {client_id} 订阅设备 {device_id} 事件: {event_types}")
    
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
        "deviceId": "speaker_001",
        "name": "智能音响",
        "type": "speaker",
        "status": "online",
        "properties": {
            "power": True,
            "volume": 50,                    # 音量 0-100
            "mute": False,                   # 静音状态
            "source": "bluetooth",           # 音源：bluetooth, wifi, aux, usb
            "playing": True,                 # 播放状态
            "track": "未知歌曲",              # 当前曲目
            "artist": "未知艺术家",           # 艺术家
            "album": "未知专辑",             # 专辑
            "duration": 180,                 # 歌曲时长（秒）
            "position": 45,                  # 播放位置（秒）
            "repeat": "none",                # 重复模式：none, one, all
            "shuffle": False,                # 随机播放
            "equalizer": "normal",           # 均衡器：normal, pop, rock, jazz, classical
            "bass": 0,                       # 低音 -10 到 10
            "treble": 0,                     # 高音 -10 到 10
            "battery": 85,                   # 电池电量（如果是便携式）
            "wifiSignal": -35,               # WiFi信号强度
            "bluetoothConnected": True,      # 蓝牙连接状态
            "bluetoothDevice": "iPhone 15",  # 连接的蓝牙设备
            "firmwareVersion": "2.1.3"      # 固件版本
        },
        "services": [
            "turnOn", "turnOff", "setVolume", "setMute", "setSource",
            "play", "pause", "stop", "nextTrack", "previousTrack",
            "setRepeat", "setShuffle", "setEqualizer", "setBass", "setTreble",
            "connectBluetooth", "disconnectBluetooth", "reboot", "reset"
        ],
        "events": [
            "power_change", "volume_change", "mute_change", "source_change",
            "playback_start", "playback_pause", "playback_stop", "track_change",
            "bluetooth_connected", "bluetooth_disconnected", "battery_low",
            "wifi_status", "error", "firmware_update"
        ]
    }
]

# 初始化默认模拟设备配置
websocket_tool.initialize_mock_devices(DEFAULT_MOCK_DEVICE_CONFIGS)
