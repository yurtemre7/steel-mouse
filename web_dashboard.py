import time
import json
import sys
import os
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import database
import config as cfg
import i18n


def _get_data_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.realpath(__file__))


app = Flask(__name__,
            template_folder=os.path.join(_get_data_dir(), 'templates'),
            static_folder=os.path.join(_get_data_dir(), 'static'))
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
    try:
        if _battery_data_fn:
            return jsonify(_battery_data_fn())
    except Exception as e:
        print(f"API battery error: {e}")
    return jsonify({"level": None, "is_charging": False, "remaining_time": None, "name": None})


@app.route("/api/devices")
def api_devices():
    try:
        if _get_devices_fn:
            return jsonify(_get_devices_fn())
    except Exception as e:
        print(f"API devices error: {e}")
    return jsonify({"devices": []})


@app.route("/api/history/<device_id>")
def api_history(device_id):
    try:
        days = request.args.get("days", 7, type=int)
        limit = request.args.get("limit", 500, type=int)
        start_time = time.time() - (days * 86400)
        rows = database.get_history(device_id=device_id, start_time=start_time, limit=limit)
        rows.sort(key=lambda r: r["timestamp"])
        return jsonify({"history": rows})
    except Exception as e:
        print(f"API history error: {e}")
        return jsonify({"history": []})


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    try:
        if _settings_fn:
            return jsonify(_settings_fn())
    except Exception as e:
        print(f"API settings error: {e}")
    return jsonify({})


@app.route("/api/settings", methods=["POST"])
def api_update_settings():
    try:
        data = request.get_json(force=True)
        if _update_settings_fn:
            return jsonify(_update_settings_fn(data))
    except Exception as e:
        print(f"API update settings error: {e}")
    return jsonify({"error": "not available"}), 503


@app.route("/api/devices/all")
def api_all_devices_history():
    try:
        devices = database.get_devices()
        result = {}
        for dev in devices:
            did = dev["device_id"]
            rows = database.get_history(device_id=did, limit=200)
            rows.sort(key=lambda r: r["timestamp"])
            result[did] = {"name": dev["device_name"], "history": rows}
        return jsonify(result)
    except Exception as e:
        print(f"API all devices error: {e}")
        return jsonify({})


def start_dashboard(port=8080):
    import threading

    def run():
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    global _thread
    _thread = threading.Thread(target=run, daemon=True)
    _thread.start()
    print(f"Dashboard started on http://localhost:{port}")
    print(f"Dashboard also available at http://steel.local:{port}")
