import argparse
import json
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
# REST server
from urllib.parse import parse_qs, urlparse
# HTTP query parsing (URL query string)
import requests
# POST to ThingSpeak

from common.config import load_json
from common.mqtt_client import MQTTClient
from common.registry import RegistryClient
from common.storage import JsonlStore


class ThingSpeakAdapter:    
    # 1. store data to local file (uploading to ThingSpeak) 
    # 2. dashboard REST query
    """Stores summaries locally and optionally forwards them to ThingSpeak."""

    def __init__(self, config_path: str):
        self.config = load_json(config_path)
        self.registry = RegistryClient(self.config["catalog_url"])
        self.store = JsonlStore(self.config.get("local_store", "data/timeseries.jsonl"))    # local timing storage even without ThingSpeak
        self.last_upload_at = 0 # last upload timestamp to respect min_upload_interval_sec
        mqtt_conf = self.config["mqtt"]
        self.client = MQTTClient("thingspeak_adapter", mqtt_conf["broker"], mqtt_conf["port"], self.notify) # create a MQTT client that will call self.notify on new messages

    def register(self): # to system_catalog "curl http://127.0.0.1:8090/services"
        self.registry.register({
            "registerType": "service",
            "id": "thingspeak_adapter",
            "type": "thingspeak_adapter",
            "attribute": {
                "inputs": self.config["summary_topics"], 
                "rest": self.config.get("rest_url", "")
            },
        })

    def start_mqtt(self):
        self.register()
        self.client.start() # connect to Mosquitto
        self.client.subscribe_many(self.config["summary_topics"])   # subscribe to those topics
        self.client.subscribe_many(self.config["raw_topics"])

    def notify(self, topic, payload):
        self.store.append(topic, payload)   # local storage
        if topic in self.config["summary_topics"]:
            self.upload_if_configured(topic, payload)

    def upload_if_configured(self, topic, payload):
        ts = self.config.get("thingspeak", {})
        if not ts.get("enabled"):
            return
        
        channel_id = ts.get("channel_id")
        write_key = ts.get("write_api_key")

        if not channel_id or not write_key:
            return
        fields = self.map_fields(topic, payload)    # map the payload to the filed of thingspeak
        if not fields:
            return
        
        min_interval = int(ts.get("min_upload_interval_sec", 16))
        now = time.time()
        if now - self.last_upload_at < min_interval:
            print(f"[thingspeak] skipped upload to respect {min_interval}s interval: {topic}")
            return
        url = f"https://api.thingspeak.com/update"
        data = {"api_key": write_key, **fields}
        try:
            response = requests.post(url, data=data, timeout=5) # POST
            self.last_upload_at = now   # can use different timestamp for each upload filed 
            print(f"[thingspeak] upload response {response.status_code}: {response.text.strip()}")
        except requests.RequestException as exc:
            print(f"[thingspeak] upload failed: {exc}")

    def map_fields(self, topic, payload):
        if "temperature" in topic:
            return {"field1": payload.get("moving_average_c", payload.get("temperature_c", ""))}
        if "activity" in topic:
            return {"field2": payload.get("motion_total", "")}
        if "sleep" in topic:
            return {"field3": payload.get("sleep_quality_score", "")}
        if "medication" in topic:
            status = payload.get("status", "")
            return {"field4": 1 if status == "on_time" else 0}  # in digit
        return {}

    def make_handler(self):
        adapter = self  # 闭包, save the outside reference

        class Handler(BaseHTTPRequestHandler):  # HTTP request handler
            def _send(self, payload, code=200):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                parsed = urlparse(self.path)    # parse拆解 the URL like, parsed.path, parsed.query, parsed.fragment (?)
                params = parse_qs(parsed.query) # query -> dict (= -> :)

                if parsed.path == "/series":    # read from the local storage instead of thingspeak
                    topic = params.get("topic", [None])[0]  # only use the first topic
                    limit = params.get("limit", [None])[0]  # the number of records to read, default 200
                    start_ts = params.get("start_ts", [None])[0]
                    end_ts = params.get("end_ts", [None])[0]

                    if limit is not None:
                        limit = int(limit)

                    start_ts = float(start_ts) if start_ts is not None else None
                    end_ts = float(end_ts) if end_ts is not None else None

                    self._send({
                        "status": "success", 
                        "data": adapter.store.read(topic=topic, start_ts=start_ts, end_ts=end_ts, limit=limit)})
                elif parsed.path == "/latest":
                    self._send({
                        "status": "success", 
                        "data": adapter.store.latest_by_topic()})
                elif parsed.path == "/health":
                    self._send({
                        "status": "ok"})
                else:
                    self._send({
                        "status": "fail", 
                        "errorType": "not found"}, 404)

            def log_message(self, fmt, *args): # fmt -> string, args -> string tuple
                print(f"[adapter-rest] {fmt % args}")   # add a prefix to print the requests that server received

        return Handler

    def serve_rest(self):
        rest = self.config.get("rest", {})
        host = rest.get("host", "0.0.0.0")
        port = int(rest.get("port", 8092))
        server = ThreadingHTTPServer((host, port), self.make_handler()) # create a HTTP server. Use handler to handle each request
        print(f"[adapter-rest] running at http://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()  # read the parameters from command line (a reader)
    parser.add_argument("--config", default="configs/thingspeak.json")  # decide the config file automatically
    args = parser.parse_args()  # get the real parameters from command line, the real config file with --config or default
    adapter = ThingSpeakAdapter(args.config)
    adapter.start_mqtt()
    adapter.serve_rest()