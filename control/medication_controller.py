import argparse
import threading
import time
from datetime import datetime, timedelta

from common.config import load_json
from common.mqtt_client import MQTTClient
from common.registry import RegistryClient


class MedicationController:
    def __init__(self, config_path: str):
        self.config = load_json(config_path)
        self.registry = RegistryClient(self.config["catalog_url"])
        self.events = []

        self.medication_schedule = list(
            self.config.get("medication_schedule", ["08:00", "20:00"])
        )

        self.patient_id = self.config.get("patient_id", "patient_001")

        self.started_at = datetime.now()

        self.taken_schedules = {}
        self.missed_schedules = set()

        # self.evaluated_schedules = set()

        self._stop = threading.Event()
        self._schedule_thread = None

        self._state_lock = threading.Lock()

        mqtt_conf = self.config["mqtt"]
        self.client = MQTTClient(
            "medication_controller", 
            mqtt_conf["broker"], 
            mqtt_conf["port"], 
            self.notify)

    def register(self):
        self.registry.register({
            "registerType": "service",
            "id": "medication_controller",
            "type": "medication_controller",
            "attribute": {
                "input": self.config["pillbox_topic"], 
                "outputs": [
                    self.config["medication_alert_topic"], 
                    self.config["medication_summary_topic"]
                ]
            },
        })

    def load_catalog_settings(self):
        """Retrieve medication schedule and patient ID from System Catalog."""
        setting = self.registry.get_setting()

        schedule = setting.get("medication_schedule", [])

        with self._state_lock:
            if isinstance(schedule, list) and schedule:
                self.medication_schedule = list(schedule)

            self.patient_id = setting.get("patientId", self.patient_id)

    def start(self):
        self.register()
        self.load_catalog_settings()

        self.client.start()
        self.client.subscribe(self.config["pillbox_topic"])

        with self._state_lock:
            self.publish_missed_if_needed(datetime.now())

        self._schedule_thread = threading.Thread(target=self.schedule_loop, daemon=True)
        self._schedule_thread.start()
        # publish even the pillbox is not opened at all

    def stop(self):
        self._stop.set()
        if self._schedule_thread:
            self._schedule_thread.join(timeout=2)
        self.client.stop()

    def schedule_loop(self):
        while not self._stop.wait(int(self.config.get("schedule_check_interval_sec", 30))):
            try:
                self.load_catalog_settings()
            except Exception as exc:
                print(f"[medication] settings refresh failed: {exc}")

            with self._state_lock:
                self.publish_missed_if_needed(datetime.now())

    def notify(self, topic, payload):
        if payload.get("event") != "open":  # depend on the status of the pillbox
            return

        try:
            timestamp = float(payload.get("timestamp") or time.time())
        except (TypeError, ValueError):
            return

        now = datetime.fromtimestamp(timestamp)

        with self._state_lock:

            self.publish_missed_if_needed(now)
            self.events.append(now)

            status, scheduled = self.classify(now)
            if status is None:
                return 
            
            elif scheduled and status != "taken_after_missed":
                self.taken_schedules[self.schedule_key(now, scheduled)] = status

            adherence = self.adherence()

        self.client.publish(self.config["medication_summary_topic"], {
            "patientId": self.patient_id,
            "event": "pillbox_open",
            "timestamp": now.timestamp(),
            "schedule_id": (self.schedule_key(now, scheduled)
                            if scheduled else None),
            "status": status,
            "nearest_schedule": scheduled,
            "adherence": adherence,
        })

        if status in {"delayed", "missed"}:
            self.client.publish(self.config["medication_alert_topic"], {
                "patientId": self.patient_id,
                "timestamp": now.timestamp(),
                "schedule_id": self.schedule_key(now, scheduled),
                "severity": "medium",
                "kind": "medication",
                "message": f"Medication {status} for schedule {scheduled}",
            })

    def classify(self, actual_time):
        allowed = int(self.config.get("medication_on_time_window_min", 30))
        missed = int(self.config.get("medication_missed_after_min", 120))

        best = None
        best_delta = None
        for scheduled in self.medication_schedule:
            hour, minute = [int(x) for x in scheduled.split(":")]
            scheduled_time = actual_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

            delta_min = (actual_time - scheduled_time).total_seconds() / 60

            if best_delta is None or abs(delta_min) < abs(best_delta):
                best = scheduled
                best_delta = delta_min
        
        key = self.schedule_key(actual_time, best)
        if key in self.missed_schedules:
            return ("taken_after_missed", best)

        if key in self.taken_schedules.keys():
            return (None, None)
        if (best_delta <= allowed and best_delta >= -allowed):
            return ("on_time", best) 
        elif (best_delta > allowed and best_delta < missed):
            return ("delayed", best)
        else:
            return ("unscheduled", "")

    def publish_missed_if_needed(self, now):
        allowed = int(self.config.get("medication_missed_after_min", 120))

        for scheduled in self.medication_schedule:
            scheduled_time = self.scheduled_datetime(now, scheduled)
            if scheduled_time < self.started_at:
                continue
            key = self.schedule_key(scheduled_time, scheduled)

            if key in self.taken_schedules or key in self.missed_schedules:
                continue

            if now >= scheduled_time + timedelta(minutes=allowed):

                self.missed_schedules.add(key)
                self.client.publish(self.config["medication_alert_topic"], 
                {
                    "patientId": self.patient_id,
                    "timestamp": now.timestamp(),
                    "schedule_id": self.schedule_key(now, scheduled),
                    "severity": "medium",
                    "kind": "medication",
                    "message": f"Medication missed for schedule {scheduled}",
                })

                self.client.publish(self.config["medication_summary_topic"], 
                {
                    "patientId": self.patient_id,
                    "timestamp": now.timestamp(),
                    "schedule_id": self.schedule_key(now, scheduled),
                    "event": "schedule_missed",
                    "status": "missed",
                    "nearest_schedule": scheduled,
                    "adherence": self.adherence(),
                })

    def scheduled_datetime(self, base_time, scheduled):
        hour, minute = [int(x) for x in scheduled.split(":")]
        return base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def schedule_key(self, base_time, scheduled):
        return f"{base_time.date().isoformat()}T{scheduled}"    #"2026-08-16T18:30"

    def adherence(self):
        total = len(self.taken_schedules) + len(self.missed_schedules)

        on_time = sum(1 for status in self.taken_schedules.values() if status == "on_time")

        delayed = sum(1 for status in self.taken_schedules.values() if status == "delayed")
        missed = len(self.missed_schedules)
        rate = round(on_time / total, 2) if total else 1.0

        return {
                    "total": total,
                    "on_time": on_time, 
                    "delayed": delayed, 
                    "missed": missed, 
                    "on_time_rate": rate
                }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/controllers.json")
    args = parser.parse_args()
    service = MedicationController(args.config)
    service.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
