import argparse
import time
import json
from collections import deque
import urllib.request
from urllib.parse import urlencode
from datetime import datetime, timedelta

from common.config import load_json
from common.mqtt_client import MQTTClient
from common.registry import RegistryClient


class SleepController:
    def __init__(self, config_path: str):
        self.config = load_json(config_path)
        self.registry = RegistryClient(self.config["catalog_url"])

        self.window = deque()
        self.last_summary = 0

        self.finalized_session_ids = set()
        self.last_settings_refresh = 0

        self.night_schedule = dict(self.config.get("sleep_time_schedule", {
            "start" : "22:00",
            "end" : "7:00"
        }))

        self.historical_baseline_score = float(self.config.get(
            "historical_sleep_baseline_score", "0.0"))

        self.awakening_motion_threshold = int(self.config.get(
            "awakening_motion_threshold", 8))

        mqtt_conf = self.config["mqtt"]
        self.client = MQTTClient(
            "sleep_controller", 
            mqtt_conf["broker"], 
            mqtt_conf["port"], 
            self.notify
        )

    def _load_catalog_sleep_settings(self):
        """
        Retrieve sleep window and awakening threshold from System Catalog.
        """
        setting = self.registry.get_setting()

        schedule = setting.get("sleep_time_schedule")
        if isinstance(schedule, dict) and {"start", "end"} <= set(schedule):
            self.night_schedule = dict(schedule)

        thresholds = setting.get("thresholds", {})

        self.awakening_motion_threshold = int(thresholds.get(
                "awakening_motion_threshold", self.awakening_motion_threshold
                ))

    def register(self):
        self.registry.register({
            "registerType": "service",
            "id": "sleep_controller",
            "type": "sleep_controller",
            "attribute": {
                "input": self.config["night_activity_topic"], 
                "outputs": [self.config["sleep_summary_topic"]]
            },
        })

    def start(self):
        self.register()
        self._load_catalog_sleep_settings()
        self.last_settings_refresh = time.time()
        # self._fetch_historical_sleep_baseline()

        try:
            self._load_sleep_history()
        except Exception as exc:
            print(f"[sleep] history unavailable: {exc}")

        self.client.start()
        self.client.subscribe(self.config["night_activity_topic"])

    def _get_adapter_url(self):
        """
        Discover ThingSpeak Adapter through System Catalog.
        """
        services = self.registry.get_services("thingspeak_adapter")

        service_list = services.get("data", []) # response body, a list

        if not service_list:
            return ""

        return (
            service_list[0]
            .get("attribute", {})
            .get("rest", "")
            .rstrip("/")
        )

    def _fetch_series(self, topic, start_ts=None, end_ts=None):
        """
        Retrieve historical time-series data from
        ThingSpeak Adapter REST /series.
        """
        adapter_url = self._get_adapter_url()

        if not adapter_url:
            return []

        query_params = {
            "topic" : topic
        }

        if start_ts is not None:
            query_params["start_ts"] = start_ts

        if end_ts is not None:
            query_params["end_ts"] = end_ts

        query = urlencode(query_params)

        url = f"{adapter_url}/series?{query}"

        with urllib.request.urlopen(url, timeout=5, ) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

        return result.get("data", [])

    # def _fetch_historical_sleep_baseline(self):
    #     """
    #     Calculate historical sleep baseline from previously stored sleep summaries.
    #     """
    #     rows = self._fetch_series(
    #         self.config["sleep_summary_topic"], limit=50, )

    #     scores = []

    #     for row in rows:
    #         payload = row.get("payload", {})

    #         score = payload.get(
    #             "sleep_quality_score"
    #         )

    #         scores.append(float(score))

    #     if scores:
    #         self.historical_baseline_score = (
    #             sum(scores) / len(scores)
    #         )

    @staticmethod   # normal functions, without self, can be called without instance
    def _parse_schedule_time(value):
        """
        Convert schedule values such as:
        '22:00', '07:30'
        into hour/minute integers.
        """
        if isinstance(value, (int, float)):
            return int(value), 0

        text = str(value)

        if ":" in text:
            hour, minute = text.split(":", 1)
            return int(hour), int(minute)

        return int(text), 0

    def _latest_completed_sleep_window(self, reference_timestamp):
        """
        Determine the most recent sleep window that has completely finished before reference_timestamp.
        """
        reference = datetime.fromtimestamp(reference_timestamp)

        start_hour, start_minute = (
            self._parse_schedule_time(self.night_schedule["start"]))

        end_hour, end_minute = (
            self._parse_schedule_time(self.night_schedule["end"]))

        end_candidate = reference.replace(
            hour=end_hour,
            minute=end_minute,
            second=0,
            microsecond=0,
        )

        # If today's sleep end has not happened yet,
        # the latest completed session ended yesterday.
        if reference < end_candidate:
            session_end = end_candidate - timedelta(days=1)
        else:
            session_end = end_candidate

        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute
        
        if start_minutes > end_minutes:
            # Overnight schedule, e.g. 22:00 -> 07:00.
            duration_minutes =24 * 60 - start_minutes \
                + end_minutes

            session_start = session_end - timedelta(
                    minutes=duration_minutes)
            
        else:
            # Same-day schedule.
            session_start = session_end.replace(
                hour=start_hour,
                minute=start_minute,
                second=0,
                microsecond=0,
            )

        return (
            session_start.timestamp(),
            session_end.timestamp(),
        )

    def _fetch_completed_night_activity(self, reference_timestamp):
        """
        Retrieve raw night activity and keep only data belonging to the most recent completed sleep period.
        """
        start_ts, end_ts = self._latest_completed_sleep_window(
            reference_timestamp)
        
        rows = self._fetch_series(self.config["night_activity_topic"], 
                                  start_ts, end_ts)

        session = []

        for row in rows:
            payload = row.get("payload", {})

            timestamp = row.get("timestamp",
                                payload.get("timestamp"),)

            if timestamp is None:
                continue

            timestamp = float(timestamp)

            if (start_ts <= timestamp <= end_ts):
                motion = int(payload.get("motion_count",0,))

                session.append((timestamp, motion))

        session.sort(key=lambda item: item[0])
        return session

    def _load_sleep_history(self):
        rows = self._fetch_series(topic=self.config["sleep_summary_topic"])

        scores = []

        for row in rows:
            payload = row.get("payload", {})

            if(payload.get("analysis_source", "") != "historical_completed_session"):
                continue

            session_id = payload.get("session_id")  # the default is None

            if not session_id:
                continue

            score = payload.get("sleep_quality_score")

            if score is None:
                continue

            if session_id in self.finalized_session_ids:
                continue

            scores.append(float(score))
            self.finalized_session_ids.add(session_id)

        if scores:
            self.historical_baseline_score = sum(scores) / len(scores)

    @staticmethod
    def _format_schedule_value(value):
        if isinstance(value, (int, float)):
            return f"{int(value):02d}:00"   # 8 -> 08, 7 -> 07, 22 -> 22

        text = str(value)

        if ":" not in text and text.isdigit():
            return f"{int(text):02d}:00"

        return text

    def notify(self, topic, payload):

        now = time.time()

        refresh_interval = int(
            self.config.get("settings_refresh_interval_sec", 30)
        )
        if now - self.last_settings_refresh >= refresh_interval:
            try:
                self._load_catalog_sleep_settings()
            except Exception as exc:
                print(f"[sleep] settings refresh failed: {exc}")
            finally:
                self.last_settings_refresh = now

        motion = int(payload.get("motion_count", 0))
        self.window.append((now, motion))

        cutoff = now - int(self.config.get("sleep_window_sec", 300))
        while self.window and self.window[0][0] < cutoff:
            self.window.popleft()
        interval = int(self.config.get("sleep_summary_interval_sec", 60))
        if now - self.last_summary < interval:
            return
        self.last_summary = now

        start_ts, end_ts = self._latest_completed_sleep_window(now)
        session_id = f"{start_ts}--{end_ts}"

        if session_id in self.finalized_session_ids:
            return

        analysis_window = []
        try:
            analysis_window = (
                self._fetch_completed_night_activity(now))
            
        except Exception as exc:
            print(
                "Full-night history unavailable, " \
                "using real-time buffer: {exc}"
            )
        
        #     analysis_window = list(self.window)
        #     data_source = "realtime_buffer"
        # else:
        #     data_source = "historical_completed_session"

        movements = [value for _, value in analysis_window]
        if not movements:
            return

        sleep_duration_sec = analysis_window[-1][0] - analysis_window[0][0]

        expected_interval = float(
            self.config.get("night_activity_sample_interval_sec", 5)
        )
        planned_duration_sec = end_ts - start_ts
        expected_samples = planned_duration_sec / expected_interval

        if len(analysis_window) < expected_samples * 0.9:
            return

        if sleep_duration_sec < planned_duration_sec * 0.9:
            return

        # if len(analysis_window) >= 2:
        #     sleep_duration_sec = analysis_window[-1][0] \
        #         - analysis_window[0][0]
        # else:
        #     sleep_duration_sec = 0

        sleep_duration_hours = round(sleep_duration_sec / 3600.0, 4)

        if (self.historical_baseline_score< 75.0):
            adaptive_threshold = max(4, self.awakening_motion_threshold- 2)
        else:
            adaptive_threshold = self.awakening_motion_threshold

        # movements = [value for _, value in self.window]
        # restlessness = sum(1 for value in movements 
        #                    if value >= adaptive_threshold)

        restlessness = 0
        high_motion_streak = 0

        for motion in movements:
            if motion >= adaptive_threshold:
                high_motion_streak += 1
                if high_motion_streak == 3:
                    restlessness += 1
            else:
                high_motion_streak = 0
        
        avg_motion = round(sum(movements) / len(movements), 2)
        
        score = max(0, min(100, 100 - restlessness * 12 - avg_motion * 2))

        baseline_deviation = round(score - self.historical_baseline_score, 1)

        # start_text = (self._format_schedule_value(
        #     self.night_schedule["start"]))

        # end_text = ( self._format_schedule_value(
        #     self.night_schedules["end"]))

        self.client.publish(self.config["sleep_summary_topic"], {
            "patientId" : payload.get("patientId"),
            "session_id" : session_id,
            "sleep_quality_score" : round(score, 1),
            "restlessness_events" : restlessness,
            "average_motion" : avg_motion,
            "sleep_duration_hours" : sleep_duration_hours,
            # "historical_baseline_deviation" : baseline_deviation
            "analysis_source" : "historical_completed_session"
        })

        self.finalized_session_ids.add(session_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/controllers.json")
    args = parser.parse_args()
    service = SleepController(args.config)
    service.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.client.stop()
