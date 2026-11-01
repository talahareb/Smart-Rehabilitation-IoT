import argparse
from datetime import datetime, timedelta
import threading
import time

from common.config import load_json
from common.mqtt_client import MQTTClient
from common.registry import RegistryClient


class ReminderScheduler:
    def __init__(self, config_path: str):
        self.config = load_json(config_path)
        self.registry = RegistryClient(self.config["catalog_url"])

        self.time_schedules = self.config.get("medication_schedule", [])
        self.last_routine_reminder_at = {}

        self.patient_id = self.config.get("patient_id", "patient_001")

        self._stop = threading.Event()
        self._schedule_thread = None

        self.lead = self.config.get("routine_reminder_lead_min", 5)
        self.late = self.config.get("routine_reminder_late_min", 5) # allowed latency

        mqtt_conf = self.config["mqtt"]
        self.client = MQTTClient("reminder_scheduler", mqtt_conf["broker"], mqtt_conf["port"], self.notify)

    def register(self):
        self.registry.register({
            "registerType": "service",
            "id": "reminder_scheduler",
            "type": "reminder_scheduler",
            "attribute": {
                "inputs": self.config["alert_topics"], 
                "output": self.config["notification_topic"]
            },
        })

    def load_catalog_settings(self):
        """
        Retrieve time-based reminder schedules and patient ID
        from System Catalog.
        """
        setting = self.registry.get_setting()

        schedules = setting.get("medication_schedule", [])
        self.lead = setting.get("routine_reminder_lead_min", self.lead)
        self.late = setting.get("routine_reminder_late_min", self.late)

        if isinstance(schedules, list) and schedules:
            self.time_schedules = list(schedules)

        self.patient_id = setting.get(
            "patientId",
            self.patient_id,
        )

    def start(self):
        self.register()
        self.load_catalog_settings()

        self.client.start()
        self.client.subscribe_many(self.config["alert_topics"])

        self._schedule_thread = threading.Thread(target=self.run_schedule_loop, daemon=True)
        self._schedule_thread.start()

    def stop(self):
        self._stop.set()
        if self._schedule_thread:
            self._schedule_thread.join(timeout=2)
        self.client.stop()

    def notify(self, topic, payload):
        priority = {"high": 1, "medium": 2, "low": 3} \
            .get(payload.get("severity"), 3)
        self.client.publish(
            self.config["notification_topic"], 
        {
            "patientId": payload.get("patientId"),
            "priority": priority,
            "source_topic": topic,
            "message": payload.get("message", "New rehabilitation reminder"),
        })

    def run_schedule_loop(self):
        while not self._stop.wait(int(self.config.get("schedule_check_interval_sec", 30))):
            try:
                self.load_catalog_settings()
            except Exception as exc:
                print(f"[reminder] settings refresh failed: {exc}")

            self.publish_due_routine_reminders()

    def publish_due_routine_reminders(self):
        now = datetime.now()

        lead = timedelta(minutes=int(self.lead))
        late = timedelta(minutes=int(self.late))

        for scheduled in self.time_schedules:
            due_time = self.scheduled_datetime(now, scheduled)

            key = f"medication:{due_time.date().isoformat()}T{scheduled}"   # YYYY-MM-DD

            if key in self.last_routine_reminder_at:    # reminder only once per scheduled time
                continue

            if due_time - lead <= now <= due_time + late:   # reminder window
                self.last_routine_reminder_at[key] = time.time()
                self.client.publish(self.config["notification_topic"], 
                {
                    "patientId": self.patient_id,
                    "priority": 3,
                    "source_topic": "routine_schedule",
                    "message": f"Medication reminder for schedule {scheduled}",
                })

    def scheduled_datetime(self, base_time, scheduled):
        hour, minute = [int(x) for x in scheduled.split(":")]
        return base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/controllers.json")
    args = parser.parse_args()
    service = ReminderScheduler(args.config)
    service.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
