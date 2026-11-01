import json
import threading
import time
from typing import Callable, Dict, Iterable, Optional

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover - handled at runtime on Raspberry Pi.
    mqtt = None


MessageHandler = Callable[[str, Dict], None]
# a callable function that receives two arguments (topic, payload)
# and returns None

class MQTTClient:
    """Small MQTT wrapper following the style of the previous IoT project."""

    def __init__(self, client_id: str, broker: str, port: int, on_message: MessageHandler): 
        # receive an external function with type MessageHandler
        if mqtt is None:
            raise RuntimeError("paho-mqtt is not installed. Run: pip install -r requirements.txt")
        self.client_id = client_id
        self.broker = broker
        self.port = int(port)
        self.on_message = on_message
        self._subscriptions = set()
        self._lock = threading.Lock()   
        # avoid to reaching the topics list at the same time

        self._client = mqtt.Client(client_id=client_id, clean_session=True) # start from a clean session
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        print(f"[mqtt] {self.client_id} connected to {self.broker}:{self.port} rc={rc}")
        with self._lock:
            topics = list(self._subscriptions)
        for topic in topics:
            client.subscribe(topic, qos=1)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))   # str -> dict
        except Exception:
            payload = {"raw": msg.payload.decode("utf-8", errors="replace")}    # invalid JSON expression
        self.on_message(msg.topic, payload)

    def start(self):
        self._client.connect(self.broker, self.port, keepalive=60)
        self._client.loop_start()

    def stop(self):
        self._client.loop_stop()
        self._client.disconnect()

    def subscribe(self, topic: str):
        with self._lock:
            self._subscriptions.add(topic)
        self._client.subscribe(topic, qos=1)
        print(f"[mqtt] {self.client_id} subscribed {topic}")

    def subscribe_many(self, topics: Iterable[str]):
        for topic in topics:
            self.subscribe(topic)

    def publish(self, topic: str, payload: Dict, retain: bool = False):
        payload = dict(payload) # avoid affecting the original payload
        payload.setdefault("timestamp", time.time())    
        # add a timestamp key if there is no timestamp else keep the default

        self._client.publish(topic, json.dumps(payload), qos=1, retain=retain)  
        # retain: the broker will store the last retained message and send it to any future subscribers of that topic any time.
        print(f"[mqtt] {self.client_id} -> {topic}: {payload}") # log message 
