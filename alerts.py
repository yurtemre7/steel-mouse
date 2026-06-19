import time

try:
    from win10toast import ToastNotifier
    _toaster = ToastNotifier()
except ImportError:
    _toaster = None

try:
    import winsound
except ImportError:
    winsound = None


WARNING_THRESHOLD = 20
CRITICAL_THRESHOLD = 10
COOLDOWN_SECONDS = 300

_last_alerts = {}


def check_battery_level(device_id, device_name, level, is_charging):
    if is_charging:
        return None

    if level <= CRITICAL_THRESHOLD:
        severity = "critical"
        title = "Critical Battery"
        message = f"{device_name} battery is at {level}%! Please charge immediately!"
        sound = True
    elif level <= WARNING_THRESHOLD:
        severity = "warning"
        title = "Low Battery"
        message = f"{device_name} battery is at {level}%. Consider charging soon."
        sound = False
    else:
        return None

    if _is_in_cooldown(device_id):
        return None

    _record_alert(device_id)
    _send_notification(title, message)
    if sound:
        _play_sound()

    return {"severity": severity, "device_id": device_id, "device_name": device_name, "level": level}


def _is_in_cooldown(device_id):
    last = _last_alerts.get(device_id)
    if last is None:
        return False
    return (time.time() - last) < COOLDOWN_SECONDS


def _record_alert(device_id):
    _last_alerts[device_id] = time.time()


def _send_notification(title, message):
    if _toaster is not None:
        try:
            _toaster.show_toast(title, message, duration=5, threaded=True)
            return
        except Exception:
            pass
    print(f"[{title}] {message}")


def _play_sound():
    if winsound is not None:
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass


def get_last_alert_time(device_id):
    return _last_alerts.get(device_id)


def reset_cooldowns():
    _last_alerts.clear()
