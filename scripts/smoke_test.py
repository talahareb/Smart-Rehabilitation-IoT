"""Lightweight system-catalog smoke test; no MQTT/Telegram/ThingSpeak required."""
import json
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalog.system_catalog import CatalogState, make_handler
from common.config import load_json


def get_json(url, method="GET", payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, method=method, data=body,
                  headers={"Content-Type": "application/json"} if body else {})
    with urlopen(req, timeout=5) as response:
        return json.load(response)


def main():
    root = Path(__file__).resolve().parents[1]
    settings = load_json(str(root / "configs" / "catalog.json"))["setting"]
    with tempfile.TemporaryDirectory() as temp:
        state = CatalogState(settings, Path(temp) / "settings.json")
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            assert get_json(f"{base}/health")["status"] == "ok"
            result = get_json(f"{base}/register", method="POST", payload={
                "registerType": "device", "id": "test_sensor",
                "type": "temperature", "topic": "/smoke/temperature"
            })
            assert result["status"] == "success"
            devices = get_json(f"{base}/devices/temperature")["data"]
            assert any(device["id"] == "test_sensor" for device in devices)
            print("PASS: System Catalog health, registration, and retrieval")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)


if __name__ == "__main__":
    main()
