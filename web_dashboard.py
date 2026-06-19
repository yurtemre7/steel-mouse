import time
import json
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import database
import config as cfg
import i18n

app = Flask(__name__)
CORS(app)

_battery_data_fn = None
_settings_fn = None
_update_settings_fn = None
_get_devices_fn = None
_thread = None


def init_dashboard(battery_data_fn, settings_fn, update_settings_fn, get_devices_fn):
    global _battery_data_fn, _settings_fn, _update_settings_fn, _get_devices_fn
    _battery_data_fn = battery_data_fn
    _settings_fn = settings_fn
    _update_settings_fn = update_settings_fn
    _get_devices_fn = get_devices_fn


@app.route("/")
def index():
    lang = i18n.get_lang()
    return render_template("index.html", lang=lang)


@app.route("/history")
def history():
    lang = i18n.get_lang()
    return render_template("history.html", lang=lang)


@app.route("/settings")
def settings_page():
    lang = i18n.get_lang()
    return render_template("settings.html", lang=lang)


@app.route("/api/battery")
def api_battery():
    if _battery_data_fn:
        return jsonify(_battery_data_fn())
    return jsonify({"level": None, "is_charging": False, "remaining_time": None, "name": None})


@app.route("/api/devices")
def api_devices():
    if _get_devices_fn:
        return jsonify(_get_devices_fn())
    return jsonify({"devices": []})


@app.route("/api/history/<device_id>")
def api_history(device_id):
    days = request.args.get("days", 7, type=int)
    limit = request.args.get("limit", 500, type=int)
    start_time = time.time() - (days * 86400)
    rows = database.get_history(device_id=device_id, start_time=start_time, limit=limit)
    rows.sort(key=lambda r: r["timestamp"])
    return jsonify({"history": rows})


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    if _settings_fn:
        return jsonify(_settings_fn())
    return jsonify({})


@app.route("/api/settings", methods=["POST"])
def api_update_settings():
    data = request.get_json(force=True)
    if _update_settings_fn:
        return jsonify(_update_settings_fn(data))
    return jsonify({"error": "not available"}), 503


@app.route("/api/devices/all")
def api_all_devices_history():
    devices = database.get_devices()
    result = {}
    for dev in devices:
        did = dev["device_id"]
        rows = database.get_history(device_id=did, limit=200)
        rows.sort(key=lambda r: r["timestamp"])
        result[did] = {"name": dev["device_name"], "history": rows}
    return jsonify(result)


def start_dashboard(port=8080):
    import threading

    def run():
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    global _thread
    _thread = threading.Thread(target=run, daemon=True)
    _thread.start()
    print(f"Dashboard started on http://localhost:{port}")
