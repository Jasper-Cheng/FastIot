import json
from typing import Dict, Any
from app.services.mqtt_client import mqtt_service
from app.services.websocket_service import push_device_message_notification
from app.services.device_message_service import device_message_service
from app.crud.device_message import create_device_message
from app.models.device_message import DeviceMessageCreate
from sqlalchemy.ext.asyncio import AsyncSession

# Helper to extract device_id from topic pattern like: devices/{device_id}/<suffix>
def _extract_device_id(topic: str) -> int:
    try:
        parts = topic.split("/")
        # ["devices", "{id}", ...]
        return int(parts[1])
    except Exception:
        return 0

async def handle_telemetry(topic: str, data: Dict[str, Any], db: AsyncSession | None = None) -> None:
    device_id = _extract_device_id(topic)
    if not device_id:
        return
    
    # 1) 检查是否有告警条件
    if db is not None:
        await device_message_service.check_telemetry_messages(device_id, data, db)
    
    # 2) 广播到应用/Web端
    mqtt_service.publish_json(
        topic=f"apps/broadcast/devices/{device_id}/status",
        payload={"device_id": device_id, "status": data},
        qos=0,
        retain=False,
    )

async def handle_lifecycle(topic: str, data: Dict[str, Any]) -> None:
    device_id = _extract_device_id(topic)
    if not device_id:
        return
    
    is_online = bool(data.get("online", True))
    
    # 广播到应用/Web端
    mqtt_service.publish_json(
        topic=f"apps/broadcast/devices/{device_id}/online",
        payload={"device_id": device_id, "online": is_online},
        qos=0,
        retain=False,
    )

async def handle_ack(topic: str, data: Dict[str, Any]) -> None:
    device_id = _extract_device_id(topic)
    if not device_id:
        return
    
    # 转发确认到应用/Web端
    mqtt_service.publish_json(
        topic=f"apps/broadcast/devices/{device_id}/ack",
        payload={"device_id": device_id, "ack": data},
        qos=0,
        retain=False,
    )

async def handle_device_message(topic: str, data: Dict[str, Any], db: AsyncSession | None = None) -> None:
    """处理设备消息"""
    device_id = _extract_device_id(topic)
    if not device_id:
        return
    
    if db is not None:
        # 使用设备消息服务创建消息
        message_info = await device_message_service.create_manual_message(
            device_id=device_id,
            message_type=data.get("message_type", "unknown"),
            message=data.get("message", "设备消息"),
            db=db
        )
        
        if message_info:
            print(f"✅ [DeviceMessage] 设备 {device_id} 消息已记录并推送: {data.get('message_type', 'unknown')}")
        else:
            print(f"❌ [DeviceMessage] 设备 {device_id} 消息处理失败")
    
    # 转发消息到应用/Web端
    mqtt_service.publish_json(
        topic=f"apps/broadcast/devices/{device_id}/message",
        payload={"device_id": device_id, "message": data},
        qos=0,
        retain=False,
    )

# Synchronous wrappers for mqtt_service.subscribe (which expects sync handler)
def _wrap_async(handler):
    import asyncio
    def _inner(topic: str, payload: Dict[str, Any]):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            asyncio.create_task(handler(topic, payload))
        else:
            loop.run_until_complete(handler(topic, payload))
    return _inner

# Register subscriptions (to be called after MQTT connects)
def register_mqtt_subscriptions() -> None:
    mqtt_service.subscribe("devices/+/telemetry", _wrap_async(handle_telemetry), qos=0)
    mqtt_service.subscribe("devices/+/lifecycle", _wrap_async(handle_lifecycle), qos=0)
    mqtt_service.subscribe("devices/+/ack", _wrap_async(handle_ack), qos=0)
    mqtt_service.subscribe("devices/+/message", _wrap_async(handle_device_message), qos=0)
