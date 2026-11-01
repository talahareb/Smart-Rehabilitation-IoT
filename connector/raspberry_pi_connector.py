import argparse
import random
import time # timestamp (s) from 1970-01-01 00:00:00    .time(), .sleep()
from datetime import datetime   # readable time format  .now()

from common.config import load_json
from common.mqtt_client import MQTTClient
from common.registry import RegistryClient


class RaspberryPiConnector:
    """Simulates rehabilitation sensors on one Raspberry Pi."""

    def __init__(self, config_path: str):
        self.config = load_json(config_path) # JSON str -> Dict
        self.registry = RegistryClient(self.config["catalog_url"])
        self.topics = self.config["topics"]
        mqtt_conf = self.config["mqtt"]
        self.client = MQTTClient(
            self.config["client_id"],
            mqtt_conf["broker"],
            int(mqtt_conf["port"]),
            self.notify,    
            # specified callback function to handle incoming messages
        )
        self.sequence = 0

    def notify(self, topic, payload):
        # Reserved for future inbound commands such as connector on/off.
        print(f"[rpi] received {topic}: {payload}")

    def register_virtual_sensors(self):
        setting = None
        for sensor_type, topic in self.topics.items():  # key value pairs
            payload = {
                "registerType": "device",
                "id": f"rpi_{sensor_type}",
                "type": sensor_type,
                "topic": topic,
                "attribute": {
                    "physicalDevice": "raspberry_pi_1",
                    "patientId": self.config["patient_id"],
                    "unit": self.config["units"].get(sensor_type, ""),  # dict
                },
            }
            setting = self.registry.register(payload)
            print(f"[rpi] registered {payload['id']} on {topic}")
        return setting

    def start(self):
        self.register_virtual_sensors()
        self.client.start()
        interval = float(self.config.get("publish_interval_sec", 5)) # default
        try:
            while True:
                self.sequence += 1
                self.publish_once()
                time.sleep(interval)
        finally:
            self.client.stop()

    def publish_once(self): # the same time interval for all topics
        now = time.time()
        hour = datetime.now().hour
        temp = round(random.gauss(36.7, 0.35), 2)   # normal body temperature with some variation, 2 floating points
        if random.random() < self.config.get("fever_probability", 0.05):    # [0, 1)
            temp = round(random.uniform(38.0, 39.1), 2) # fever range
        activity = max(0, int(random.gauss(35 if 8 <= hour <= 21 else 4, 18)))
        night_motion = max(0, int(random.gauss(5 if hour < 7 or hour >= 22 else 1, 3)))
        pillbox_open = random.random() < self.config.get("pillbox_open_probability", 0.05)

        base = {
            "patientId": self.config["patient_id"], 
            "sequence": self.sequence, 
            "timestamp": now}
        self.client.publish(self.topics["temperature"], {**base, "temperature_c": temp})
        self.client.publish(self.topics["activity"], {**base, "motion_count": activity})
        self.client.publish(self.topics["night_activity"], {**base, "motion_count": night_motion})
        if pillbox_open:
            self.client.publish(self.topics["pillbox"], {**base, "event": "open"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/raspberry_pi_connector.json")
    args = parser.parse_args()
    RaspberryPiConnector(args.config).start()
