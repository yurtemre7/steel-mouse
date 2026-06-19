from config import get, set as cfg_set

TRANSLATIONS = {
    "tr": {
        "battery": "Batarya",
        "status_charging": "Durum: Şarj Oluyor",
        "status_discharging": "Durum: Şarj Oluyor Değil",
        "last_updated": "Son Güncelleme",
        "interval": "Aralık",
        "tray_display": "Sistem Tepsisi Gösterimi",
        "hover_display": "Üzerine gelince yüzdeyi göster",
        "icon_display": "Yüzdeyi simgede göster",
        "quit": "Çıkış",
        "looking_for_mouse": "Fare aranıyor...",
        "remaining_time": "Kalan Süre",
        "remaining_time_value": "{hours} saat {minutes} dakika",
        "remaining_time_minutes": "{minutes} dakika",
        "remaining_time_seconds": "{seconds} saniye",
        "no_data": "Veri yok",
        "language": "Dil",
        "refresh": "Yenile",
        "name": "İsim",
        "minutes": "dakika",
        "hours": "saat",
        "seconds": "saniye",
        "api_enabled": "API Açık",
        "api_disabled": "API Kapalı",
        "settings": "Ayarlar",
        "device_list": "Cihaz Listesi",
        "select_device": "Cihaz Seç",
        "all_devices": "Tüm Cihazlar",
        "no_devices": "Cihaz bulunamadı",
        "device_count": "{count} cihaz bağlı",
        "tooltip_charging": "{battery}% - Şarj Oluyor",
        "tooltip_discharging": "{battery}% - {time} kaldı",
        "tooltip_no_time": "{battery}% - Veri yok",
        "title_charging": "Batarya: {battery}% - Şarj Oluyor",
        "title_discharging": "Batarya: {battery}% - {time}",
        "title_no_data": "Batarya: N/A",
        "on": "Açık",
        "off": "Kapalı",
    },
    "en": {
        "battery": "Battery",
        "status_charging": "Status: Charging",
        "status_discharging": "Status: Discharging",
        "last_updated": "Last Updated",
        "interval": "Interval",
        "tray_display": "Tray Battery Display",
        "hover_display": "Hover for percentage",
        "icon_display": "Show percentage on icon",
        "quit": "Quit",
        "looking_for_mouse": "Looking for mouse and mouse data...",
        "remaining_time": "Remaining Time",
        "remaining_time_value": "{hours}h {minutes}m",
        "remaining_time_minutes": "{minutes}m",
        "remaining_time_seconds": "{seconds}s",
        "no_data": "No data",
        "language": "Language",
        "refresh": "Refresh",
        "name": "Name",
        "minutes": "min",
        "hours": "h",
        "seconds": "s",
        "api_enabled": "API Enabled",
        "api_disabled": "API Disabled",
        "settings": "Settings",
        "device_list": "Device List",
        "select_device": "Select Device",
        "all_devices": "All Devices",
        "no_devices": "No devices found",
        "device_count": "{count} devices connected",
        "tooltip_charging": "{battery}% - Charging",
        "tooltip_discharging": "{battery}% - {time} remaining",
        "tooltip_no_time": "{battery}% - No data",
        "title_charging": "Battery: {battery}% - Charging",
        "title_discharging": "Battery: {battery}% - {time}",
        "title_no_data": "Battery: N/A",
        "on": "On",
        "off": "Off",
    },
}

_current_lang = None


def get_lang():
    global _current_lang
    if _current_lang is None:
        _current_lang = get("language", "tr")
    return _current_lang


def set_lang(lang):
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang
        cfg_set("language", lang)


def t(key, **kwargs):
    lang = get_lang()
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def format_remaining_time(seconds):
    if seconds is None:
        return t("no_data")
    if seconds < 60:
        return t("remaining_time_seconds", seconds=seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return t("remaining_time_value", hours=hours, minutes=minutes)
    return t("remaining_time_minutes", minutes=minutes)
