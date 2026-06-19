import rivalcfg, pystray, os, time, threading
import hid as hid_lib
from PIL import Image, ImageDraw, ImageFont
from mock_mouse import MockMouse
from battery_estimator import BatteryEstimator
import i18n
import config as cfg
import mqtt_client
import database
import auto_start
import alerts

last_update = None
battery_level = None
battery_charging = None
icon = None
image = None
stopped = False
event = None
mock = False

estimator = BatteryEstimator()
mouse_name = None

devices = {}
active_device_id = None
mouse_objects = {}

time_error_retry = 1 / 20
time_error = 60 * 0.2

import sys

def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.realpath(__file__))

def _get_data_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.realpath(__file__))

directory = f"{_get_app_dir()}/"
image_directory = f"{_get_data_dir()}/images/"


def load_config():
    cfg.load_config()
    i18n.set_lang(cfg.get("language", "tr"))


def create_menu():
    remaining = estimator.get_remaining_seconds()
    remaining_str = i18n.format_remaining_time(remaining)
    interval = cfg.get("time_delta", 300)
    api_enabled = cfg.get("api_enabled", False)
    mqtt_enabled = cfg.get("mqtt_enabled", False)
    lang = i18n.get_lang()

    menu_items = []

    if len(devices) > 1:
        device_menu_items = []
        for dev_id, dev_data in devices.items():
            dev_type_label = f"[{dev_data['type'].capitalize()}]"
            dev_name = f"{dev_data['name']} {dev_type_label}"
            text = f"{dev_name} ({dev_data['level']}%)" if dev_data['level'] is not None else dev_name
            device_menu_items.append(
                pystray.MenuItem(
                    text=text,
                    action=set_active_device,
                    checked=lambda dev_id=dev_id: dev_id == active_device_id,
                    default=(dev_id == active_device_id),
                    radio=True,
                )
            )
        menu_items.append(
            pystray.MenuItem(
                text=i18n.t("select_device"),
                action=pystray.Menu(*device_menu_items),
            )
        )

    active_dev = devices.get(active_device_id, {}) if active_device_id else {}
    display_name = active_dev.get('name', mouse_name) or 'N/A'
    display_level = active_dev.get('level', battery_level)
    display_type = active_dev.get('type', 'mouse')
    type_label = f" [{display_type.capitalize()}]"

    menu_items.extend([
        pystray.MenuItem(
            f"{i18n.t('name')}: {display_name}{type_label}",
            lambda: None,
            radio=False,
        ),
        pystray.MenuItem(
            f"{i18n.t('battery')}: {str(f'{display_level}%' if display_level is not None else 'N/A')}",
            lambda: None,
        ),
        pystray.MenuItem(
            f"{i18n.t('remaining_time')}: {remaining_str}",
            lambda: None,
        ),
        pystray.MenuItem(
            (i18n.t("status_charging") if battery_charging else i18n.t("status_discharging")),
            lambda: None,
        ),
        pystray.MenuItem(
            text=i18n.t("last_updated") + ": "
            + (time.strftime("%H:%M:%S", time.localtime(last_update)) if last_update else "N/A")
            + f" ({i18n.t('interval')}: {interval if battery_level is not None else time_error_retry}s)",
            action=pystray.Menu(
                *[
                    pystray.MenuItem(
                        text=f"{int(t / 60)} {i18n.t('minutes')}",
                        action=set_time_delta,
                        checked=lambda t=t: t == cfg.get("time_delta", 300),
                        default=(t == cfg.get("time_delta", 300)),
                        radio=True,
                    )
                    for t in [60, 300, 600, 1800, 3600]
                ],
            ),
        ),
        pystray.MenuItem(
            text=i18n.t("tray_display"),
            action=pystray.Menu(
                pystray.MenuItem(
                    text=i18n.t("hover_display"),
                    action=set_display_mode,
                    checked=lambda *_: cfg.get("display_mode", "hover") == "hover",
                    default=(cfg.get("display_mode", "hover") == "hover"),
                    radio=True,
                ),
                pystray.MenuItem(
                    text=i18n.t("icon_display"),
                    action=set_display_mode,
                    checked=lambda *_: cfg.get("display_mode", "icon") == "icon",
                    default=(cfg.get("display_mode", "hover") == "icon"),
                    radio=True,
                ),
            ),
        ),
        pystray.MenuItem(
            text=i18n.t("language"),
            action=pystray.Menu(
                pystray.MenuItem(
                    text="Türkçe",
                    action=set_language,
                    checked=lambda *_: lang == "tr",
                    default=(lang == "tr"),
                    radio=True,
                ),
                pystray.MenuItem(
                    text="English",
                    action=set_language,
                    checked=lambda *_: lang == "en",
                    default=(lang == "en"),
                    radio=True,
                ),
            ),
        ),
        pystray.MenuItem(
            i18n.t("refresh"),
            refresh_connection,
        ),
        pystray.MenuItem(
            f"API: {i18n.t('on') if api_enabled else i18n.t('off')} (localhost:{cfg.get('api_port', 5000)})",
            toggle_api,
            checked=lambda *_: api_enabled,
        ),
        pystray.MenuItem(
            f"Dashboard: {i18n.t('on') if cfg.get('dashboard_enabled', False) else i18n.t('off')} (steel.local:{cfg.get('dashboard_port', 8080)})",
            toggle_dashboard,
            checked=lambda *_: cfg.get("dashboard_enabled", False),
        ),
        pystray.MenuItem(
            f"MQTT: {i18n.t('on') if mqtt_enabled else i18n.t('off')} ({cfg.get('mqtt_broker', 'localhost')}:{cfg.get('mqtt_port', 1883)})",
            toggle_mqtt,
            checked=lambda *_: mqtt_enabled,
        ),
        pystray.MenuItem(
            f"{i18n.t('auto_start')}: {i18n.t('on') if cfg.get('auto_start', False) else i18n.t('off')}",
            toggle_auto_start,
            checked=lambda *_: cfg.get("auto_start", False),
        ),
        pystray.MenuItem(i18n.t("quit"), quit_app),
    ])

    return pystray.Menu(*menu_items)


def load_image(image_name):
    return Image.open(f"{image_directory}{image_name}.png")


def get_icon_text_font(draw, text):
    digit_count = len(text)
    if digit_count == 1:
        max_font_size = 104
        min_padding = 10
    elif digit_count == 2:
        max_font_size = 76
        min_padding = 6
    else:
        max_font_size = 52
        min_padding = 5

    for font_size in range(max_font_size, 11, -2):
        font = ImageFont.load_default(size=font_size)
        left, top, right, bottom = draw.textbbox(
            (50, 50), text, font=font, anchor="mm"
        )
        if (
            left >= min_padding
            and top >= min_padding
            and right <= 100 - min_padding
            and bottom <= 100 - min_padding
        ):
            return font

    return ImageFont.load_default(size=36)


STEELSERIES_VENDOR_ID = 0x1038

KNOWN_KEYBOARD_PRODUCT_IDS = {
    0x121E, 0x1220, 0x1222, 0x1226, 0x1228,
    0x1237, 0x123A, 0x123B, 0x123C, 0x1240,
    0x1248, 0x124B, 0x124C, 0x1253, 0x125A,
}

KEYBOARD_BATTERY_COMMAND = [0x02, 0x00]
KEYBOARD_BATTERY_RESPONSE_LENGTH = 32


def _is_keyboard_device(vendor_id, product_id):
    if product_id in KNOWN_KEYBOARD_PRODUCT_IDS:
        return True
    if (vendor_id, product_id) in rivalcfg.devices.PROFILES:
        return False
    return False


def _read_keyboard_battery(vendor_id, product_id):
    try:
        device = hid_lib.device()
        for interface in hid_lib.enumerate(vendor_id, product_id):
            try:
                device.open_path(interface["path"])
                device.write(bytearray([0x00] + KEYBOARD_BATTERY_COMMAND))
                data = device.read(KEYBOARD_BATTERY_RESPONSE_LENGTH, timeout_ms=200)
                device.close()
                if data and len(data) >= 3:
                    level = data[1]
                    is_charging = bool(data[2] & 0x01)
                    if 0 <= level <= 100:
                        return {"level": level, "is_charging": is_charging}
            except Exception:
                try:
                    device.close()
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _scan_keyboards():
    found = []
    seen_product_ids = set()
    for dev in hid_lib.enumerate(STEELSERIES_VENDOR_ID):
        pid = dev["product_id"]
        vid = dev["vendor_id"]
        if pid in seen_product_ids:
            continue
        seen_product_ids.add(pid)
        if _is_keyboard_device(vid, pid):
            name = dev.get("product_string", f"SteelSeries Keyboard {pid:04X}")
            battery = _read_keyboard_battery(vid, pid)
            found.append({
                "vendor_id": vid,
                "product_id": pid,
                "name": name,
                "battery": battery,
            })
    return found


def read_raw_battery(device_path, command, read_length=64):
    try:
        dev = hid_lib.device()
        dev.open_path(device_path)
        dev.write(command)
        time.sleep(0.05)
        data = dev.read(read_length, timeout_ms=200)
        dev.close()
        return list(data) if data else []
    except Exception:
        try:
            dev.close()
        except Exception:
            pass
        return []


def get_battery(event: threading.Event):
    global stopped, icon, battery_level, last_update, battery_charging, mock, mouse_name, active_device_id, devices
    mock = cfg.get("mock", False)
    while not stopped:
        try:
            found_devices = []
            if mock:
                found_devices = [
                    {"object": MockMouse("Fatih Gülcü", level=95), "type": "mouse"},
                    {"object": MockMouse("SteelSeries Keyboard", level=80), "type": "keyboard"},
                ]
            else:
                plugged_devices = list(rivalcfg.devices.list_plugged_devices())
                for dev in plugged_devices:
                    try:
                        mouse = rivalcfg.mouse.get_mouse(
                            vendor_id=dev["vendor_id"],
                            product_id=dev["product_id"],
                        )
                        found_devices.append({"object": mouse, "type": "mouse"})
                    except Exception:
                        continue

                for kb in _scan_keyboards():
                    found_devices.append({
                        "object": kb,
                        "type": "keyboard",
                    })

            if not found_devices:
                print("No devices found")
                time.sleep(time_error_retry)
                raise Exception

            new_devices = {}
            for entry in found_devices:
                device_type = entry["type"]
                obj = entry["object"]

                if device_type == "mouse":
                    device_id = f"mouse_{getattr(obj, 'product_id', 0)}_{obj.name}"
                    battery = obj.battery
                    name = obj.name
                    if battery is not None and battery["level"] is not None:
                        level = max(min(battery["level"], 100), 0)
                        is_charging = battery["is_charging"]
                    else:
                        continue
                else:
                    # Keyboard - could be MockMouse (mock mode) or dict (real mode)
                    if isinstance(obj, dict):
                        device_id = f"keyboard_{obj['product_id']}_{obj['name']}"
                        name = obj["name"]
                        battery = obj["battery"]
                    else:
                        # MockMouse in mock mode
                        device_id = f"keyboard_{getattr(obj, 'product_id', 0)}_{obj.name}"
                        name = obj.name
                        battery = obj.battery
                    
                    if battery is not None and battery["level"] is not None:
                        level = max(min(battery["level"], 100), 0)
                        is_charging = battery["is_charging"]
                    else:
                        continue

                new_devices[device_id] = {
                    "name": name,
                    "level": level,
                    "is_charging": is_charging,
                    "type": device_type,
                }
                database.save_battery(device_id, name, level, is_charging)
                alerts.check_battery_level(device_id, name, level, is_charging)

            devices = new_devices

            if active_device_id not in devices:
                active_device_id = next(iter(devices), None)

            if active_device_id and active_device_id in devices:
                active = devices[active_device_id]
                mouse_name = active["name"]
                battery_level = active["level"]
                battery_charging = active["is_charging"]
                last_update = time.time()

                if not battery_charging:
                    estimator.add_sample(battery_level)
                else:
                    estimator.reset()

                mqtt_client.publish_battery_data()

                if icon is not None:
                    icon.icon = create_battery_icon()
                    icon.menu = create_menu()
                    remaining = estimator.get_remaining_seconds()
                    if battery_charging:
                        icon.title = i18n.t("title_charging", battery=battery_level or "N/A")
                    elif remaining is not None:
                        icon.title = i18n.t("title_discharging", battery=battery_level or "N/A", time=i18n.format_remaining_time(remaining))
                    else:
                        icon.title = i18n.t("title_no_data")
                    icon.update_menu()

                interval = cfg.get("time_delta", 300)
                sleeptime = interval if battery_level is not None else time_error_retry
                event.clear()
                event.wait(timeout=sleeptime)
            else:
                print("No battery found")
                time.sleep(time_error_retry)
        except Exception as e:
            print(f"Error: {e}\n\nSleeping for {time_error} seconds...")
            time.sleep(time_error)

    for mouse in mouse_objects.values():
        try:
            mouse.close()
        except Exception:
            pass
    print("Stopping thread")


def create_battery_icon():
    global battery_level, battery_charging, active_device_id, devices
    display_mode = cfg.get("display_mode", "hover")
    image = Image.new("RGB", (100, 100), color="white")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 100, 100), fill="black")
    error = load_image("no_error")

    active_type = devices.get(active_device_id, {}).get("type", "mouse") if active_device_id else "mouse"

    def draw_battery_indicator(color, level):
        draw.rectangle((0, 0, 100, 100), fill="black")
        draw.rectangle((0, 100 - level, 100, 100), fill=color)

    if battery_level is not None:
        if battery_charging:
            color = "orange"
        elif active_type == "keyboard":
            if battery_level < 20:
                color = "red"
            elif battery_level < 50:
                color = "cyan"
            else:
                color = "blue"
        else:
            if battery_level < 20:
                color = "red"
            elif battery_level < 50:
                color = "yellow"
            else:
                color = "green"

        if display_mode == "icon":
            text = str(battery_level)
            font = get_icon_text_font(draw, text)
            draw.text(
                (50, 50),
                text,
                fill=color,
                font=font,
                anchor="mm",
            )
        else:
            draw_battery_indicator(color, battery_level)
    else:
        error = load_image("error")

    image.paste(error, (0, 0), error)

    image = image.convert("RGBA")
    data = image.get_flattened_data()
    if data is None:
        print("No data found in image, returning empty image.")
        return image
    new_data = []
    for item in data:
        if isinstance(item, tuple) and item[0] == 0 and item[1] == 0 and item[2] == 0:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    image.putdata(new_data)

    return image


def refresh_connection():
    global event
    if event is None:
        print("Event is None, cannot refresh connection.")
        return
    event.set()


def set_active_device(icon, item):
    global active_device_id, battery_level, battery_charging, mouse_name, last_update
    for dev_id, dev_data in devices.items():
        if dev_data['name'] in item.text:
            active_device_id = dev_id
            mouse_name = dev_data['name']
            battery_level = dev_data['level']
            battery_charging = dev_data['is_charging']
            last_update = time.time()
            cfg.set("active_device_id", active_device_id)
            if icon is not None:
                icon.icon = create_battery_icon()
                icon.menu = create_menu()
                icon.update_menu()
            if event is not None:
                event.set()
            break


def set_time_delta(icon, item):
    global event
    if event is None:
        return
    new_time_delta = int(item.text.split(" ")[0]) * 60
    cfg.set("time_delta", new_time_delta)
    event.set()


def set_display_mode(icon, item):
    mode = "icon" if item.text == i18n.t("icon_display") else "hover"
    cfg.set("display_mode", mode)
    if icon is not None:
        icon.icon = create_battery_icon()
        icon.menu = create_menu()
        icon.update_menu()
    if event is not None:
        event.set()


def set_language(icon, item):
    if item.text == "Türkçe":
        i18n.set_lang("tr")
    else:
        i18n.set_lang("en")
    if icon is not None:
        icon.icon = create_battery_icon()
        icon.menu = create_menu()
        icon.update_menu()
    if event is not None:
        event.set()


def toggle_api(icon, item):
    enabled = not cfg.get("api_enabled", False)
    cfg.set("api_enabled", enabled)
    if enabled:
        start_web_api()
    if icon is not None:
        icon.menu = create_menu()
        icon.update_menu()


def toggle_mqtt(icon, item):
    enabled = not cfg.get("mqtt_enabled", False)
    cfg.set("mqtt_enabled", enabled)
    if enabled:
        start_mqtt_client()
    else:
        mqtt_client.stop_mqtt()
    if icon is not None:
        icon.menu = create_menu()
        icon.update_menu()


def toggle_auto_start(icon, item):
    new_state = auto_start.toggle()
    cfg.set("auto_start", new_state)
    if icon is not None:
        icon.menu = create_menu()
        icon.update_menu()


def toggle_dashboard(icon, item):
    enabled = not cfg.get("dashboard_enabled", False)
    cfg.set("dashboard_enabled", enabled)
    if enabled:
        start_dashboard()
    if icon is not None:
        icon.menu = create_menu()
        icon.update_menu()


def quit_app(icon, item):
    global stopped
    mqtt_client.stop_mqtt()
    icon.stop()
    stopped = True


def get_battery_data():
    remaining = estimator.get_remaining_seconds()
    return {
        "level": battery_level,
        "is_charging": battery_charging,
        "remaining_time": remaining,
        "remaining_time_str": i18n.format_remaining_time(remaining),
        "last_update": last_update,
        "name": mouse_name,
    }


def get_settings():
    return {
        "time_delta": cfg.get("time_delta", 300),
        "display_mode": cfg.get("display_mode", "hover"),
        "language": cfg.get("language", "tr"),
        "api_port": cfg.get("api_port", 5000),
        "api_enabled": cfg.get("api_enabled", False),
        "design_capacity": cfg.get("design_capacity", 250),
    }


def update_settings(data):
    allowed = ["time_delta", "display_mode", "language", "design_capacity"]
    updated = {}
    for key in allowed:
        if key in data:
            cfg.set(key, data[key])
            updated[key] = data[key]
    if "language" in data:
        i18n.set_lang(data["language"])
    if event is not None:
        event.set()
    return {"updated": updated, "settings": get_settings()}


def get_devices():
    result = []
    for dev_id, dev_data in devices.items():
        remaining = None
        if dev_id == active_device_id:
            remaining = estimator.get_remaining_seconds()
        result.append({
            "id": dev_id,
            "name": dev_data["name"],
            "battery_level": dev_data["level"],
            "is_charging": dev_data["is_charging"],
            "type": dev_data["type"],
            "remaining_time": remaining,
            "remaining_time_str": i18n.format_remaining_time(remaining),
            "is_active": dev_id == active_device_id,
        })
    return {"devices": result}


def start_web_api():
    from api_server import init_api, start_api_server
    port = cfg.get("api_port", 5000)
    init_api(get_battery_data, get_settings, update_settings, refresh_connection, get_devices)
    start_api_server(port)


def start_dashboard():
    import hosts_manager
    hosts_manager.add_domain()
    from web_dashboard import init_dashboard, start_dashboard as _start
    port = cfg.get("dashboard_port", 8080)
    init_dashboard(get_battery_data, get_settings, update_settings, get_devices)
    _start(port)


def start_mqtt_client():
    mqtt_config = {
        "mqtt_broker": cfg.get("mqtt_broker", "localhost"),
        "mqtt_port": cfg.get("mqtt_port", 1883),
        "mqtt_topic_prefix": cfg.get("mqtt_topic_prefix", "steelmouse"),
        "mqtt_username": cfg.get("mqtt_username", ""),
        "mqtt_password": cfg.get("mqtt_password", ""),
        "mqtt_discovery": cfg.get("mqtt_discovery", True),
    }
    mqtt_client.init_mqtt(get_battery_data, mqtt_config)
    mqtt_client.start_mqtt()


def main():
    global icon, event, image

    load_config()
    cfg.set("auto_start", auto_start.is_enabled())
    database.init_db()
    event = threading.Event()
    image = create_battery_icon()
    icon = pystray.Icon("Battery", icon=image, title=i18n.t("title_no_data"))
    thread = threading.Thread(target=get_battery, args=(event,))
    thread.daemon = True
    thread.start()
    icon.menu = pystray.Menu(
        pystray.MenuItem(
            i18n.t("looking_for_mouse"),
            lambda: None,
        ),
        pystray.MenuItem(i18n.t("quit"), quit_app),
    )

    if cfg.get("api_enabled", False):
        start_web_api()

    if cfg.get("dashboard_enabled", False):
        start_dashboard()

    if cfg.get("mqtt_enabled", False):
        start_mqtt_client()

    icon.run()


if __name__ == "__main__":
    main()
