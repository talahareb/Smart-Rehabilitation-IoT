# Smart Rehabilitation IoT Platform

**A modular IoT prototype for supporting post-operative rehabilitation through simulated health monitoring, activity analysis, medication reminders, and user-facing notifications.**

**Project area:** Internet of Things · Smart Healthcare · Microservices · Data Analytics

## The Problem

Recovery after surgery often continues at home, where patients, caregivers, and medical staff may have limited visibility into everyday indicators such as temperature, movement, sleep patterns, and medication adherence. Monitoring these signals separately makes it harder to recognize concerning trends or deliver timely reminders.

This project explores how an interconnected IoT platform can organize those signals, process them automatically, and present actionable information through a dashboard and notifications.

## Our Solution

The **Smart Rehabilitation IoT Platform** uses a simulated Raspberry Pi sensor connector, an MQTT message broker, and independent Python monitoring services to form an end-to-end rehabilitation-monitoring prototype.

The platform brings together:

- **Health monitoring:** temperature readings, activity levels, nighttime movement, and pillbox events.
- **Data processing:** specialized controllers analyze incoming sensor messages and publish summaries or alerts.
- **Adaptive activity profiling:** a lightweight one-dimensional K-means implementation groups historical activity data into three levels to adjust inactivity thresholds.
- **Patient awareness:** a web dashboard displays processed information, and an optional Telegram bot delivers alerts and status reports.
- **Historical data:** locally stored time series, with optional ThingSpeak upload.

The project uses **simulated sensor signals** and is intended as a software prototype, not a validated medical monitoring device.

## System Architecture

![Original team proposal diagram showing Raspberry Pi, MQTT, processing controllers, System Catalog, ThingSpeak, dashboard, and Telegram notifications](docs/images/proposed-system-architecture.jpg)

*Architecture diagram from the team's original Smart Rehabilitation IoT proposal. It represents the intended system design; the repository implements the central services in Python.*

### How the System Works

1. A **Raspberry Pi connector** generates simulated sensor readings and publishes them to MQTT topics.
2. A **System Catalog** registers devices and services and exposes configuration through REST endpoints.
3. Independent **monitoring controllers** subscribe to their sensor topics and process incoming events.
4. Controllers publish **health summaries, alerts, and reminders** through MQTT.
5. A **ThingSpeak adapter** retains selected time-series data locally and can optionally upload it to ThingSpeak.
6. A **dashboard backend** serves processed summaries and configurable schedules through REST endpoints to its browser interface.
7. An optional **Telegram bot** sends notifications and responds to simple status/report commands.

### Data Flow

```text
Simulated Raspberry Pi sensors
         │ MQTT
         ▼
     Mosquitto broker ──────────► Controllers
                                   │  temperature / activity /
                                   │  sleep / medication /
                                   │  reminders
                                   ▼
                           MQTT summaries & alerts
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
            Storage / ThingSpeak             Telegram bot
                    │
                    │ REST
                    ▼
             Dashboard backend
                    │
                    ▼
                Web dashboard

System Catalog ◄──── REST registration and settings ──── Services
```

## Key Features

| Component | What it does |
| --- | --- |
| **Vital Signs Controller** | Applies a moving average and temperature-based checks to produce health summaries and fever-related alerts. |
| **Activity Controller** | Processes rolling movement data, detects extended inactivity, and includes a small 1D K-means routine for activity profiling when historical data is available. |
| **Sleep Controller** | Analyzes nighttime activity to summarize sleep duration, movement, and restlessness. |
| **Medication Controller** | Compares simulated pillbox events with schedules and produces adherence summaries and alerts. |
| **Reminder Scheduler** | Combines time-based reminders and monitoring alerts. |
| **System Catalog** | Registers devices/services and provides centralized settings over REST. |
| **Dashboard** | Presents monitoring information and supports updates to certain user schedules/settings. |
| **ThingSpeak Adapter** | Stores time-series messages locally and optionally forwards selected metrics to ThingSpeak. |
| **Telegram Notifier** | Supports notifications and basic bot commands when configured. |

### Activity Profiling: Data-Driven Adaptation

The activity controller contains a **custom one-dimensional K-means routine** for analyzing historical movement totals retrieved through the adapter's REST API. With sufficient history, it assigns an **Active**, **Average**, or **Weak** profile and adjusts inactivity thresholds and alert timing. If historical data is unavailable or insufficient, the controller retains its configured defaults.

This is a lightweight example of unsupervised grouping within a broader rule-based IoT system. It is not a clinically evaluated prediction model.

## Technology Stack

| Area | Tools / technologies |
| --- | --- |
| Language | Python |
| IoT communication | MQTT, Mosquitto, `paho-mqtt` |
| Service communication | REST APIs, Python HTTP servers |
| Device layer | Raspberry Pi-oriented connector with simulated sensor data |
| Analysis | Rolling windows, moving averages, thresholds, 1D K-means |
| Visualization | Browser-based dashboard (HTML, CSS, JavaScript) |
| Historical storage | Local JSONL time series; optional ThingSpeak |
| Notifications | Telegram Bot API, `requests` |

## Project Structure

```text
Smart-Rehabilitation-IoT/
├── catalog/             # Device/service registry and shared settings
├── connector/           # Simulated Raspberry Pi sensor publisher
├── control/             # Vital signs, activity, sleep, medication, reminders
├── adapter/             # Local storage and optional ThingSpeak integration
├── dashboard/           # REST backend and browser interface
├── notification/        # Optional Telegram bot
├── common/              # Shared networking, registration, configuration
├── configs/             # Service configuration and Telegram template
├── scripts/             # Local demo launchers and smoke test
├── docs/
│   ├── images/          # Original proposal architecture figure
│   └── ...              # Additional protocol and API documentation
├── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Python 3 and `pip`
- An MQTT broker such as **Mosquitto**, available on `localhost:1883`
- A browser for the dashboard

### 1. Download the project and install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate the environment using `.venv\Scripts\Activate.ps1` instead.

### 2. Start the MQTT broker

Install and run Mosquitto for your operating system. The project defaults to `localhost:1883`. On Debian/Ubuntu, for example:

```bash
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

### 3. Verify the System Catalog

```bash
python3 scripts/smoke_test.py
```

This lightweight test checks the System Catalog HTTP endpoint, registration, and retrieval without requiring a running MQTT broker.

### 4. Launch the local demonstration

On macOS or Linux, from the project root:

```bash
bash scripts/run_pi_demo.sh
```

The script starts the System Catalog, adapter, controllers, scheduler, dashboard, and simulated sensor connector. See [`docs/LOCAL_DEMO_GUIDE.md`](docs/LOCAL_DEMO_GUIDE.md) for a more detailed macOS setup and [`scripts/run_local_demo.ps1`](scripts/run_local_demo.ps1) for the Windows launcher.

### 5. Open the dashboard

```text
http://127.0.0.1:8093
```

### Optional: Telegram notifications

Create a private local config file from the provided example:

```bash
cp configs/telegram.json.example configs/telegram.json
```

Set your Telegram bot token and permitted chat ID(s) in `configs/telegram.json`, then run:

```bash
python3 -m notification.telegram_bot --config configs/telegram.json
```

**Never commit actual bot tokens or other API credentials.** Telegram is optional; the main monitoring demo does not require it.

### Optional: ThingSpeak

The adapter stores data locally by default. To enable cloud upload, configure `configs/thingspeak.json` with your channel ID and write API key and set `thingspeak.enabled` to `true`. Avoid committing live credentials.

## Demonstration and Testing

The implementation includes working REST endpoints, controllers, simulated device messages, local data storage, and dashboard code. In local software checks, the System Catalog HTTP API and simulated sensor-processing-to-dashboard flow were exercised, including an abnormal-temperature alert and reminder.

These checks used **simulated MQTT delivery**, rather than a live Mosquitto broker. Actual Raspberry Pi hardware, external Telegram delivery, and ThingSpeak cloud uploading require their own configuration and validation.

## Potential Extensions

- Replace simulated data with physical sensor measurements.
- Expand sensor coverage and support multiple patients.
- Evaluate activity profiling with larger, labeled datasets.
- Add more comprehensive testing and dashboard visualizations.
- Introduce stronger authentication, privacy controls, and operational monitoring for real-world use.

## Project Team and Credits

This is a **collaborative project** developed by:

- **Tala Hareb**
- **Xiang Li**
- **Shiyun Tang**
- **Xianlu Feng**

The original use-case proposal (version 0.7, November 2025) provides the motivation, objectives, and architecture diagram featured above. The code package is based on the collaborative project's updated implementation, available from the [original repository](https://github.com/lixiang4312-beep/SMART_REHAB_IoT).
