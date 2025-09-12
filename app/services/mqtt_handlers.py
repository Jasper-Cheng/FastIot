import json
from typing import Dict, Any
from app.services.mqtt_client import mqtt_service
from app.services.redis_service import redis_service
from app.services.websocket_service import push_alert_notification
from app.services.alert_service import alert_service
from app.crud.alert import create_alert
from app.models.alert import AlertCreate
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
        await alert_service.check_telemetry_alerts(device_id, data, db)
    
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
    
    # 更新设备信息缓存中的状态
    cached_info = await redis_service.get_device_info(device_id)
    if cached_info:
        cached_info["status"] = "online" if is_online else "offline"
        await redis_service.set_device_info(device_id, cached_info)
    
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

async def handle_alert(topic: str, data: Dict[str, Any], db: AsyncSession | None = None) -> None:
    """处理设备告警消息"""
    device_id = _extract_device_id(topic)
    if not device_id:
        return
    
    if db is not None:
        # 使用alert服务创建告警
        alert_info = await alert_service.create_manual_alert(
            device_id=device_id,
            alert_type=data.get("alert_type", "unknown"),
            message=data.get("message", "设备告警"),
            db=db
        )
        
        if alert_info:
            print(f"✅ [Alert] 设备 {device_id} 告警已记录并推送: {data.get('alert_type', 'unknown')}")
        else:
            print(f"❌ [Alert] 设备 {device_id} 告警处理失败")
    
    # 转发告警到应用/Web端
    mqtt_service.publish_json(
        topic=f"apps/broadcast/devices/{device_id}/alert",
        payload={"device_id": device_id, "alert": data},
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
    mqtt_service.subscribe("devices/+/alert", _wrap_async(handle_alert), qos=0)
