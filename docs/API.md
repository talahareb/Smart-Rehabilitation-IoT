# REST API

## System Catalog

Base URL: `http://127.0.0.1:8090`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/setting` | Platform configuration |
| `PATCH` | `/setting` | Update user-configurable schedules |
| `GET` | `/devices` | All registered devices |
| `GET` | `/devices/{type}` | Devices filtered by type |
| `GET` | `/services` | All registered services |
| `GET` | `/services/{type}` | Services filtered by type |
| `POST` | `/register` | Register a device or service |
| `DELETE` | `/device/{id}` | Remove device |
| `DELETE` | `/service/{id}` | Remove service |

Registration body:

```json
{
  "registerType": "device",
  "id": "rpi_temperature",
  "type": "temperature",
  "topic": "/rehab/patient_001/rpi/temperature",
  "attribute": {
    "unit": "C"
  }
}
```

Settings update body (all fields are optional, but at least one is required):

```json
{
  "medication_schedule": ["08:00", "13:00", "20:00"],
  "routine_reminder_lead_min": 5,
  "routine_reminder_late_min": 5,
  "sleep_time_schedule": {
    "start": "22:00",
    "end": "07:00"
  }
}
```

Schedule changes are persisted in `data/user_settings.json`. Controllers refresh
them while running, so the services do not need to be restarted.

## ThingSpeak Adapter REST

Base URL: `http://127.0.0.1:8092`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/latest` | Latest stored record by topic |
| `GET` | `/series?topic={topic}&limit=100` | Stored records for a topic |

## Dashboard Backend

Base URL: `http://127.0.0.1:8093`

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Browser dashboard |
| `GET` | `/api/latest` | Latest stored summaries |
| `GET` | `/api/series?topic={topic}` | Historical series proxy |
| `GET` | `/api/settings` | Current schedule settings |
| `PATCH` | `/api/settings` | Validate and save schedule settings |
