import json
from typing import Dict, Any
from app.services.mqtt_client import mqtt_service
from app.services.redis_service import redis_service
from app.crud.device import update_device_last_active
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
    # 1) cache latest status
    await redis_service.set_device_status(device_id, data)
    # 2) optional: update last active in DB
    if db is not None:
        await update_device_last_active(db, device_id)
    # 3) rebroadcast to app/web side
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
    await redis_service.set_device_online(device_id, is_online)
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
    # Forward ack to app/web
    mqtt_service.publish_json(
        topic=f"apps/broadcast/devices/{device_id}/ack",
        payload={"device_id": device_id, "ack": data},
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
