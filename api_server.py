import threading

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

_battery_data_fn = None
_settings_fn = None
_update_settings_fn = None
_refresh_fn = None
_devices_fn = None


def init_api(battery_data_fn, settings_fn, update_settings_fn, refresh_fn, devices_fn):
    global _battery_data_fn, _settings_fn, _update_settings_fn, _refresh_fn, _devices_fn
    _battery_data_fn = battery_data_fn
    _settings_fn = settings_fn
    _update_settings_fn = update_settings_fn
    _refresh_fn = refresh_fn
    _devices_fn = devices_fn


@app.route("/api/battery", methods=["GET"])
def get_battery():
    if _battery_data_fn is None:
        return jsonify({"error": "API not initialized"}), 500
    return jsonify(_battery_data_fn())


@app.route("/api/settings", methods=["GET"])
def get_settings():
    if _settings_fn is None:
        return jsonify({"error": "API not initialized"}), 500
    return jsonify(_settings_fn())


@app.route("/api/settings", methods=["POST"])
def update_settings():
    if _update_settings_fn is None:
        return jsonify({"error": "API not initialized"}), 500
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    result = _update_settings_fn(data)
    return jsonify(result)


@app.route("/api/devices", methods=["GET"])
def get_devices():
    if _devices_fn is None:
        return jsonify({"error": "API not initialized"}), 500
    return jsonify(_devices_fn())


@app.route("/api/refresh", methods=["POST"])
def refresh():
    if _refresh_fn is None:
        return jsonify({"error": "API not initialized"}), 500
    _refresh_fn()
    return jsonify({"status": "ok"})


def start_api_server(port=5000):
    thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    thread.start()
    print(f"API server started on http://127.0.0.1:{port}")
    return thread
