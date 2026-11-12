# Known Issues & Troubleshooting

Common troubleshooting solutions for **SteelMouse (Rust)**:

---

### 1. Battery Percentage Always Shows "N/A"

**Cause:**
The mouse is asleep, powered off, out of wireless range, in Bluetooth mode, or the 2.4 GHz USB wireless receiver has lost its HID session.

**Solutions:**
- **Move or click the mouse** to ensure it is awake and communicating.
- **Unplug and replug the 2.4 GHz USB wireless dongle** from your computer. USB HID device sessions can become stale after system sleep, lock screen, or hibernation.
- **Check wireless mode switch:** Ensure the physical switch on the underside of your mouse is set to **2.4 GHz** mode. Standard Bluetooth connections do not expose SteelSeries proprietary USB HID battery telemetry.
- **Trigger a manual refresh:** Right-click the SteelMouse tray icon and click **Refresh Now**.

---

### 2. macOS: Mouse Not Detected or Permission Denied (Input Monitoring)

**Cause:**
Starting with macOS Catalina (10.15) and newer (macOS Sonoma, Sequoia, etc.), reading raw USB HID events and reports requires **Input Monitoring** permissions.

**Solutions:**
1. Open **System Settings** (or **System Preferences**).
2. Go to **Privacy & Security** → **Input Monitoring**.
3. Locate **SteelMouse** (or your terminal application if running from CLI) and toggle the permission **ON**.
4. If SteelMouse was already toggled ON, toggle it **OFF** and then back **ON**, then relaunch the application.
5. If prompted by macOS for **Accessibility** permissions, allow it under **Privacy & Security** → **Accessibility** as well.

---

### 3. Mouse Not Detected or Unsupported Mouse Model

**Cause:**
Your SteelSeries mouse model, edition, or firmware version uses a USB Product ID (PID) or HID report packet structure not yet registered in SteelMouse's device database.

**Solutions:**
- Use the built-in **Mouse Analyzer & Config Generator**:
  - Right-click the tray icon and select **`🔍 Analyze / Report Unsupported Mouse...`**, or run from your terminal:
    ```bash
    steelmouse --analyze
    ```
  - Enter the battery percentage currently displayed in SteelSeries GG so the analyzer can automatically identify the matching response byte and scale factor.
  - Click **`🔍 Scan & Analyze Mouse`** to inspect all connected HID interfaces.
  - Click the generated GitHub issue link to submit an issue with pre-filled profile information, or attach the generated `steelmouse_diagnostic_*.json` file.
- Alternatively, record diagnostic data via the command line:
  ```bash
  steelmouse --record --battery 85
  ```
- Submit an issue at [https://github.com/yurtemre7/steel-mouse/issues](https://github.com/yurtemre7/steel-mouse/issues).
