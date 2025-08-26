import json
import os
import threading
import time
from typing import Callable, Dict, Any

import paho.mqtt.client as mqtt

# Topic conventions
# - devices/{device_id}/status   -> device state published by server (or device)
# - devices/{device_id}/online   -> boolean online status published by server
# - devices/{device_id}/control  -> control command published by server for device to consume


class MqttService:
    def __init__(self) -> None:
        self._client: mqtt.Client | None = None
        self._connected: bool = False
        self._lock = threading.Lock()
        # Broker config (env with sensible defaults)
        self._host = os.getenv("MQTT_HOST", "127.0.0.1")
        self._port = int(os.getenv("MQTT_PORT", "1883"))
        self._username = os.getenv("MQTT_USER")
        self._password = os.getenv("MQTT_PASSWORD")
        self._client_id = os.getenv("MQTT_CLIENT_ID", f"fastiot-server-{int(time.time())}")
        self._keepalive = int(os.getenv("MQTT_KEEPALIVE", "60"))

    def connect(self) -> None:
        with self._lock:
            if self._connected:
                return
            client = mqtt.Client(client_id=self._client_id, clean_session=True)
            if self._username:
                client.username_pw_set(self._username, self._password or None)

            def on_connect(cli: mqtt.Client, _userdata, _flags, rc):
                self._connected = rc == 0
            client.on_connect = on_connect

            def on_disconnect(cli: mqtt.Client, _userdata, rc):
                self._connected = False
            client.on_disconnect = on_disconnect

            client.connect(self._host, self._port, keepalive=self._keepalive)
            client.loop_start()
            # wait briefly for connection
            for _ in range(20):
                if self._connected:
                    break
                time.sleep(0.05)
            self._client = client

    def disconnect(self) -> None:
        with self._lock:
            if not self._client:
                return
            try:
                self._client.loop_stop()
                self._client.disconnect()
            finally:
                self._client = None
                self._connected = False

    def ensure_connected(self) -> None:
        if not self._connected or not self._client:
            self.connect()

    def publish_json(self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False) -> bool:
        self.ensure_connected()
        if not self._client:
            return False
        result = self._client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=qos, retain=retain)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    def subscribe(self, topic: str, handler: Callable[[str, Dict[str, Any]], None], qos: int = 0) -> None:
        """Subscribe to a topic and invoke handler(topic, json_payload)."""
        self.ensure_connected()
        if not self._client:
            return

        def on_message(_cli, _userdata, msg: mqtt.MQTTMessage):
            try:
                data = json.loads(msg.payload.decode("utf-8")) if msg.payload else {}
            except Exception:
                data = {"raw": msg.payload.decode("utf-8", errors="ignore")}
            handler(msg.topic, data)

        self._client.on_message = on_message
        self._client.subscribe(topic, qos=qos)


# Global instance
mqtt_service = MqttService()
