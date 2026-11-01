import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

import requests

from common.config import load_json
from common.registry import RegistryClient

HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Smart Rehabilitation Dashboard</title>
  <style>
    :root {
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-soft: #f9fbfd;
      --text: #172033;
      --muted: #627084;
      --line: #dbe3ee;
      --blue: #2563eb;
      --teal: #0f9488;
      --green: #16a34a;
      --amber: #d97706;
      --red: #dc2626;
      --shadow: 0 14px 34px rgba(23, 32, 51, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-width: 320px;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    }

    .shell {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 24px 0 32px;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 0 22px;
      border-bottom: 1px solid var(--line);
    }

    h1 {
      margin: 0;
      font-size: clamp(24px, 3vw, 34px);
      font-weight: 760;
      letter-spacing: 0;
    }

    .subtitle {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 14px;
    }

    .statusbar {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .pill {
      min-height: 34px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 999px;
      padding: 7px 12px;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }

    .dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: var(--amber);
    }

    .dot.ok { background: var(--green); }
    .dot.bad { background: var(--red); }

    button {
      min-height: 34px;
      border: 1px solid #bdd0ee;
      background: #eaf2ff;
      color: #174ea6;
      border-radius: 8px;
      padding: 7px 12px;
      font: inherit;
      font-size: 13px;
      font-weight: 650;
      cursor: pointer;
    }

    button:hover { background: #dceaff; }

    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 22px 0;
    }

    .metric {
      min-height: 210px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 16px;
      display: grid;
      grid-template-rows: auto auto 1fr auto;
      gap: 12px;
    }

    .metric-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
    }

    .label {
      margin: 0;
      font-size: 13px;
      color: var(--muted);
      font-weight: 700;
      text-transform: uppercase;
    }

    .badge {
      border-radius: 999px;
      padding: 4px 9px;
      background: #eef2f7;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }

    .badge.normal { background: #e7f7ec; color: #166534; }
    .badge.warn { background: #fff4df; color: #92400e; }
    .badge.alert { background: #ffe7e7; color: #b91c1c; }

    .value {
      margin: 0;
      font-size: 34px;
      line-height: 1.05;
      font-weight: 780;
      letter-spacing: 0;
    }

    .detail {
      min-height: 18px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }

    canvas {
      width: 100%;
      height: 54px;
      display: block;
    }

    .lower {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
      gap: 14px;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 16px;
      min-width: 0;
    }

    .panel h2 {
      margin: 0 0 14px;
      font-size: 16px;
      letter-spacing: 0;
    }

    .settings-panel {
      margin-top: 14px;
    }

    .settings-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }

    .settings-head h2 {
      margin: 0;
    }

    .settings-message {
      min-height: 18px;
      color: var(--muted);
      font-size: 13px;
      text-align: right;
    }

    .settings-message.success { color: #166534; }
    .settings-message.error { color: #b91c1c; }

    .settings-grid {
      display: grid;
      grid-template-columns: minmax(240px, 1.4fr) repeat(4, minmax(135px, 1fr));
      gap: 16px;
      align-items: start;
    }

    .field-group {
      display: grid;
      gap: 8px;
      min-width: 0;
    }

    .field-group label,
    .field-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }

    input {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      color: var(--text);
      padding: 7px 10px;
      font: inherit;
      font-size: 14px;
    }

    input:focus {
      border-color: #7aa2df;
      outline: 2px solid #dbeafe;
      outline-offset: 1px;
    }

    .medication-times {
      display: grid;
      gap: 8px;
    }

    .time-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 38px;
      gap: 8px;
    }

    .icon-button {
      width: 38px;
      padding: 0;
      font-size: 19px;
      line-height: 1;
    }

    .settings-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-top: 16px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }

    th, td {
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }

    th {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }

    td.topic {
      color: #1e4c86;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    pre {
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 12px;
      color: #293449;
    }

    .empty {
      min-height: 140px;
      display: grid;
      place-items: center;
      border: 1px dashed var(--line);
      border-radius: 8px;
      color: var(--muted);
      background: var(--panel-soft);
      text-align: center;
      padding: 16px;
    }

    @media (max-width: 900px) {
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .lower { grid-template-columns: 1fr; }
      .settings-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .topbar { align-items: flex-start; flex-direction: column; }
      .statusbar { justify-content: flex-start; }
    }

    @media (max-width: 560px) {
      .shell { width: min(100% - 20px, 1180px); padding-top: 14px; }
      .summary { grid-template-columns: 1fr; }
      .settings-grid { grid-template-columns: 1fr; }
      .settings-head { align-items: flex-start; flex-direction: column; }
      .settings-message { text-align: left; }
      .value { font-size: 30px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1>Smart Rehabilitation Dashboard</h1>
        <p class="subtitle">Patient patient_001 | Raspberry Pi monitoring node</p>
      </div>
      <div class="statusbar">
        <span class="pill"><span class="dot" id="status-dot"></span><span id="status-text">Connecting</span></span>
        <span class="pill" id="updated">Last update: --</span>
        <button id="refresh" type="button">Refresh</button>
      </div>
    </header>

    <section class="summary" id="summary"></section>

    <section class="lower">
      <div class="panel">
        <h2>Latest Data</h2>
        <div id="latest-table"></div>
      </div>
      <div class="panel">
        <h2>Reminder Stream</h2>
        <div id="reminder"></div>
      </div>
    </section>

    <section class="panel settings-panel">
      <div class="settings-head">
        <h2>Schedule Settings</h2>
        <div class="settings-message" id="settings-message"></div>
      </div>
      <form id="settings-form">
        <div class="settings-grid">
          <div class="field-group">
            <span class="field-label">Medication Times</span>
            <div class="medication-times" id="medication-times"></div>
          </div>
          <label class="field-group">
            Reminder Lead (minutes)
            <input id="reminder-lead" type="number" min="0" max="180" step="1" required>
          </label>
          <label class="field-group">
            Reminder Grace (minutes)
            <input id="reminder-late" type="number" min="0" max="180" step="1" required>
          </label>
          <label class="field-group">
            Sleep Start
            <input id="sleep-start" type="time" required>
          </label>
          <label class="field-group">
            Sleep End
            <input id="sleep-end" type="time" required>
          </label>
        </div>
        <div class="settings-actions">
          <button id="add-medication-time" type="button">Add time</button>
          <button type="submit">Save settings</button>
        </div>
      </form>
    </section>
  </main>

  <script>
    const metrics = [
      {
        key: 'temperature',
        label: 'Temperature',
        topic: '/rehab/patient_001/summary/temperature',
        accent: '#dc2626',
        value: p => valueOrDash(p.moving_average_c, ' C'),
        detail: p => `Current ${valueOrDash(p.temperature_c, ' C')}`,
        status: p => p.status === 'fever' ? ['alert', 'Fever'] : ['normal', p.status || 'Normal'],
        sample: p => numberOrNull(p.moving_average_c ?? p.temperature_c)
      },
      {
        key: 'activity',
        label: 'Activity',
        topic: '/rehab/patient_001/summary/activity',
        accent: '#2563eb',
        value: p => valueOrDash(p.motion_total, ''),
        detail: p => `${p.window_sec || 60}s rolling motion`,
        status: p => p.status === 'inactive' ? ['warn', 'Inactive'] : ['normal', p.status || 'Active'],
        sample: p => numberOrNull(p.motion_total)
      },
      {
        key: 'sleep',
        label: 'Sleep Quality',
        topic: '/rehab/patient_001/summary/sleep',
        accent: '#7c3aed',
        value: p => valueOrDash(p.sleep_quality_score, ''),
        detail: p => `${p.restlessness_events ?? 0} restless events`,
        status: p => ['normal', 'Summary'],
        sample: p => numberOrNull(p.sleep_quality_score)
      },
      {
        key: 'medication',
        label: 'Medication',
        topic: '/rehab/patient_001/summary/medication',
        accent: '#0f9488',
        value: p => p.status ? titleCase(p.status) : '--',
        detail: p => p.nearest_schedule ? `Nearest schedule ${p.nearest_schedule}` : 'Waiting for pillbox event',
        status: p => {
          if (p.status === 'missed') return ['alert', 'Missed'];
          if (p.status === 'delayed') return ['warn', 'Delayed'];
          if (p.status === 'taken_after_missed') return ['warn', 'Taken Late'];
          return ['normal', p.status ? 'Recorded' : 'Waiting'];
        },
        sample: p => p.status === 'on_time' ? 1 : p.status === 'delayed' ? 0 : null
      }
    ];

    const reminderTopic = '/rehab/patient_001/notifications/reminder';
    const summaryRoot = document.getElementById('summary');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const updated = document.getElementById('updated');
    const settingsForm = document.getElementById('settings-form');
    const medicationTimesRoot = document.getElementById('medication-times');
    const settingsMessage = document.getElementById('settings-message');

    function setSettingsMessage(message, state = '') {
      settingsMessage.textContent = message;
      settingsMessage.className = `settings-message ${state}`.trim();
    }

    function addMedicationTime(value = '08:00') {
      const row = document.createElement('div');
      row.className = 'time-row';

      const input = document.createElement('input');
      input.type = 'time';
      input.required = true;
      input.value = value;
      input.setAttribute('aria-label', 'Medication time');

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'icon-button';
      remove.textContent = '-';
      remove.title = 'Remove medication time';
      remove.setAttribute('aria-label', 'Remove medication time');
      remove.addEventListener('click', () => {
        if (medicationTimesRoot.children.length > 1) row.remove();
      });

      row.append(input, remove);
      medicationTimesRoot.appendChild(row);
    }

    function renderSettings(setting) {
      medicationTimesRoot.innerHTML = '';
      const medicationSchedule = setting.medication_schedule || ['08:00'];
      medicationSchedule.forEach(addMedicationTime);

      document.getElementById('reminder-lead').value =
        setting.routine_reminder_lead_min ?? 5;
      document.getElementById('reminder-late').value =
        setting.routine_reminder_late_min ?? 5;

      const sleepSchedule = setting.sleep_time_schedule || {};
      document.getElementById('sleep-start').value = sleepSchedule.start || '22:00';
      document.getElementById('sleep-end').value = sleepSchedule.end || '07:00';
    }

    async function loadSettings() {
      try {
        const setting = await fetchJson('/api/settings');
        renderSettings(setting);
        setSettingsMessage('Settings loaded');
      } catch (error) {
        setSettingsMessage(`Unable to load settings: ${error.message}`, 'error');
      }
    }

    async function saveSettings(event) {
      event.preventDefault();
      setSettingsMessage('Saving...');

      const medicationSchedule = [...medicationTimesRoot.querySelectorAll('input')]
        .map(input => input.value)
        .filter(Boolean);

      const payload = {
        medication_schedule: medicationSchedule,
        routine_reminder_lead_min: Number(
          document.getElementById('reminder-lead').value
        ),
        routine_reminder_late_min: Number(
          document.getElementById('reminder-late').value
        ),
        sleep_time_schedule: {
          start: document.getElementById('sleep-start').value,
          end: document.getElementById('sleep-end').value,
        },
      };

      try {
        const response = await fetch('/api/settings', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.errorType || `${response.status} ${response.statusText}`);
        }

        renderSettings(result.setting || payload);
        setSettingsMessage('Settings saved', 'success');
      } catch (error) {
        setSettingsMessage(`Unable to save settings: ${error.message}`, 'error');
      }
    }

    function valueOrDash(value, suffix) {
      return value === undefined || value === null || value === '' ? '--' : `${value}${suffix}`;
    }

    function numberOrNull(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }

    function titleCase(value) {
      return String(value).replace(/_/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());
    }

    function formatTime(ts) {
      if (!ts) return '--';
      return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    function ensureCards() {
      summaryRoot.innerHTML = metrics.map(metric => `
        <article class="metric" data-key="${metric.key}">
          <div class="metric-head">
            <p class="label">${metric.label}</p>
            <span class="badge">Waiting</span>
          </div>
          <p class="value">--</p>
          <div class="detail">No data yet</div>
          <canvas width="320" height="64"></canvas>
        </article>
      `).join('');
    }

    function drawSparkline(canvas, rows, pickValue, accent) {
      const ctx = canvas.getContext('2d');
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);
      const values = rows.map(row => pickValue(row.payload || {})).filter(value => value !== null);
      if (values.length < 2) {
        ctx.strokeStyle = '#dbe3ee';
        ctx.beginPath();
        ctx.moveTo(0, height - 10);
        ctx.lineTo(width, height - 10);
        ctx.stroke();
        return;
      }
      const min = Math.min(...values);
      const max = Math.max(...values);
      const range = max - min || 1;
      ctx.lineWidth = 3;
      ctx.strokeStyle = accent;
      ctx.beginPath();
      values.forEach((value, index) => {
        const x = index * (width / (values.length - 1));
        const y = height - 8 - ((value - min) / range) * (height - 18);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.lineTo(width, height);
      ctx.lineTo(0, height);
      ctx.closePath();
      ctx.fillStyle = accent + '1f';
      ctx.fill();
    }

    async function fetchJson(url) {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return response.json();
    }

    async function updateMetric(metric, latest) {
      const card = document.querySelector(`[data-key="${metric.key}"]`);
      const row = latest[metric.topic];
      const payload = row ? row.payload || {} : {};
      const [statusClass, statusLabel] = row ? metric.status(payload) : ['warn', 'Waiting'];
      card.querySelector('.value').textContent = row ? metric.value(payload) : '--';
      card.querySelector('.detail').textContent = row ? metric.detail(payload) : 'Waiting for controller output';
      const badge = card.querySelector('.badge');
      badge.className = `badge ${statusClass}`;
      badge.textContent = statusLabel;
      try {
        const series = await fetchJson(`/api/series?topic=${encodeURIComponent(metric.topic)}&limit=40`);
        drawSparkline(card.querySelector('canvas'), series.data || [], metric.sample, metric.accent);
      } catch (error) {
        drawSparkline(card.querySelector('canvas'), [], metric.sample, metric.accent);
      }
    }

    function renderLatestTable(latest) {
      const entries = Object.entries(latest);
      const root = document.getElementById('latest-table');
      if (!entries.length) {
        root.innerHTML = '<div class="empty">Waiting for processed summaries.</div>';
        return;
      }
      root.innerHTML = `
        <table>
          <thead><tr><th style="width:42%">Topic</th><th style="width:18%">Time</th><th>Payload</th></tr></thead>
          <tbody>
            ${entries.map(([topic, row]) => `
              <tr>
                <td class="topic">${topic}</td>
                <td>${formatTime(row.timestamp)}</td>
                <td><pre>${JSON.stringify(row.payload || {}, null, 2)}</pre></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    function renderReminder(latest) {
      const row = latest[reminderTopic];
      const root = document.getElementById('reminder');
      if (!row) {
        root.innerHTML = '<div class="empty">No reminders published yet.</div>';
        return;
      }
      const payload = row.payload || {};
      root.innerHTML = `
        <div class="metric" style="min-height: 180px; box-shadow: none;">
          <div class="metric-head">
            <p class="label">Priority ${payload.priority ?? '--'}</p>
            <span class="badge ${payload.priority === 1 ? 'alert' : 'warn'}">${formatTime(row.timestamp)}</span>
          </div>
          <p class="value" style="font-size: 22px;">${payload.message || 'Reminder'}</p>
          <div class="detail">${payload.source_topic || ''}</div>
        </div>
      `;
    }

    async function refresh() {
      try {
        const data = await fetchJson('/api/latest');
        const latest = data.data || {};
        await Promise.all(metrics.map(metric => updateMetric(metric, latest)));
        renderLatestTable(latest);
        renderReminder(latest);
        statusDot.className = 'dot ok';
        statusText.textContent = 'Connected';
        updated.textContent = `Last update: ${new Date().toLocaleTimeString()}`;
      } catch (error) {
        statusDot.className = 'dot bad';
        statusText.textContent = 'Adapter unavailable';
        updated.textContent = 'Last update: failed';
      }
    }

    ensureCards();
    document.getElementById('refresh').addEventListener('click', refresh);
    document.getElementById('add-medication-time').addEventListener(
      'click',
      () => addMedicationTime('08:00')
    );
    settingsForm.addEventListener('submit', saveSettings);
    loadSettings();
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>"""

def resolve_adapter_url(config, registry):
    """Discover ThingSpeak Adapter from System Catalog, with local fallback."""
    fallback = config.get("adapter_url", "").rstrip("/")

    try:
        services = registry.get_services("thingspeak_adapter")

        for service in services.get("data", []):
            adapter_url = (
                service.get("attribute", {})
                .get("rest", "")
                .rstrip("/")
            )

            if adapter_url:
                return adapter_url

    except Exception as exc:
        print(
            "[dashboard] adapter discovery failed, "
            f"using fallback: {exc}"
        )

    return fallback


def make_handler(adapter_url, catalog_url):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload, code=200):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)

            if parsed.path == "/":
                data = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/html; charset=utf-8",
                )
                self.send_header(
                    "Content-Length",
                    str(len(data)),
                )
                self.end_headers()
                self.wfile.write(data)

            elif parsed.path == "/api/latest":
                self.proxy("/latest")

            elif parsed.path == "/api/series":
                self.proxy("/series?" + parsed.query)

            elif parsed.path == "/api/settings":
                self.proxy_request("GET", catalog_url + "/setting")

            elif parsed.path == "/health":
                self._send_json({"status": "ok"})

            else:
                self._send_json(
                    {
                        "status": "fail",
                        "errorType": "not found",
                    },
                    404,
                )

        def do_PATCH(self):
            if urlparse(self.path).path != "/api/settings":
                self._send_json(
                    {
                        "status": "fail",
                        "errorType": "not found",
                    },
                    404,
                )
                return

            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(
                    self.rfile.read(length).decode("utf-8")
                )
            except json.JSONDecodeError:
                self._send_json(
                    {
                        "status": "fail",
                        "errorType": "invalid json",
                    },
                    400,
                )
                return

            self.proxy_request(
                "PATCH",
                catalog_url + "/setting",
                payload,
            )

        def proxy(self, suffix):
            self.proxy_request("GET", adapter_url + suffix)

        def proxy_request(self, method, url, payload=None):
            try:
                response = requests.request(
                    method,
                    url,
                    json=payload,
                    timeout=5,
                )
                self._send_json(response.json(), response.status_code)

            except (requests.RequestException, ValueError) as exc:
                self._send_json(
                    {
                        "status": "fail",
                        "errorType": str(exc),
                    },
                    502,
                )

        def log_message(self, fmt, *args):
            print(f"[dashboard] {fmt % args}")

    return Handler


def run(config_path: str):
    config = load_json(config_path)

    host = config.get("host", "0.0.0.0")
    port = int(config.get("port", 8093))

    registry = RegistryClient(config["catalog_url"])

    # Register Dashboard Data Aggregator as a platform service.
    try:
        registry.register({
            "registerType": "service",
            "id": "dashboard_data_aggregator",
            "type": "dashboard_data_aggregator",
            "attribute": {
                "rest": config.get(
                    "rest_url",
                    f"http://127.0.0.1:{port}",
                ),
                "upstream": "thingspeak_adapter",
            },
        })

    except Exception as exc:
        print(
            "[dashboard] catalog registration failed: "
            f"{exc}"
        )

    # Prefer service discovery; keep adapter_url as fallback.
    adapter_url = resolve_adapter_url(config, registry)

    print(f"[dashboard] ThingSpeak Adapter: {adapter_url}")

    catalog_url = config["catalog_url"].rstrip("/")
    server = ThreadingHTTPServer(
        (host, port),
        make_handler(adapter_url, catalog_url),
    )

    print(f"[dashboard] running at http://{host}:{port}")

    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/dashboard.json",
    )
    args = parser.parse_args()

    run(args.config)
