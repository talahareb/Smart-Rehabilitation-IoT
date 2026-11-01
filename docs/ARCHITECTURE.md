# Architecture

This project follows the same pattern as the previous Smart Museum IoT project, adapted to smart rehabilitation.

## Main principles

- The System Catalog is a REST registry and configuration service.
- MQTT is the runtime event bus for sensor data, summaries, alerts, and reminders.
- The Raspberry Pi is one physical device that runs a connector service.
- Each simulated sensor is represented as a virtual device/topic registered in the catalog.
- Controllers perform analysis internally and publish results back to MQTT.
- ThingSpeak is optional historical storage; it is not part of the real-time control loop.
- The dashboard reads prepared data through REST and does not subscribe directly to MQTT.

## Runtime flow

1. Start the System Catalog.
2. Start the ThingSpeak Adapter, controllers, Reminder Scheduler, Dashboard Backend, and optional Telegram notifier.
3. Start the Raspberry Pi connector.
4. The connector registers virtual sensors and publishes raw streams.
5. Controllers subscribe to raw topics and publish summaries or alerts.
6. The Reminder Scheduler converts alerts into user-facing reminders.
7. The ThingSpeak Adapter stores selected summaries locally and optionally uploads them to ThingSpeak.
8. The Dashboard Backend serves the latest stored summaries to the browser.

## Services

| Service | Protocols | Responsibility |
|---|---|---|
| System Catalog | REST | Register devices/services and provide settings |
| Raspberry Pi Connector | REST + MQTT | Register virtual sensors and publish simulated data |
| Vital Signs Controller | REST + MQTT | Detect fever and rapid temperature increase |
| Activity Controller | REST + MQTT | Detect prolonged inactivity |
| Sleep Controller | REST + MQTT | Generate sleep quality summaries |
| Medication Controller | REST + MQTT | Classify pillbox events, detect missed schedules, and summarize adherence |
| Reminder Scheduler | REST + MQTT | Convert alerts into prioritized notifications and publish routine reminders |
| ThingSpeak Adapter | MQTT + REST | Store summaries locally and optionally upload to ThingSpeak |
| Dashboard Backend | REST | Serve dashboard and JSON endpoints |
| Telegram Notifier | MQTT + HTTPS | Optional Telegram delivery |
