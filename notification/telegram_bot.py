import argparse
import threading
import time

import requests

from common.config import load_json
from common.mqtt_client import MQTTClient
from common.registry import RegistryClient


class TelegramNotifier:
    def __init__(self, config_path: str):
        self.config = load_json(config_path)
        self.registry = RegistryClient(self.config["catalog_url"])

        self.telegram_enabled = True
        self.language = "en"
        self.recent_messages = {}

        self._stop = threading.Event()
        self._schedule_thread = None

        mqtt = self.config["mqtt"]
        self.client = MQTTClient(
            "telegram_notifier",
            mqtt["broker"],
            mqtt["port"],
            self.notify,
        )

    def register(self):
        self.registry.register({
            "registerType": "service",
            "id": "telegram_notifier",
            "type": "telegram_notifier",
            "attribute": {
                "inputs": self.config["topics"]
            },
        })

    def load_catalog_preferences(self):
        setting = self.registry.get_setting()
        preferences = {}

        # default settings
        if isinstance(setting.get("notification_settings"), dict):
            preferences.update(setting["notification_settings"])

        # Original catalog.json settings take priority
        if isinstance(setting.get("notification"), dict):
            preferences.update(setting["notification"])

        self.language = preferences.get(
            "language",
            self.language,
        )

        self.telegram_enabled = bool(
            preferences.get("telegram_enabled",
                             self.telegram_enabled))

    def start(self):
        self.register()

        try:
            self.load_catalog_preferences()
        except Exception as exc:
            print(f"[telegram] using local defaults: {exc}")

        self.client.start()
        self.client.subscribe_many(self.config["topics"])

        # Enable simple Telegram commands when credentials exist
        if (
            self.telegram_enabled
            and self.config.get("enable_commands", True)
            and self.config.get("bot_token")
            and self.config.get("chat_ids")
        ):
            self._schedule_thread = threading.Thread(target=self._command_loop, daemon=True)
            self._schedule_thread.start()

    def _is_duplicate(self, message):
        now = time.time()
        last_time = self.recent_messages.get(message)

        self.recent_messages = {
            msg: ts
            for msg, ts in self.recent_messages.items()
            if now - ts < 30
        }

        self.recent_messages[message] = now

        return last_time is not None and now - last_time < 5

    def notify(self, topic, payload):
        if not self.telegram_enabled:
            return

        message = payload.get("message") \
            or f"New rehabilitation event: {payload}"

        # Alert and Reminder Scheduler may contain the same message
        if not self._is_duplicate(message):
            self.send_message(message)

    def send_message(self, message, chat_id=None):
        token = self.config.get("bot_token", "")

        chat_ids = (
            [chat_id]
            if chat_id is not None
            else self.config.get("chat_ids", [])
        )

        if not token or not chat_ids:
            print(f"[telegram] dry-run: {message}")
            return

        url = (
            f"https://api.telegram.org/"
            f"bot{token}/sendMessage"
        )

        for target in chat_ids:
            try:
                response = requests.post(
                    url,
                    data={
                        "chat_id": target,
                        "text": message,
                    },
                    timeout=5,
                )
                response.raise_for_status()

            except requests.RequestException as exc:
                print (f"[telegram] send failed: {exc}")

    def _get_adapter_url(self):
        services = self.registry.get_services("thingspeak_adapter")
        data = services.get("data", [])

        if not data:
            return ""

        return (
            data[0]
            .get("attribute", {})
            .get("rest", "")
            .rstrip("/")
        )

    @staticmethod
    def _format_summary(topic, payload):
        if "/summary/temperature" in topic:
            avg = payload.get("moving_average_c",
                            payload.get("temperature_c", "--"),)
            status = payload.get("status", "unknown")
            trend = payload.get("temperature_rate_c_per_min", "--")

            return (
                f"Temperature: {avg} C, "
                f"{status}, trend {trend} C/min"
            )

        if "/summary/activity" in topic:
            return (
                f"Activity: {payload.get('status', 'unknown')}, "
                f"profile {payload.get('profile', 'Average')}, "
                f"motion {payload.get('motion_total', '--')}"
            )

        if "/summary/sleep" in topic:
            return (
                f"Sleep: score "
                f"{payload.get('sleep_quality_score', '--')}, "
                f"duration "
                f"{payload.get('sleep_duration_hours', '--')} h, "
                f"restless events "
                f"{payload.get('restlessness_events', '--')}"
            )

        if "/summary/medication" in topic:
            return (
                f"Medication: "
                f"{payload.get('status', 'unknown')}, "
                f"adherence "
                f"{payload.get('adherence', {}).get('on_time_rate')}"
            )

        return ""

    def _latest_status_message(self):
        adapter_url = self._get_adapter_url()

        if not adapter_url:
            return "Latest status is currently unavailable."

        response = requests.get(f"{adapter_url}/latest", timeout=5)
        response.raise_for_status()

        latest = response.json().get("data", {})
        summaries = []

        for topic, row in latest.items():
            if "/summary/" not in topic:
                continue

            text = self._format_summary(topic, row.get("payload", {}))

            if text:
                summaries.append(text)

        return (
            "\n".join(summaries)
            or "No processed summaries available yet."
        )

    def _handle_command(self, text, chat_id):
        command = text.strip().lower()

        if command in {"/status", "/report"}:
            try:
                message = self._latest_status_message()
            except Exception as exc:
                message = f"Unable to retrieve the latest status: {exc}"

            self.send_message(message, chat_id)

        elif command in {"/start", "/help"}:
            self.send_message(
                "Smart Rehabilitation Bot\n"
                "/status - latest patient status\n"
                "/report - latest rehabilitation report",
                chat_id,
            )

    def _command_loop(self):
        token = self.config.get("bot_token", "")
        offset = None

        while True:
            try:
                params = {"timeout": 20}

                if offset is not None:
                    params["offset"] = offset

                response = requests.get(
                    (
                        f"https://api.telegram.org/"
                        f"bot{token}/getUpdates"
                    ),
                    params=params,
                    timeout=25,
                )
                response.raise_for_status()

                for update in response.json().get("result", []):
                    offset = update.get("update_id", 0) + 1
                
                    message = update.get("message", {})
                    text = message.get("text", "")
                    chat_id = (message.get("chat", {}).get("id"))

                    if text and chat_id is not None:
                        self._handle_command(text, chat_id,)

            except requests.RequestException as exc:
                print (f"[telegram] command polling: {exc}")
                time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/telegram.json")
    args = parser.parse_args()
    service = TelegramNotifier(args.config)
    service.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.client.stop()
