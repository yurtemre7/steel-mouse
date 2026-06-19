# SteelMouse

A Windows system tray application that monitors SteelSeries mouse battery level, with smart home integration via MQTT and REST API.

![System Tray Image of the App SteelMouse](assets/image.png)

## Features

- **Battery Monitoring**: Real-time battery level display in system tray
- **Remaining Time Estimation**: Calculates estimated time remaining based on discharge rate
- **Charging Status**: Shows whether the mouse is charging or discharging
- **Turkish/English Support**: Menu-based language selection
- **MQTT Integration**: Publish battery data to Home Assistant, Google Home, Apple Home
- **REST API**: Local API for custom integrations
- **Configurable Update Interval**: 1min, 5min, 10min, 30min, 1h

## Table of Contents

- [Features](#features)
- [Usage](#usage)
- [Tested Devices](#tested-devices)
- [Installation](#installation)
- [MQTT Setup (Home Assistant)](#mqtt-setup-home-assistant)
- [REST API](#rest-api)
- [Configuration](#configuration)
- [Building from Source](#building-application-and-installer-from-source)
- [Troubleshooting](#troubleshooting)
- [Acknowledgements](#acknowledgements)
- [License](#license)

## Usage

Once the application is started, you can hover over the icon to see the battery level and remaining time.

Right-click the tray icon to access:
- **Battery**: Current level and remaining time
- **Status**: Charging/Discharging
- **Tray battery display**: Switch between hover and icon percentage display
- **Language**: Türkçe / English
- **Refresh**: Force immediate battery update
- **API**: Toggle REST API on/off
- **MQTT**: Toggle MQTT connection on/off

## Tested/Working Devices

- Steelseries AEROX 3 Wireless (2.4G and wired mode)
- Steelseries AEROX 5 Wireless (2.4G mode)
- Steelseries AEROX 9 Wireless (2.4G mode)
- Steelseries Prime Wireless
- Steelseries Prime Mini Wireless

## Installation

### Pre-built Executable (Recommended)

1. Download the latest `mouse.exe` from the [Releases](https://github.com/crowroser/steel-mouse/releases/) tab.
2. Place `mouse.exe` in a folder of your choice.
3. Create a `config.json` in the same folder (see [Configuration](#configuration)).
4. Run `mouse.exe`.

### Manual Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/crowroser/steel-mouse.git
   cd steel-mouse
   ```

2. Install Python 3.10+ and dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Run the application:
   ```sh
   python mouse.py
   ```

## MQTT Setup (Home Assistant)

SteelMouse supports MQTT auto-discovery for Home Assistant.

### Prerequisites

- MQTT broker (e.g., Mosquitto) running on your network
- Home Assistant with MQTT integration configured

### Configuration

Add to your `config.json`:

```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.1.100",
  "mqtt_port": 1883,
  "mqtt_topic_prefix": "steelmouse",
  "mqtt_username": "",
  "mqtt_password": "",
  "mqtt_discovery": true
}
```

### MQTT Topics

| Topic | Description |
|-------|-------------|
| `steelmouse/battery/level` | Battery percentage (0-100) |
| `steelmouse/battery/charging` | Charging status (true/false) |
| `steelmouse/battery/remaining_time` | Remaining time in seconds |
| `steelmouse/battery/name` | Device name |
| `steelmouse/status` | Online/Offline status |

### Home Assistant Auto-Discovery

When `mqtt_discovery` is enabled, SteelMouse automatically publishes discovery messages to:
- `homeassistant/sensor/steelmouse_battery/config`
- `homeassistant/binary_sensor/steelmouse_charging/config`
- `homeassistant/sensor/steelmouse_remaining/config`

Home Assistant will automatically detect and add these sensors.

## REST API

SteelMouse includes a local REST API (disabled by default).

### Enable API

Set `"api_enabled": true` in `config.json` or toggle via the tray menu.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/battery` | Battery level, charging status, remaining time |
| GET | `/api/settings` | Current application settings |
| POST | `/api/settings` | Update settings (JSON body) |
| GET | `/api/devices` | List connected devices |
| POST | `/api/refresh` | Force battery refresh |

### Example Response

```json
{
  "level": 85,
  "is_charging": false,
  "remaining_time": 3600,
  "remaining_time_str": "1h 0m",
  "last_update": 1781869992.63,
  "name": "SteelSeries Aerox 3 Wireless"
}
```

## Configuration

Create a `config.json` in the application directory:

```json
{
  "time_delta": 300,
  "display_mode": "hover",
  "language": "tr",
  "api_port": 5000,
  "api_enabled": false,
  "mock": false,
  "mqtt_enabled": false,
  "mqtt_broker": "localhost",
  "mqtt_port": 1883,
  "mqtt_topic_prefix": "steelmouse",
  "mqtt_username": "",
  "mqtt_password": "",
  "mqtt_discovery": true
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `time_delta` | 300 | Update interval in seconds |
| `display_mode` | "hover" | "hover" or "icon" |
| `language` | "tr" | "tr" (Turkish) or "en" (English) |
| `api_port` | 5000 | REST API port |
| `api_enabled` | false | Enable REST API |
| `mock` | false | Use mock mouse for testing |
| `mqtt_enabled` | false | Enable MQTT publishing |
| `mqtt_broker` | "localhost" | MQTT broker address |
| `mqtt_port` | 1883 | MQTT broker port |
| `mqtt_topic_prefix` | "steelmouse" | MQTT topic prefix |
| `mqtt_username` | "" | MQTT username (optional) |
| `mqtt_password` | "" | MQTT password (optional) |
| `mqtt_discovery` | true | Enable HA auto-discovery |

## Building from Source

To build a standalone executable:

```sh
pip install pyinstaller
pyinstaller --onefile --icon=images/logo.ico --noconsole --add-data "images;images" mouse.py
```

The executable will be in the `dist/` folder.

## Troubleshooting

If you encounter any issues, first check the [`KNOWNISSUES.md`](./KNOWNISSUES.md) file.

For debugging, run with console output:

```sh
python mouse.py
```

## Acknowledgements

- [DeveloperX19](https://github.com/DeveloperX19) for the license of his intellectual property of the icon art.
- [flozz](https://github.com/flozz) for the `rivalcfg` library and the idea of a standalone Python executable.
- [Pyenb](https://github.com/Pyenb) for rewrites.
- [T-solidus-T](https://github.com/T-solidus-T) for improvements to the threads, icon & menu logic.
- [bossman90](https://github.com/bossman90) for the battery charging indicator in the system tray.

## License

MIT: Feel free to use this code as you wish. If you do use it, I'd appreciate a mention.
