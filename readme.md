# SteelMouse ⚡

**SteelMouse** is a lightweight, native system tray application for **Windows** and **macOS** that queries your wireless SteelSeries gaming mouse directly over USB HID and displays its live battery level and charging status in your taskbar or menu bar—without needing SteelSeries GG running in the background.

![System Tray Image of SteelMouse](assets/image.png)

## 🌟 Key Features

- **⚡ Native & Ultra-Lightweight**: Written in **Rust** (~2.1 MB standalone executable, <10 MB RAM, <10 ms startup time).
- **🖥️ Cross-Platform**: Supports **Windows** (Win32 System Tray) and **macOS** (Apple Silicon & Intel Menu Bar).
- **🎨 Dual Tray Display Modes**:
  - **Hover Tooltip Mode**: Clean color-coded battery fill icon in the tray with percentage shown on hover.
  - **Percentage Number Mode**: Renders the live battery percentage number directly onto the tray icon.
- **🔄 Configurable Polling & Autostart**: Choose background refresh intervals (`1 min`, `5 min`, `10 min`, `30 min`, `1 hr`), trigger instant manual refreshes, and toggle **Start Automatically on Login** directly from the tray menu.
- **🔍 Built-In Mouse Analyzer & Issue Generator**: Includes an interactive analyzer tool (`🔍 Analyze / Report Unsupported Mouse...` in the tray menu or `steelmouse --analyze`) that scans SteelSeries USB HID interfaces, matches responses against your current battery percentage, generates a ready-to-paste `MouseProfile` config, and provides a pre-filled GitHub issue link.

---

## 💻 Supported Wireless Mice

SteelMouse includes protocol profiles and USB HID decoders for 75+ SteelSeries device IDs, including:

- **SteelSeries Aerox 3 Wireless** (Gen 1, Gen 2, & CS2 Dragon Lore Edition — Wired & 2.4 GHz modes)
- **SteelSeries Aerox 5 Wireless** (Standard, Destiny 2, & Diablo IV Editions — Wired & 2.4 GHz modes)
- **SteelSeries Aerox 9 Wireless** (Standard & WoW Editions — Wired & 2.4 GHz modes)
- **SteelSeries Prime Wireless & Prime Mini Wireless** (Wired & 2.4 GHz modes)
- **SteelSeries Rival 3 Wireless** (Gen 1 & Gen 2 — 2.4 GHz mode)
- **SteelSeries Rival 650 Wireless** (Wired & 2.4 GHz modes)
- **SteelSeries Rival Pro** (UWB Wireless Receiver)

---

## 🚀 Installation

### Windows
1. Download the latest installer `SteelMouse_Rust_Setup.exe` (or the portable `steelmouse-windows-x64.zip`) from the [Releases](https://github.com/yurtemre7/steel-mouse/releases/) page.
2. Run the installer. It installs SteelMouse in user space (no administrator prompt required) and can optionally add a Startup shortcut.

### macOS (Apple Silicon & Intel)
1. Download `steelmouse-macos-arm64` (Apple Silicon M1–M4) or `steelmouse-macos-x64` (Intel Mac) from [Releases](https://github.com/yurtemre7/steel-mouse/releases/).
2. Make the binary executable and launch it:
   ```bash
   chmod +x steelmouse-macos-arm64
   ./steelmouse-macos-arm64
   ```

---

## 🔍 Adding or Reporting a New Mouse

If your SteelSeries wireless mouse is not yet supported or reports an inaccurate percentage:

1. Right-click the SteelMouse tray icon and click **`🔍 Analyze / Report Unsupported Mouse...`** (or run `steelmouse --analyze`).
2. *(Optional)* Enter the battery percentage currently displayed in **SteelSeries GG** (`0–100`) so the analyzer can pinpoint the exact response byte and scaling formula.
3. Click **`🔍 Scan & Analyze Mouse`**.
4. Click the generated **`https://github.com/yurtemre7/steel-mouse/issues/new`** link to open a pre-filled GitHub issue in your browser (or copy the generated Markdown report / attach the exported `steelmouse_diagnostic_*.json` file).

---

## 🛠️ Building from Source & CLI Options

Requires the [Rust toolchain](https://rustup.rs/):

```bash
# Clone the repository
git clone https://github.com/yurtemre7/steel-mouse.git
cd steel-mouse

# Run the unit and hardware fixture test suite
cargo test

# Run in mock mouse mode (for UI testing without hardware)
cargo run -- --mock

# Launch the interactive Mouse Analyzer & Issue Generator window
cargo run -- --analyze

# Record a JSON diagnostic report from the command line
cargo run -- --record --battery 85

# Build production release binary
cargo build --release
```

---

## 🤝 Acknowledgements

- [DeveloperX19](https://github.com/DeveloperX19) for the icon art license.
- [flozz](https://github.com/flozz) for [`rivalcfg`](https://github.com/flozz/rivalcfg) and reverse-engineered SteelSeries USB HID protocols.
- [Pyenb](https://github.com/Pyenb), [T-solidus-T](https://github.com/T-solidus-T), and [bossman90](https://github.com/bossman90) for early contributions to the project.

## 📄 License

MIT: Feel free to use this code as you wish. Mentioning the project is appreciated!
