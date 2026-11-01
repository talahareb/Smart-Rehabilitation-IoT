import argparse
import time
from collections import deque

from common.config import load_json
from common.mqtt_client import MQTTClient
from common.registry import RegistryClient


class VitalSignsController:
    def __init__(self, config_path: str):
        self.config = load_json(config_path)
        self.registry = RegistryClient(self.config["catalog_url"])
        self.window = deque(
            maxlen=int(self.config.get("moving_average_window", 5)))

        self.previous_avg = None
        self.previous_time = None

        self.fever_threshold_c = float(
            self.config.get("fever_threshold_c", 38.0))
        
        self.rapid_rise_threshold_c_per_min = float(
            self.config.get("rapid_rise_c_per_min", 0.5))
        
        mqtt_conf = self.config["mqtt"]
        self.client = MQTTClient(
            self.config["client_id"], 
            mqtt_conf["broker"], 
            mqtt_conf["port"], 
            self.notify
        )

    def register(self):
        self.registry.register({
            "registerType": "service",
            "id": self.config["client_id"],
            "type": "vital_signs_controller",
            "attribute": {
                "input": self.config["temperature_topic"], 
                "outputs": [
                    self.config["temperature_alert_topic"], 
                    self.config["summary_topic"]
                ]
            },
        })

    def start(self):
        self.register()
        self.load_catalog_settings()
        self.client.start()
        self.client.subscribe(self.config["temperature_topic"])

    def load_catalog_settings(self):
        setting = self.registry.get_setting()
        thresholds = setting.get("thresholds", {})

        self.fever_threshold_c = float(
            thresholds.get("fever_c", self.fever_threshold_c)
        )

        self.rapid_rise_threshold_c_per_min = float(
            thresholds.get(
                "rapid_rise_c_per_min",
                self.rapid_rise_threshold_c_per_min,))

    def notify(self, topic, payload):
        temp = float(payload["temperature_c"])
        # previous = self.window[-1] if self.window else None

        self.window.append(temp)
        avg = round(sum(self.window) / len(self.window), 2)

        threshold = self.fever_threshold_c

        current_time = float(payload.get("timestamp", time.time()))
        rate_of_change = 0.0

        if (self.previous_avg is not None 
            and self.previous_time is not None):

            elapsed_seconds = current_time - self.previous_time

            if elapsed_seconds > 0:
                rate_of_change = ((avg - self.previous_avg) 
                                  / elapsed_seconds * 60.0)

        rate_of_change = round(rate_of_change, 2)

        rapid_temperature_increase = \
        rate_of_change >= self.rapid_rise_threshold_c_per_min

        # Publish temperature summary and trend information.
        self.client.publish(
            self.config["summary_topic"],
            {
                "patientId": payload.get("patientId"),
                "temperature_c": temp,
                "moving_average_c": avg,
                "temperature_rate_c_per_min": rate_of_change,
                "status": (
                    "fever"
                    if avg >= threshold
                    else "normal"
                )
            }, 
        )

        # Fever alert.
        if avg >= threshold:
            self.client.publish(
                self.config["temperature_alert_topic"],
                {
                    "patientId": payload.get("patientId"),
                    "severity": "high",
                    "kind": "temperature",
                    "message": (
                        f"Fever detected: moving average {avg} C"
                    )
                },
            )

        # Rapid temperature increase alert.
        if rapid_temperature_increase:
            self.client.publish(
                self.config["temperature_alert_topic"],
                {
                    "patientId": payload.get("patientId"),
                    "severity": "high",
                    "kind": "temperature",
                    "message": (
                        "Rapid temperature increase: "
                        f"{rate_of_change} C/min"
                    )
                },
            )
            
        # Save current filtered value for the next trend calculation.
        self.previous_avg = avg
        self.previous_time = current_time


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/controllers.json")
    args = parser.parse_args()
    service = VitalSignsController(args.config)
    service.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.client.stop()
