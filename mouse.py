import rivalcfg, pystray, os, time, threading
from PIL import Image, ImageDraw, ImageFont
from mock_mouse import MockMouse
from battery_estimator import BatteryEstimator
import i18n
import config as cfg
import mqtt_client

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

    return pystray.Menu(
        pystray.MenuItem(
            f"{i18n.t('name')}: {mouse_name or 'N/A'}",
            lambda: None,
            radio=False,
        ),
        pystray.MenuItem(
            f"{i18n.t('battery')}: {str(f'{battery_level}%' if battery_level is not None else 'N/A')}",
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
            f"MQTT: {i18n.t('on') if mqtt_enabled else i18n.t('off')} ({cfg.get('mqtt_broker', 'localhost')}:{cfg.get('mqtt_port', 1883)})",
            toggle_mqtt,
            checked=lambda *_: mqtt_enabled,
        ),
        pystray.MenuItem(i18n.t("quit"), quit_app),
    )


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


def get_battery(event: threading.Event):
    global stopped, icon, battery_level, last_update, battery_charging, mock, mouse_name
    mock = cfg.get("mock", False)
    mouse = None
    while not stopped:
        try:
            if mock:
                mouse = MockMouse("Fatih Gülcü", level=95)
            else:
                mouse = rivalcfg.get_first_mouse()
            print(f"Mouse found {mouse}")
            if mouse is None:
                print("No mouse found")
                time.sleep(time_error_retry)
                raise Exception

            battery = mouse.battery
            print(f"Mouse battery {battery}")

            if battery is not None:
                mouse_name = mouse.name
                if battery["level"] is not None:
                    battery_level = max(min(battery["level"], 100), 0)
                    last_update = time.time()
                    battery_charging = battery["is_charging"]

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
                sleeptime = (
                    interval if battery["level"] is not None else time_error_retry
                )
                event.clear()
                event.wait(timeout=sleeptime)
            else:
                print("No battery found")
                time.sleep(time_error_retry)
        except Exception as e:
            print(f"Error: {e}\n\nSleeping for {time_error} seconds...")
            time.sleep(time_error)

    if mouse is not None:
        mouse.close()
    print("Stopping thread")


def create_battery_icon():
    global battery_level, battery_charging
    display_mode = cfg.get("display_mode", "hover")
    image = Image.new("RGB", (100, 100), color="white")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 100, 100), fill="black")
    error = load_image("no_error")

    def draw_battery_indicator(color, level):
        draw.rectangle((0, 0, 100, 100), fill="black")
        draw.rectangle((0, 100 - level, 100, 100), fill=color)

    if battery_level is not None:
        if battery_charging:
            color = "orange"
        elif battery_level < 20:
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
    }


def update_settings(data):
    allowed = ["time_delta", "display_mode", "language"]
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
    devices = []
    if mouse_name is not None:
        remaining = estimator.get_remaining_seconds()
        devices.append({
            "name": mouse_name,
            "battery_level": battery_level,
            "is_charging": battery_charging,
            "remaining_time": remaining,
        })
    return {"devices": devices}


def start_web_api():
    from api_server import init_api, start_api_server
    port = cfg.get("api_port", 5000)
    init_api(get_battery_data, get_settings, update_settings, refresh_connection, get_devices)
    start_api_server(port)


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

    if cfg.get("mqtt_enabled", False):
        start_mqtt_client()

    icon.run()


if __name__ == "__main__":
    main()
