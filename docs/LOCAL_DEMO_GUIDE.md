# 本机 Demo 启动指南

本文档适用于当前 macOS 本机 Demo。完整运行链路为：

```text
模拟 Raspberry Pi Connector
    -> Mosquitto MQTT
    -> Controllers / Reminder Scheduler
    -> 本地 JSONL 存储、Dashboard、ThingSpeak、Telegram
```

## 1. 首次安装

### 1.1 安装并配置 Mosquitto

```bash
brew install mosquitto
```

如果正式配置文件不存在，从 Homebrew 提供的示例创建：

```bash
test -f /opt/homebrew/etc/mosquitto/mosquitto.conf || \
  cp /opt/homebrew/etc/mosquitto/mosquitto.conf.example \
     /opt/homebrew/etc/mosquitto/mosquitto.conf
```

启动 MQTT Broker：

```bash
brew services start mosquitto
```

验证 `1883` 端口：

```bash
nc -z 127.0.0.1 1883 && echo "MQTT ready"
```

正常时会输出 `MQTT ready`。

### 1.2 创建 Python 虚拟环境

```bash
cd ~/projects/Smart-Rehabilitation-IoT
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

验证依赖：

```bash
python -c "import paho.mqtt.client, requests; print('Python dependencies ready')"
```

以后每次打开新终端，都需要先进入项目并激活虚拟环境：

```bash
cd ~/projects/Smart-Rehabilitation-IoT
source .venv/bin/activate
```

## 2. 外部服务配置

### 2.1 ThingSpeak

打开 [ThingSpeak](https://thingspeak.com/) 并登录 MathWorks 账号，然后：

1. 进入 `Channels -> My Channels`。
2. 点击 `New Channel`。
3. 将 Channel Name 设置为 `Smart Rehabilitation IoT`。
4. 勾选并填写下面四个 Field。

ThingSpeak Channel 使用以下字段：

| Field | 数据 |
|---|---|
| Field 1 | Temperature |
| Field 2 | Activity |
| Field 3 | Sleep Quality |
| Field 4 | Medication Adherence |

以下选项当前项目不会使用，可以保持空白或不勾选：

- Metadata
- Tags
- Link to External Site
- Link to GitHub
- Elevation
- Show Channel Location
- Show Video
- Show Status

点击页面底部的 `Save Channel` 完成创建。

#### 获取 Channel ID

保存后，进入该 Channel 的 `Channel Settings` 页面。页面顶部会显示一个纯数字的
`Channel ID`，例如：

```text
Channel ID: 1234567
```

只复制数字部分，不要复制 `Channel ID:` 标签。Channel ID 不是密码，但仍建议只
写入配置，不必放入报告截图。

#### 获取 Write API Key

进入该 Channel 的 `API Keys` 标签页，找到 `Write API Key` 并复制。不要误用：

- `Read API Key`：用于读取私有 Channel，不用于本项目上传。
- `User API Key`：账号级密钥，也不是本项目需要的密钥。
- `Write API Key`：本项目上传数据所需的密钥。

Channel 默认为私有是正常的。项目上传只需要 Channel ID 和 Write API Key，不需要
将 Channel 改成 Public，也不需要配置 Read API Key。

#### 写入项目配置

在 `configs/thingspeak.json` 中设置：

```json
"thingspeak": {
  "enabled": true,
  "channel_id": "YOUR_CHANNEL_ID",
  "write_api_key": "YOUR_WRITE_API_KEY",
  "min_upload_interval_sec": 16
}
```

不要把真实 Write API Key 写入文档或提交到 Git。

### 2.2 Telegram

首次配置时创建本地配置文件：

```bash
cp configs/telegram.json.example configs/telegram.json
```

在 `configs/telegram.json` 中填写 BotFather Token 和 Chat ID：

```json
"bot_token": "YOUR_BOT_TOKEN",
"chat_ids": [123456789]
```

同时确认 `configs/catalog.json` 中：

```json
"telegram_enabled": true
```

`configs/telegram.json` 已被 `.gitignore` 忽略，不应提交。

## 3. 每次启动完整 Demo

完整 Demo 使用两个终端。不要在同一个终端重复运行主脚本。

### 终端 1：启动 Broker 和主体服务

```bash
brew services start mosquitto

cd ~/projects/Smart-Rehabilitation-IoT
source .venv/bin/activate
bash scripts/run_pi_demo.sh
```

`run_pi_demo.sh` 会启动：

- System Catalog，端口 `8090`
- ThingSpeak Adapter，端口 `8092`
- Vital Signs Controller
- Activity Controller
- Sleep Controller
- Medication Controller
- Reminder Scheduler
- Dashboard Backend，端口 `8093`
- 模拟 Raspberry Pi Connector

Connector 在前台持续运行，因此这个终端不会返回命令提示符，这是正常现象。

### 终端 2：启动 Telegram Bot

```bash
cd ~/projects/Smart-Rehabilitation-IoT
source .venv/bin/activate
python -m notification.telegram_bot --config configs/telegram.json
```

当前主启动脚本不会自动启动 Telegram，因此终端 2 必须单独保留。

## 4. 验证运行状态

### 4.1 REST 服务

在第三个终端执行：

```bash
curl http://127.0.0.1:8090/health
curl http://127.0.0.1:8092/health
curl http://127.0.0.1:8093/health
```

三个接口都应返回：

```json
{"status": "ok"}
```

### 4.2 Dashboard

浏览器打开：

```text
http://127.0.0.1:8093
```

Dashboard 应显示体温、活动和服药等摘要，不应持续显示
`Adapter unavailable`。

### 4.3 ThingSpeak

主 Demo 终端中应出现：

```text
[thingspeak] upload response 200: NON_ZERO_ENTRY_ID
```

返回非零 Entry ID 表示上传成功。ThingSpeak 免费 Channel 的最小更新间隔为
15 秒，项目配置为 16 秒。

### 4.4 Telegram

在 Telegram 中向 Bot 发送：

```text
/status
```

Bot 应返回最新体温、活动、睡眠或服药摘要。也可以使用 `/help` 和
`/report`。

## 5. 停止 Demo

1. 在 Telegram Bot 终端按 `Ctrl+C`。
2. 在主体 Demo 终端按 `Ctrl+C`。
3. 主脚本会结束它启动的后台服务。

Mosquitto 默认继续作为 macOS 后台服务运行。需要停止时执行：

```bash
brew services stop mosquitto
```

## 6. 提交代码前处理密钥

`configs/telegram.json` 已被忽略，不需要删除。

`configs/thingspeak.json` 是 Git 追踪文件。提交或 push 前，把其中的云端配置恢复为：

```json
"thingspeak": {
  "enabled": false,
  "channel_id": "",
  "write_api_key": "",
  "min_upload_interval_sec": 16
}
```

然后确认暂存内容：

```bash
git diff --cached
```

当前 Write API Key 只存在于未提交的工作区；清空后再提交即可。如果密钥曾经
进入任何 commit 或已经 push，仅在新提交中删除并不能清除历史记录，此时必须在
ThingSpeak 的 API Keys 页面重新生成 Write API Key。

## 7. 常见问题

### `paho-mqtt is not installed`

说明启动脚本使用的 Python 环境不正确：

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### `brew services start` 成功，但 `1883` 没有响应

检查服务：

```bash
brew services list
```

如果 Mosquitto 为 `error 3`，通常是缺少正式配置文件：

```bash
cp /opt/homebrew/etc/mosquitto/mosquitto.conf.example \
   /opt/homebrew/etc/mosquitto/mosquitto.conf
brew services restart mosquitto
```

### `Address already in use`

说明旧服务仍占用端口。先确认对应进程：

```bash
lsof -nP -iTCP:8090 -sTCP:LISTEN
lsof -nP -iTCP:8092 -sTCP:LISTEN
lsof -nP -iTCP:8093 -sTCP:LISTEN
```

回到旧 Demo 终端按 `Ctrl+C`，再重新启动，不要同时运行两份 Demo。
