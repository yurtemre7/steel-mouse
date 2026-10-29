# Building SteelMouse and Installer

This document provides instructions on how to build the native Rust executable and Windows installer for **SteelMouse**.

## 1. Building the Standalone Executable

Ensure you have the [Rust toolchain](https://rustup.rs/) installed, then run:

```bash
cargo build --release
```

The standalone release binary will be produced at `target/release/steelmouse.exe` (Windows) or `target/release/steelmouse` (macOS).

## 2. Creating a Windows Installer with Inno Setup

1. **Download and Install Inno Setup**: Download Inno Setup from the [official website](https://jrsoftware.org/isdl.php).
2. **Compile the Script**: Open `innosetup/setup_rust.iss` in Inno Setup (or run `ISCC.exe innosetup\setup_rust.iss`).
3. The installer `SteelMouse_Rust_Setup.exe` will be generated inside the `innosetup/` folder.

## 3. CI / GitHub Actions

The repository includes a GitHub Actions workflow (`.github/workflows/build.yml`) that runs `cargo test`, builds release binaries for Windows (`x86_64-pc-windows-msvc`) and macOS (`aarch64-apple-darwin` & `x86_64-apple-darwin`), compiles the Inno Setup installer, and publishes the release artifacts.
