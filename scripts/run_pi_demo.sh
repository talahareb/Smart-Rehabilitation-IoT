#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Starting Smart Rehabilitation IoT demo."
echo "This script assumes Mosquitto is running on localhost:1883."

trap 'echo "Stopping Smart Rehab services..."; jobs -p | xargs -r kill' EXIT
# 把后台启动的服务一起关掉，避免端口被旧进程占住

python3 -m catalog.system_catalog --config configs/catalog.json &
sleep 1
python3 -m adapter.thingspeak_adapter --config configs/thingspeak.json &
sleep 1
python3 -m control.vital_signs_controller --config configs/controllers.json &
python3 -m control.activity_controller --config configs/controllers.json &
python3 -m control.sleep_controller --config configs/controllers.json &
python3 -m control.medication_controller --config configs/controllers.json &
python3 -m control.reminder_scheduler --config configs/controllers.json &
sleep 1
python3 -m dashboard.dashboard_backend --config configs/dashboard.json &
sleep 1
python3 -m connector.raspberry_pi_connector --config configs/raspberry_pi_connector.json
