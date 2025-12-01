import asyncio
from asyncio_mqtt import Client, MqttError
from app.core.config import settings


class MQTTService:
    def __init__(self):
        self.host = settings.MQTT_HOST
        self.port = settings.MQTT_PORT
        self.username = settings.MQTT_USERNAME
        self.password = settings.MQTT_PASSWORD

        # 三个固定的 topic
        self.topic_control = "jasper/control"   # 后台 -> 设备
        self.topic_data = "jasper/data"         # 设备 -> 后台
        self.topic_status = "jasper/status"     # 设备 -> 后台

        self.client = None
        self.running = False

    async def connect(self):
        """后台作为客户端，连接到 MQTT Broker"""
        self.client = Client(
            self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            client_id="jasper_backend"
        )

        await self.client.connect()
        print("[MQTT] 后台已连接到 Broker")
        self.running = True

    async def subscribe_topics(self):
        """订阅固定的三个 topic"""
        await self.client.subscribe(self.topic_data)
        await self.client.subscribe(self.topic_status)
        print("[MQTT] 后台已订阅: data / status")

    async def listen(self, on_data, on_status):
        """
        持续监听消息并回调处理
        on_data(sn, payload)
        on_status(sn, payload)
        """
        async with self.client.unfiltered_messages() as messages:
            await self.subscribe_topics()

            async for msg in messages:
                topic = msg.topic
                payload = msg.payload.decode()

                if topic == self.topic_data:
                    data = self.parse_payload(payload)
                    sn = data.get("sn")
                    on_data(sn, data)

                elif topic == self.topic_status:
                    data = self.parse_payload(payload)
                    sn = data.get("sn")
                    on_status(sn, data)

    async def publish_control(self, sn: str, payload: dict):
        """后台 -> 设备，给某个 SN 发布控制指令"""
        message = {**payload, "sn": sn}
        await self.client.publish(self.topic_control, str(message))
        print(f"[MQTT] 已发送控制命令给 {sn} -> {message}")

    @staticmethod
    def parse_payload(payload: str):
        """简单转 dict；你可以改为 JSON"""
        try:
            import json
            return json.loads(payload)
        except:
            return {"raw": payload}
