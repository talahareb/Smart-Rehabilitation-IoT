# MQTT Topics

Default topics use the prefix `/rehab/patient_001`.

## Raw sensor streams

| Topic | Publisher | Payload |
|---|---|---|
| `/rehab/patient_001/rpi/temperature` | Raspberry Pi connector | `temperature_c` |
| `/rehab/patient_001/rpi/activity` | Raspberry Pi connector | `motion_count` |
| `/rehab/patient_001/rpi/night_activity` | Raspberry Pi connector | `motion_count` |
| `/rehab/patient_001/rpi/pillbox` | Raspberry Pi connector | `event: open` |

## Alerts

| Topic | Publisher | Purpose |
|---|---|---|
| `/rehab/patient_001/alerts/temperature` | Vital Signs Controller | Fever and rapid temperature increase alerts |
| `/rehab/patient_001/alerts/activity` | Activity Controller | Inactivity alerts |
| `/rehab/patient_001/alerts/medication` | Medication Controller | Late or missed medication alerts |

## Summaries

| Topic | Publisher | Purpose |
|---|---|---|
| `/rehab/patient_001/summary/temperature` | Vital Signs Controller | Temperature status |
| `/rehab/patient_001/summary/activity` | Activity Controller | Activity status |
| `/rehab/patient_001/summary/sleep` | Sleep Controller | Sleep quality |
| `/rehab/patient_001/summary/medication` | Medication Controller | Medication adherence |

## Notifications

| Topic | Publisher | Subscriber |
|---|---|---|
| `/rehab/patient_001/notifications/reminder` | Reminder Scheduler | ThingSpeak Adapter, Telegram Notifier |
