"""
WebSocket工具类
支持收发信息、心跳机制、连接管理
支持标准请求-响应模式：property.get, service.invoke, event.subscribe
"""
import json
import asyncio
import uuid
from datetime import datetime
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
        
    async def connect(self, websocket: WebSocket, client_id: str, metadata: Optional[Dict[str, Any]] = None):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = {
            "connected_at": get_local_time(),
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
            print(f"✅ [WebSocket] 消息已发送给客户端 {client_id}: {message.get('type', 'unknown')}")
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


# 全局WebSocket工具实例
websocket_tool = WebSocketTool()


# 默认方法处理器
async def property_get_handler(client_id: str, request_id: str, params: Dict[str, Any]):
    """处理 property.get 请求"""
    device_id = params.get("deviceId")
    property_names = params.get("propertyNames", [])
    
    print(f"🔍 [WebSocket] 客户端 {client_id} 查询设备 {device_id} 属性: {property_names}")
    
    # 模拟设备属性数据
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
    
    # 模拟服务调用
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
