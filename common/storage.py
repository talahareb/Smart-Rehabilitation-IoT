import json
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class JsonlStore:
    """Tiny append-only time-series store for local Raspberry Pi testing."""

    def __init__(self, path: str):
        self.path = Path(path)  # to use the member functions of Path
        self.path.parent.mkdir(parents=True, exist_ok=True) 
        # parents = True -> create the middle directories if they don't exist, 
        # exist_ok = True -> no error if the directory already exists
    
    def append(self, topic: str, payload: Dict):
        record = {
            "topic": topic,
            "timestamp": payload.get("timestamp", time.time()),
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:   # "a" -> can create the file if it doesn't exist
            fh.write(json.dumps(record) + "\n") # dict -> JSON string, add a newline for each record

    def read(self, topic: Optional[str] = None, start_ts = None, end_ts = None, limit=None) -> List[Dict]:
        if not self.path.exists():
            return []
        rows = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if topic is not None and row.get("topic") != topic:
                    continue

                timestamp = row.get("timestamp")

                if timestamp is None:
                    continue

                timestamp = float(timestamp)

                if start_ts is not None and timestamp < start_ts:
                    continue

                if end_ts is not None and timestamp > end_ts:
                    continue

                rows.append(row)

        return rows[-limit:] if limit is not None else rows

    def latest_by_topic(self) -> Dict[str, Dict]:
        latest = {}
        for row in self.read():
            topic = row.get("topic")
            current = latest.get(topic)

            if (
                current is None
                or float(row["timestamp"]) >= float(current["timestamp"])
            ):
                latest[topic] = row
        return latest
