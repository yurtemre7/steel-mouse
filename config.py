import json
import os
import sys


def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.realpath(__file__))


CONFIG_FILE = os.path.join(_get_app_dir(), "config.json")

DEFAULT_CONFIG = {
    "time_delta": 300,
    "display_mode": "hover",
    "language": "tr",
    "api_port": 5000,
    "api_enabled": False,
    "mock": False,
    "mqtt_enabled": False,
    "mqtt_broker": "localhost",
    "mqtt_port": 1883,
    "mqtt_topic_prefix": "steelmouse",
    "mqtt_username": "",
    "mqtt_password": "",
    "mqtt_discovery": True,
    "dashboard_enabled": False,
    "dashboard_port": 8080,
    "auto_start": False,
    "design_capacity": 250,
}

_config = None


def load_config():
    global _config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _config = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in _config:
                    _config[key] = value
    except (FileNotFoundError, json.JSONDecodeError):
        _config = DEFAULT_CONFIG.copy()
        save_config()

    migrate_old_config()
    return _config


def save_config():
    global _config
    if _config is None:
        _config = DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(_config, f, indent=2, ensure_ascii=False)


def get_config():
    global _config
    if _config is None:
        load_config()
    return _config


def get(key, default=None):
    cfg = get_config()
    return cfg.get(key, default)


def set(key, value):
    cfg = get_config()
    cfg[key] = value
    save_config()


def update(values: dict):
    cfg = get_config()
    cfg.update(values)
    save_config()


def migrate_old_config():
    directory = _get_app_dir()
    changed = False

    time_delta_file = os.path.join(directory, "time_delta.txt")
    if os.path.exists(time_delta_file):
        try:
            with open(time_delta_file, "r") as f:
                content = f.read().strip()
                if content and content.isdigit():
                    _config["time_delta"] = int(content)
                    changed = True
            os.remove(time_delta_file)
            print("Migrated time_delta.txt to config.json")
        except Exception:
            pass

    display_mode_file = os.path.join(directory, "display_mode.txt")
    if os.path.exists(display_mode_file):
        try:
            with open(display_mode_file, "r") as f:
                content = f.read().strip().lower()
                if content in ["hover", "icon"]:
                    _config["display_mode"] = content
                    changed = True
            os.remove(display_mode_file)
            print("Migrated display_mode.txt to config.json")
        except Exception:
            pass

    if changed:
        save_config()
