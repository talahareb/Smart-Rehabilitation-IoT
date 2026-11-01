import argparse
import json
import time
from collections import deque
import urllib.request
from urllib.parse import urlencode

from common.config import load_json
from common.mqtt_client import MQTTClient
from common.registry import RegistryClient

# connector -> perodically publish simulated sensor data
# controller -> receive sensor data, publish abnormal alerts and summaries

class ActivityController:
    def __init__(self, config_path: str):
        self.config = load_json(config_path)
        self.registry = RegistryClient(self.config["catalog_url"])  # 
        self.window = deque()   # double-ended queue
        self.inactive_since = None
        self.target_activity_level = None

        # adaptive activity level based on patient profile, e.g., elderly, average, athlete
        self.patient_profile = "Average"

        self.adaptive_motion_threshold = int(self.config.get("inactivity_motion_threshold", 20))
        self.adaptive_alert_after_sec = int(self.config.get("inactivity_alert_after_sec", 120))

        self.last_profile_update_time = 0
        self.update_interval_sec = 3600

        mqtt_conf = self.config["mqtt"]
        self.client = MQTTClient(
            "activity_controller", 
            mqtt_conf["broker"], 
            mqtt_conf["port"], 
            self.notify)

    def register(self):
        self.registry.register({
            "registerType": "service",
            "id": "activity_controller",
            "type": "activity_controller",
            "attribute": {
                "input": self.config["activity_topic"], 
                "outputs": [
                    self.config["activity_alert_topic"], 
                    self.config["activity_summary_topic"]
                ]
            }
        })

    def _kmeans_1d(self, data, k=3, max_iters=10):  # classify data into k clusters
        """Simple 1D K-means clustering for historical activity data."""
        if not data or len(set(data)) < k:  # with unique values and maybe different order
            return None

        unique_data = sorted(set(data))
        centroids = [   # different clusters with different centroids
            unique_data[i * len(unique_data) // k]
            for i in range(k)
        ]

        for _ in range(max_iters):
            clusters = [[] for _ in range(k)]

            for point in data:
                distances = [abs(point - c) for c in centroids]
                cluster_idx = distances.index(min(distances))
                clusters[cluster_idx].append(point)

            new_centroids = []

            for cluster in clusters:
                if cluster:
                    new_centroids.append(
                        sum(cluster) / len(cluster)
                    )
                else:
                    new_centroids.append(0)

            if new_centroids == centroids:
                break

            centroids = new_centroids

        return sorted(centroids)

    def _load_catalog_activity_settings(self):
        """Retrieve activity configuration from System Catalog."""
        setting = self.registry.get_setting()

        self.target_activity_level = setting.get(   # get the target activity level
            "target_activity_level",
            self.target_activity_level,
        )   # if do not exist, use the default value
        # the default value will not write into the catalog, 
        # but the user can change it in the catalog

        thresholds = setting.get("thresholds", {})

        self.adaptive_motion_threshold = int(
            thresholds.get(
                "inactivity_motion_base",
                thresholds.get(
                    "inactivity_motion_threshold",
                    self.adaptive_motion_threshold,
                )
            )
        )

    def _fetch_historical_activity(self):   # motion total
        """Retrieve historical activity summaries through ThingSpeak Adapter."""
        services = self.registry.get_services("thingspeak_adapter")
        service_list = services.get("data", [])

        if not service_list:
            return []

        adapter_url = service_list[0].get("attribute", {}) \
            .get("rest", "").rstrip("/")

        if not adapter_url:
            return []

        query = urlencode({
            "topic": self.config["activity_summary_topic"],
            "limit": 200
        })

        url = f"{adapter_url}/series?{query}"

        with urllib.request.urlopen(url, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))

        historical_data = []

        for row in result.get("data", []):
            payload = row.get("payload", {})
            motion_total = payload.get("motion_total")

            if motion_total is not None:
                historical_data.append(float(motion_total))

        return historical_data

    def update_patient_profile(self, patient_id="default_patient"):
        """
        Retrieve configuration and historical activity,
        apply K-means, and adapt inactivity behaviour.
        """
        try:
            # REST request to System Catalog.
            self._load_catalog_activity_settings()

            # REST request to ThingSpeak Adapter.
            historical_data = self._fetch_historical_activity()

            centroids = self._kmeans_1d(historical_data, k=3, )

            if centroids:
                # Use recent real historical activity rather than
                # a hard-coded prototype value.
                recent_values = historical_data[-10:]
                recent_avg = (
                    sum(recent_values) / len(recent_values)
                )

                distances = [
                    abs(recent_avg - c)
                    for c in centroids
                ]
                closest_idx = distances.index(min(distances))

                if closest_idx == 2:
                    self.patient_profile = "Active"
                    self.adaptive_motion_threshold = 30
                    self.adaptive_alert_after_sec = 3600

                elif closest_idx == 1:
                    self.patient_profile = "Average"
                    self.adaptive_motion_threshold = 20
                    self.adaptive_alert_after_sec = 2400

                else:
                    self.patient_profile = "Weak"
                    self.adaptive_motion_threshold = 10
                    self.adaptive_alert_after_sec = 1800

        except Exception as exp:
            # Keep current/default profile if Catalog or Adapter
            # is temporarily unavailable.
            print(
                "Profile update failed, keeping defaults: "
                f"{exp}"
            )

        self.last_profile_update_time = time.time()

        print(
            f"Profile updated to: {self.patient_profile}, "
        #    f"Target: {self.target_activity_level}, "
            f"Threshold: {self.adaptive_motion_threshold}, "
            f"Alert Freq: {self.adaptive_alert_after_sec}s"
        )

    def start(self):
        self.register()
        self.client.start()
        self.client.subscribe(self.config["activity_topic"])

        self.update_patient_profile()   # initialization

    def notify(self, topic, payload):
        now = time.time()
        self.window.append((now, int(payload.get("motion_count", 0))))

        patient_id = payload.get("patientId", "unknown")

        if (
            now - self.last_profile_update_time
            >= self.update_interval_sec
        ):
            self.update_patient_profile(patient_id)

        cutoff = now - int(self.config.get("activity_window_sec", 60))

        while self.window and self.window[0][0] < cutoff:   # self.window avoid reaching empty deque
            self.window.popleft()

        total_motion = sum(value for _, value in self.window)

        status = "inactive" \
            if total_motion < self.adaptive_motion_threshold \
            else "active"
        
        if status == "inactive":
            self.inactive_since = self.inactive_since or now    # None or now
        else:
            self.inactive_since = None

        self.client.publish(
            self.config["activity_summary_topic"], 
            {
                "patientId": patient_id,
                "window_sec": self.config.get("activity_window_sec", 60),
                "motion_total": total_motion,
                "status": status,
                "profile": self.patient_profile
            }
        )

        alert_after = self.adaptive_alert_after_sec
        if self.inactive_since and now - self.inactive_since >= alert_after:
            self.client.publish(self.config["activity_alert_topic"], 
                                {
                                    "patientId": patient_id,
                                    "severity": "medium",
                                    "kind": "activity",
                                    "message": f"Prolonged inactivity detected for at least {alert_after} seconds",
                                }
            )
            self.inactive_since = now

        # long enough inactive time -> alert

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/controllers.json")
    args = parser.parse_args()
    service = ActivityController(args.config)
    service.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.client.stop()
