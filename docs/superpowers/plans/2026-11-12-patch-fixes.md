# Patch-release fixes (v2.6.2) Implementation Plan

**Source:** `IMPROVEMENTS.md` (repo root). **Branch:** `patch-improvements`.

## Global Constraints
- PATCH release only: NO breaking changes. Do not change CLI flags, config.json schema/field names, menu items' meaning, or public APIs in `src/protocol`. Existing config.json files must still load.
- No new features (no notifications, multi-device, subcommands). No new dependencies.
- Must compile on Windows and macOS: wrap platform code in `#[cfg]`; you can only build on macOS here.
- `cargo build` and `cargo test` must pass at the end of each task. Preserve existing comments/docstrings unrelated to your change.
- Do NOT run `git commit` or any git write command (the sandbox forbids it); the controller commits. Do not dispatch subagents.

## Task 1: Logging (src/log.rs)
Files: `src/log.rs`
- Timestamp: local date+time `YYYY-MM-DD HH:MM:SS` via `chrono::Local` (replace the hand-rolled UTC `chrono_now`).
- Log path: `directories::ProjectDirs::from("de","yurtemre","SteelMouse")` data_local_dir/`steelmouse.log` (create dir); fall back to the exe directory, then `steelmouse.log`.
- Rotation at `init()`: if the existing log is > 1 MiB, rename it to `steelmouse.log.1` (overwriting any old one) before opening.
- Add unit tests for a pure helper (e.g. timestamp format shape, rotate-if-large helper using a temp dir under `std::env::temp_dir()`).
- Keep `log::init()` and `log::log(&str)` signatures unchanged.

## Task 2: Tray app robustness (src/gui.rs, src/main.rs, src/config.rs)
Files: `src/gui.rs`, `src/main.rs`, `src/config.rs`
- Autostart toggle: only call `set_checked(target_state)` if `set_autostart` returns Ok; on Err log it and leave checkbox unchanged.
- Error retry: replace hard-coded 12s with backoff 12s → 30s → 60s (cap 60s, and never above the user's `time_delta` if that is smaller than 60... keep simple: `min(backoff, 60)`); reset on success. Extract a pure function `next_error_delay(consecutive_failures: u32) -> u64` and unit test it.
- Skip `tray.set_icon`/`set_tooltip` when level, charging, and display mode are unchanged from the previous update.
- Quit/Ctrl+C: keep behavior (exit 0) but drop the tray icon first on Quit (`tray_icon.take()`) so Windows leaves no ghost icon.
- Replace hard-coded "v2.6.1" string in `main.rs` log line with `env!("CARGO_PKG_VERSION")`.
- config.rs: clamp loaded `time_delta` to a minimum of 5 seconds (prevent busy-loop from `0`); log parse errors; save atomically (write `config.json.tmp`, then rename). Unit tests for the clamp (pure fn). Field names/serde format unchanged.

## Task 3: Autostart & unwrap hardening (src/autostart.rs, src/menu.rs)
Files: `src/autostart.rs`, `src/menu.rs`
- macOS plist: XML-escape the exe path (`&`,`<`,`>`) when written into the plist; keep file name `com.steelmouse.plist` and Label unchanged (renaming would orphan existing installs). Extract a pure `plist_content(exe: &str) -> String` and unit test escaping.
- Propagate `create_dir_all` and plist-removal errors in `set_autostart` instead of ignoring them (macOS).
- menu.rs: replace `.unwrap()` on `menu.append`/`submenu.append` with logged-and-ignored errors (`if let Err(e) = ... { log::log(...) }`) so a menu failure doesn't abort the process.

## Task 4: CI, docs, repo hygiene
Files: `.github/workflows/build.yml`, `knownissues.md`, `.gitignore`, `Cargo.toml`, `time_delta.txt`
- Add a `test` job (on push to main and pull_request, matrix ubuntu/macos/windows) running `cargo fmt --check` is NOT required (repo may be unformatted); run `cargo build` and `cargo test` only. On ubuntu install `libudev-dev libusb-1.0-0-dev` if needed for hidapi; if unsure, run only on macos+windows. Add `pull_request:` trigger without breaking existing release job conditions.
- In the release job, pass `github.event.head_commit.message` via `env:` (e.g. `RAW_MSG: ${{ github.event.head_commit.message }}`) instead of interpolating it in the shell script.
- Rewrite `knownissues.md` for the Rust app (battery N/A: replug dongle; macOS permissions/Input Monitoring; mouse not detected → run `steelmouse --analyze`). Remove Python issues.
- `.gitignore`: remove stale Python/PyInstaller entries (keep `target/`, Inno Setup, runtime state files, OS/IDE). Add `.superpowers/`.
- Delete `time_delta.txt` from the working tree (controller will `git rm`).
- Cargo.toml: add `repository`-free metadata only if known; otherwise just add `license = "MIT"` ONLY if LICENSE file is MIT; bump `version` to `2.6.2` and update `Cargo.lock` via `cargo build`. Also update any other place that hard-codes the version (grep `2.6.1`, e.g. innosetup/setup_rust.iss, readme badges) to `2.6.2`.
