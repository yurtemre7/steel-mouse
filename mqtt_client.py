import threading
import json

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

_client = None
_connected = False
_battery_data_fn = None
_config = {}
_discovery_sent = False


def init_mqtt(battery_data_fn, config):
    global _battery_data_fn, _config
    _battery_data_fn = battery_data_fn
    _config = config


def _on_connect(client, userdata, flags, rc, properties=None):
    global _connected, _discovery_sent
    if rc == 0:
        _connected = True
        print(f"MQTT connected to {_config.get('mqtt_broker', 'localhost')}")
        if _config.get("mqtt_discovery", True):
            _send_discovery()
    else:
        print(f"MQTT connection failed with code {rc}")


def _on_disconnect(client, userdata, rc, properties=None):
    global _connected
    _connected = False
    print("MQTT disconnected")


def _send_discovery():
    global _discovery_sent
    if _client is None or not _connected:
        return

    prefix = _config.get("mqtt_topic_prefix", "steelmouse")
    discovery_prefix = "homeassistant"

    battery_config = {
        "name": "SteelSeries Mouse Battery",
        "state_topic": f"{prefix}/battery/level",
        "unit_of_measurement": "%",
        "device_class": "battery",
        "unique_id": "steelmouse_battery",
        "availability_topic": f"{prefix}/status",
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": {
            "identifiers": ["steelmouse"],
            "name": "SteelSeries Mouse",
            "manufacturer": "SteelSeries",
        },
    }
    _client.publish(
        f"{discovery_prefix}/sensor/steelmouse_battery/config",
        json.dumps(battery_config),
        retain=True,
    )

    charging_config = {
        "name": "SteelSeries Mouse Charging",
        "state_topic": f"{prefix}/battery/charging",
        "payload_on": "true",
        "payload_off": "false",
        "device_class": "battery_charging",
        "unique_id": "steelmouse_charging",
        "availability_topic": f"{prefix}/status",
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": {
            "identifiers": ["steelmouse"],
            "name": "SteelSeries Mouse",
            "manufacturer": "SteelSeries",
        },
    }
    _client.publish(
        f"{discovery_prefix}/binary_sensor/steelmouse_charging/config",
        json.dumps(charging_config),
        retain=True,
    )

    remaining_config = {
        "name": "SteelSeries Mouse Remaining Time",
        "state_topic": f"{prefix}/battery/remaining_time",
        "unit_of_measurement": "s",
        "device_class": "duration",
        "unique_id": "steelmouse_remaining",
        "availability_topic": f"{prefix}/status",
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": {
            "identifiers": ["steelmouse"],
            "name": "SteelSeries Mouse",
            "manufacturer": "SteelSeries",
        },
    }
    _client.publish(
        f"{discovery_prefix}/sensor/steelmouse_remaining/config",
        json.dumps(remaining_config),
        retain=True,
    )

    _discovery_sent = True
    print("MQTT discovery messages sent")


def publish_battery_data():
    if _client is None or not _connected or _battery_data_fn is None:
        return

    data = _battery_data_fn()
    prefix = _config.get("mqtt_topic_prefix", "steelmouse")

    _client.publish(f"{prefix}/battery/level", str(data.get("level", "")), retain=True)
    _client.publish(
        f"{prefix}/battery/charging",
        str(data.get("is_charging", False)).lower(),
        retain=True,
    )
    _client.publish(
        f"{prefix}/battery/remaining_time",
        str(data.get("remaining_time", "")),
        retain=True,
    )
    _client.publish(f"{prefix}/battery/name", data.get("name", ""), retain=True)
    _client.publish(f"{prefix}/status", "online", retain=True)


def start_mqtt():
    global _client

    if mqtt is None:
        print("paho-mqtt not installed, MQTT disabled")
        return

    broker = _config.get("mqtt_broker", "localhost")
    port = _config.get("mqtt_port", 1883)
    username = _config.get("mqtt_username", "")
    password = _config.get("mqtt_password", "")

    _client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    _client.on_connect = _on_connect
    _client.on_disconnect = _on_disconnect

    if username:
        _client.username_pw_set(username, password)

    try:
        _client.connect(broker, port, 60)
        _client.loop_start()
        print(f"MQTT client started, connecting to {broker}:{port}")
    except Exception as e:
        print(f"MQTT connection error: {e}")


def stop_mqtt():
    global _client, _connected
    if _client is not None:
        prefix = _config.get("mqtt_topic_prefix", "steelmouse")
        _client.publish(f"{prefix}/status", "offline", retain=True)
        _client.loop_stop()
        _client.disconnect()
        _connected = False
        _client = None
        print("MQTT client stopped")
