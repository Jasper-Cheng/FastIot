"""
WebSocket工具类
支持收发信息、心跳机制、连接管理
支持标准请求-响应模式：property.get, service.invoke, event.subscribe
支持后端直接发送：family.message, system.message
"""
import json
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Set, Callable, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from app.utils.time_utils import get_local_time


class WebSocketTool:
    """WebSocket工具类"""
    
    def __init__(self):
        # 活跃连接管理
        self.active_connections: Dict[str, WebSocket] = {}  # client_id -> WebSocket
        # 连接元数据
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}  # client_id -> metadata dict
        # 方法处理器
        self.method_handlers: Dict[str, Callable] = {}  # method_name -> handler_function
        # 事件订阅管理
        self.event_subscriptions: Dict[str, Set[str]] = {}  # device_sn -> set of client_ids
        # 待处理请求
        self.pending_requests: Dict[str, Dict[str, Any]] = {}  # request_id -> request_info
        # 心跳超时时间（秒）
        self.heartbeat_timeout = 60  # 默认60秒超时
        
    async def connect(self, websocket: WebSocket, client_id: str, metadata: Optional[Dict[str, Any]] = None):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = {
            "connected_at": get_local_time(),
            "last_heartbeat": get_local_time(),
            "metadata": metadata or {}
        }
        
        print(f"✅ [WebSocket] 客户端 {client_id} 已连接: metadata = {metadata}")
        
    async def disconnect(self, client_id: str):
        """断开WebSocket连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
            
        # 清理事件订阅
        for device_sn in list(self.event_subscriptions.keys()):
            self.event_subscriptions[device_sn].discard(client_id)
            if not self.event_subscriptions[device_sn]:
                del self.event_subscriptions[device_sn]
            
        print(f"❌ [WebSocket] 客户端 {client_id} 已断开")
        
    async def send_message(self, client_id: str, message: Dict[str, Any]) -> bool:
        """发送消息给指定客户端"""
        if client_id not in self.active_connections:
            print(f"❌ [WebSocket] 客户端 {client_id} 未连接")
            return False
            
        try:
            websocket = self.active_connections[client_id]
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
            print(f"✅ [WebSocket] 消息已发送给客户端 {client_id}，{message.get('method', '')} {message.get('params', {}).get('type', '')}")
            return True
        except Exception as e:
            print(f"❌ [WebSocket] 发送消息给客户端 {client_id} 失败: {e}")
            await self.disconnect(client_id)
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
            await self.disconnect(client_id)
            
        
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
        
    async def send_event_notification(self, device_sn: str, event_type: str, data: Dict[str, Any]):
        """发送事件通知给订阅的客户端"""
        if device_sn not in self.event_subscriptions:
            return
            
        event_id = f"evt_{uuid.uuid4().hex[:8]}"
        event_message = {
            "id": event_id,
            "method": "event.notify",
            "params": {
                "deviceSn": device_sn,
                "eventType": event_type,
                "data": data,
                "occurredAt": int(get_local_time().timestamp() * 1000)
            },
            "timestamp": int(get_local_time().timestamp() * 1000)
        }
        
        # 发送给所有订阅该设备的客户端
        for client_id in self.event_subscriptions[device_sn]:
            await self.send_message(client_id, event_message)
            
    def subscribe_to_device_events(self, client_id: str, device_sn: str):
        """订阅设备事件"""
        if device_sn not in self.event_subscriptions:
            self.event_subscriptions[device_sn] = set()
        self.event_subscriptions[device_sn].add(client_id)
        print(f"✅ [WebSocket] 客户端 {client_id} 订阅设备 {device_sn} 事件")
        
    def unsubscribe_from_device_events(self, client_id: str, device_sn: str):
        """取消订阅设备事件"""
        if device_sn in self.event_subscriptions:
            self.event_subscriptions[device_sn].discard(client_id)
            if not self.event_subscriptions[device_sn]:
                del self.event_subscriptions[device_sn]
        print(f"❌ [WebSocket] 客户端 {client_id} 取消订阅设备 {device_sn} 事件")
        
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
            
                
    def is_client_connected(self, client_id: str) -> bool:
        """检查client_id是否已连接
        
        Args:
            client_id: 客户端ID
            
        Returns:
            bool: 如果client_id已存在连接，返回True；否则返回False
        """
        return client_id in self.active_connections
    
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
                await self.disconnect(client_id)
                
    def set_heartbeat_timeout(self, timeout_seconds: int):
        """设置心跳超时时间"""
        self.heartbeat_timeout = timeout_seconds
        print(f"✅ [WebSocket] 心跳超时设置为 {timeout_seconds} 秒")
    
    async def send_family_message(
        self,
        client_id: str,
        message_type: str,
        data: Dict[str, Any]
    ):
        """
        发送family消息给指定发送者的family成员
        
        Args:
            client_id: 发送者客户端ID
            message_type: 消息类型，例如：delete.member
            data: 消息数据
        """
        
        # 获取发送者的family信息
        sender_metadata = self.get_connection_info(client_id)
        if not sender_metadata or "metadata" not in sender_metadata or "family_clients" not in sender_metadata["metadata"]:
            print(f"❌ [WebSocket] 无法获取客户端 {client_id} 的family信息")
            return
        
        family_clients = sender_metadata["metadata"]["family_clients"]
        
        # 生成消息ID和时间戳
        message_id = f"fam_{uuid.uuid4().hex[:8]}"
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # 构建family消息
        family_message = {
            "id": message_id,
            "method": "family.message",
            "params": {
                "type": message_type,
                "data": data
            },
            "timestamp": timestamp
        }
        
        # 发送给family中的所有客户端
        print(f"👨‍👩‍👧‍👦 [WebSocket] 客户端 {client_id} 发送消息给客户端 {family_clients}，消息数据: {family_message}")
        for family_client_id in family_clients:
            if family_client_id in self.active_connections:
                try:
                    await self.send_message(family_client_id, family_message)
                except Exception as e:
                    print(f"❌ [WebSocket] 发送family消息给 {family_client_id} 失败: {e}")
    
    async def send_system_message(
        self,
        message_type: str,
        data: Dict[str, Any]
    ):
        """
        发送系统消息给所有连接的客户端
        
        Args:
            message_type: 消息类型
            data: 消息数据
        """
        print(f"🔔 [WebSocket] 发送系统消息: {message_type}")
        
        # 生成时间戳和消息ID
        current_timestamp = int(datetime.now().timestamp() * 1000)
        message_id = f"sys_{uuid.uuid4().hex[:8]}"
        
        # 确保data中包含timestamp
        if "timestamp" not in data:
            data["timestamp"] = current_timestamp
        
        # 构建系统消息
        system_message = {
            "id": message_id,
            "method": "system.message",
            "params": {
                "type": message_type,
                "data": data
            },
            "timestamp": current_timestamp
        }
        
        # 发送给所有连接的客户端
        for target_client_id in self.active_connections:
            try:
                await self.send_message(target_client_id, system_message)
                print(f"📤 [WebSocket] 系统消息已发送给 {target_client_id}")
            except Exception as e:
                print(f"❌ [WebSocket] 发送系统消息给 {target_client_id} 失败: {e}")


# 全局WebSocket工具实例
websocket_tool = WebSocketTool()


# 默认方法处理器
async def property_get_handler(client_id: str, request_id: str, params: Dict[str, Any]):
    """处理 property.get 请求"""
    device_sn = params.get("deviceSn")
    property_names = params.get("propertyNames", [])
    
    print(f"🔍 [WebSocket] 客户端 {client_id} 查询设备 {device_sn} 属性: {property_names}")
    
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
        "deviceSn": device_sn,
        "properties": properties
    }
    
    await websocket_tool.send_response(client_id, request_id, "property.get", response_params)


async def service_invoke_handler(client_id: str, request_id: str, params: Dict[str, Any]):
    """处理 service.invoke 请求"""
    device_sn = params.get("deviceSn")
    service_name = params.get("serviceName")
    arguments = params.get("arguments", {})
    
    print(f"🔧 [WebSocket] 客户端 {client_id} 调用设备 {device_sn} 服务: {service_name}")
    
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
        "deviceSn": device_sn,
        "serviceName": service_name,
        "result": result
    }
    
    await websocket_tool.send_response(client_id, request_id, "service.invoke", response_params)


async def event_subscribe_handler(client_id: str, request_id: str, params: Dict[str, Any]):
    """处理 event.subscribe 请求"""
    device_sn = params.get("deviceSn")
    
    # 订阅设备事件
    websocket_tool.subscribe_to_device_events(client_id, device_sn)
    
    response_params = {
        "deviceSn": device_sn,
        "subscribed": True
    }
    
    await websocket_tool.send_response(client_id, request_id, "event.subscribe", response_params)


async def event_unsubscribe_handler(client_id: str, request_id: str, params: Dict[str, Any]):
    """处理 event.unsubscribe 请求"""
    device_sn = params.get("deviceSn")
    
    # 取消订阅设备事件
    websocket_tool.unsubscribe_from_device_events(client_id, device_sn)
    
    response_params = {
        "deviceSn": device_sn,
        "unsubscribed": True
    }
    
    await websocket_tool.send_response(client_id, request_id, "event.unsubscribe", response_params)


# 注册默认方法处理器
websocket_tool.register_method_handler("property.get", property_get_handler)
websocket_tool.register_method_handler("service.invoke", service_invoke_handler)
websocket_tool.register_method_handler("event.subscribe", event_subscribe_handler)
websocket_tool.register_method_handler("event.unsubscribe", event_unsubscribe_handler)
