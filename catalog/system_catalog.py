import argparse
import copy
import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer # server side
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from common.config import load_json

MUTABLE_SETTING_KEYS = {
    "medication_schedule",
    "routine_reminder_lead_min",
    "routine_reminder_late_min",
    "sleep_time_schedule",
}


def _normalize_time(value):
    if not isinstance(value, str):
        raise ValueError("schedule times must use HH:MM strings")

    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ValueError(f"invalid schedule time: {value}") from exc

    return parsed.strftime("%H:%M")


def validate_setting_update(payload):
    if not isinstance(payload, dict) or not payload:
        raise ValueError("settings update must be a non-empty JSON object")

    unsupported = set(payload) - MUTABLE_SETTING_KEYS
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ValueError(f"unsupported setting keys: {names}")

    normalized = {}

    if "medication_schedule" in payload:
        schedule = payload["medication_schedule"]
        if not isinstance(schedule, list) or not schedule:
            raise ValueError("medication_schedule must be a non-empty list")
        if len(schedule) > 12:
            raise ValueError("medication_schedule supports at most 12 times")

        values = [_normalize_time(value) for value in schedule]
        if len(set(values)) != len(values):
            raise ValueError("medication_schedule contains duplicate times")
        normalized["medication_schedule"] = sorted(values)

    for key in ("routine_reminder_lead_min", "routine_reminder_late_min"):
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
        if not 0 <= value <= 180:
            raise ValueError(f"{key} must be between 0 and 180")
        normalized[key] = value

    if "sleep_time_schedule" in payload:
        schedule = payload["sleep_time_schedule"]
        if not isinstance(schedule, dict):
            raise ValueError("sleep_time_schedule must be an object")
        if set(schedule) != {"start", "end"}:
            raise ValueError("sleep_time_schedule requires start and end")

        start = _normalize_time(schedule["start"])
        end = _normalize_time(schedule["end"])
        if start == end:
            raise ValueError("sleep start and end must be different")
        normalized["sleep_time_schedule"] = {
            "start": start,
            "end": end,
        }

    return normalized


class CatalogState: # server status, receiving new registration
    def __init__(self, setting: Dict, user_settings_path=None):
        self.setting = copy.deepcopy(setting)
        self.devices: List[Dict] = []   # device catalog
        self.services: List[Dict] = []  # service catalog
        self._lock = threading.RLock()
        self.user_settings_path = (
            Path(user_settings_path)
            if user_settings_path else None
        )
        self.user_settings = {}
        self._load_user_settings()

    def _load_user_settings(self):
        if not self.user_settings_path or not self.user_settings_path.exists():
            return

        try:
            payload = json.loads(
                self.user_settings_path.read_text(encoding="utf-8")
            )
            normalized = validate_setting_update(payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"[catalog] ignoring invalid user settings: {exc}")
            return

        self.user_settings.update(normalized)
        self.setting.update(copy.deepcopy(normalized))

    def _persist_user_settings(self, settings):
        if not self.user_settings_path:
            return

        self.user_settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.user_settings_path.with_suffix(
            self.user_settings_path.suffix + ".tmp"
        )
        temporary_path.write_text(
            json.dumps(settings, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.user_settings_path)

    def get_setting(self):
        with self._lock:
            return copy.deepcopy(self.setting)

    def update_setting(self, payload):
        normalized = validate_setting_update(payload)
        with self._lock:
            user_settings = copy.deepcopy(self.user_settings)
            user_settings.update(copy.deepcopy(normalized))
            self._persist_user_settings(user_settings)

            self.user_settings = user_settings
            self.setting.update(copy.deepcopy(normalized))
            setting = copy.deepcopy(self.setting)

        return {
            "status": "success",
            "updated": normalized,
            "setting": setting,
        }

    def register(self, item: Dict) -> Dict:
        if not isinstance(item, dict):
            return {
                "status": "fail",
                "errorType": "registration body must be an object",
                "setting": ""}

        kind = item.get("registerType")
        if kind not in {"device", "service"}:
            return {
                "status": "fail", 
                "errorType": "registerType must be device or service", 
                "setting": ""}
        if not item.get("id") or not item.get("type"):
            return {
                "status": "fail", 
                "errorType": "missing id or type", 
                "setting": ""}
        
        with self._lock:
            target = self.devices if kind == "device" else self.services

            for index, existing in enumerate(target):
                if existing.get("id") == item["id"]:    # update
                    target[index] = item
                    return {
                        "status": "success",
                        "errorType": "None",
                        "setting": copy.deepcopy(self.setting),
                        "updated": True}

            target.append(item) # append new item
            return {
                "status": "success",
                "errorType": "None",
                "setting": copy.deepcopy(self.setting)}

    def delete(self, kind: str, object_id: str) -> Dict:
        with self._lock:
            target = self.devices if kind == "device" else self.services
            before = len(target)
            target[:] = [item for item in target if item.get("id") != object_id] # edit the quote can also edit the original list
            return {
                "status": "success",
                "deleted": before - len(target)}

    def list_items(self, kind: str, item_type: str = None) -> Dict:
        with self._lock:
            target = self.devices if kind == "devices" else self.services
            data = [
                copy.deepcopy(item)
                for item in target
                if item_type is None or item.get("type") == item_type
            ]
        return {
            "status": "success", 
            "data": data}

def make_handler(state: CatalogState):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload: Dict, code: int = 200):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path not in {"/", "/register"}:
                self._send({
                    "status": "fail", 
                    "errorType": "not found"}, 404)
                return
            length = int(self.headers.get("Content-Length", "0"))   # HTTP header contains the length of body
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))   # read the body of the request and decode it to a string, then parse it as JSON
            except json.JSONDecodeError:    # invalid JSON expression
                self._send({
                    "status": "fail", 
                    "errorType": "invalid json"}, 400)
                return
            result = state.register(payload)
            self._send(result, 200 if result["status"] == "success" else 400)

        def do_GET(self):
            parts = [p for p in urlparse(self.path).path.split("/") if p]   # exsiting
            if parts == ["setting"]:
                self._send(state.get_setting())
            elif parts and parts[0] in {"devices", "services"}:
                self._send(state.list_items(parts[0], parts[1] if len(parts) > 1 else None)) # None -> list all items
            elif parts and parts[0] == "config" and len(parts) == 2:
                config_key = parts[1]
                setting = state.get_setting()
                if config_key in setting:
                    self._send({
                        "status": "success",
                        config_key: setting[config_key]
                    })
                else:
                    self._send({
                        "status": "fail", 
                        "errorType": f"config key '{config_key}' not found"}, 404)
            elif parts == ["health"]:
                self._send({"status": "ok"})
            else:
                self._send({
                    "status": "fail", 
                    "errorType": "not found"}, 404)

        def do_PATCH(self):
            if urlparse(self.path).path != "/setting":
                self._send({
                    "status": "fail",
                    "errorType": "not found"}, 404)
                return

            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(
                    self.rfile.read(length).decode("utf-8")
                )
                result = state.update_setting(payload)
            except json.JSONDecodeError:
                self._send({
                    "status": "fail",
                    "errorType": "invalid json"}, 400)
                return
            except ValueError as exc:
                self._send({
                    "status": "fail",
                    "errorType": str(exc)}, 400)
                return
            except OSError as exc:
                self._send({
                    "status": "fail",
                    "errorType": f"unable to persist settings: {exc}"}, 500)
                return

            self._send(result)

        def do_DELETE(self):
            parts = [p for p in urlparse(self.path).path.split("/") if p]
            if len(parts) == 2 and parts[0] in {"device", "service"}:
                self._send(state.delete(parts[0], parts[1]))
            else:
                self._send({
                    "status": "fail", 
                    "errorType": "not found"}, 404)

        def log_message(self, fmt, *args):
            print(f"[catalog] {self.address_string()} - {fmt % args}")  
            # obtain the address of the client that sent the request and print it with the log message 
            # self.client_address -> (host, port) tuple, 
            # self.address_string() -> host name or IP address of the client
    return Handler


def run(config_path: str):
    config = load_json(config_path)
    user_settings_path = Path(
        config.get("user_settings_path", "data/user_settings.json")
    )
    if not user_settings_path.is_absolute():
        project_root = Path(config_path).resolve().parent.parent
        user_settings_path = project_root / user_settings_path

    state = CatalogState(config["setting"], user_settings_path)
    host = config.get("host", "0.0.0.0")   
    port = int(config.get("port", 8090))
    server = ThreadingHTTPServer((host, port), make_handler(state))
    print(f"[catalog] running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/catalog.json")
    args = parser.parse_args()
    run(args.config)
