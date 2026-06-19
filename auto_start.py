import sys
import os
import winreg

APP_NAME = "SteelMouse"

_startup_folder = os.path.join(
    os.environ.get("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup",
)
_startup_link = os.path.join(_startup_folder, f"{APP_NAME}.vbs")


def _is_frozen():
    return getattr(sys, "frozen", False)


def _get_exe_path():
    return sys.executable if _is_frozen() else os.path.abspath(__file__)


def _get_startup_vbs_content():
    exe = _get_exe_path()
    if _is_frozen():
        return f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{exe}""", 0, False\n'
    else:
        return f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{sys.executable}"" ""{exe}""", 0, False\n'


def is_enabled():
    if _is_frozen():
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ,
            )
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False
    else:
        return os.path.exists(_startup_link)


def enable():
    if _is_frozen():
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
        winreg.CloseKey(key)
    else:
        with open(_startup_link, "w", encoding="utf-8") as f:
            f.write(_get_startup_vbs_content())


def disable():
    if _is_frozen():
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
    else:
        if os.path.exists(_startup_link):
            os.remove(_startup_link)


def toggle():
    if is_enabled():
        disable()
        return False
    else:
        enable()
        return True
