# Improvement Backlog

Findings from a code review of SteelMouse v2.6.1 (static read, nothing was changed or run). Priorities: **H** high, **M** medium, **L** low.

## Bugs / Correctness

- [ ] **(H) Log file is never rotated and the timestamp is UTC `HH:MM:SS` only** ([log.rs](src/log.rs)). It is opened in append mode and grows without limit. `log::log` also runs on every poll and tray event. Add size-based rotation and a full local date and time (`chrono` is already a dependency), and gate verbose lines behind a debug flag.
- [ ] **(H) Log lives next to the exe** ([log.rs](src/log.rs)). This fails for read-only installs such as `Program Files` and macOS app bundles. Use `ProjectDirs` (as `config.rs` does) for the log path.
- [ ] **(M) Error-retry interval is hard-coded to 12s** ([gui.rs](src/gui.rs)). When the mouse is asleep or unplugged the app polls forever at that rate. Use exponential backoff (12s → 30s → 60s, capped at the user interval).
- [ ] **(M) Poll-loop wake logic is clunky** ([gui.rs](src/gui.rs)). It ticks every 1s and takes the config mutex twice per tick. A single `recv_timeout(sleep_secs)` that is re-evaluated on a config-change message would be simpler and cheaper. It would also fix the case where the interval is lowered mid-wait.
- [ ] **(M) Autostart toggle ignores errors** ([gui.rs](src/gui.rs)). `set_autostart` is called with `let _ =`, and the checkbox is flipped regardless of the result. Only update the check state on success, and log or show the failure.
- [ ] **(M) macOS autostart plist is named `com.steelmouse.plist`** ([autostart.rs](src/autostart.rs)). The config uses the `de.yurtemre` identifier. Make the bundle ID consistent, and check that the plist path escapes spaces in the exe path.
- [ ] **(M) Config load silently falls back to defaults on a parse error** ([config.rs](src/config.rs)), and `save` swallows I/O errors. Log both, and write atomically (temp file + rename). Also validate `time_delta` to a sane minimum, since a hand-edited `0` would cause a busy loop.
- [ ] **(L) `process::exit(0)` on Quit and Ctrl+C** ([gui.rs](src/gui.rs), [main.rs](src/main.rs)). The tray icon is not dropped, so on Windows a ghost icon can linger until hover. Remove the tray icon and set `ControlFlow::Exit` instead.
- [ ] **(L) `.unwrap()` on `menu.append`, mutex locks, and `self.api.as_mut()`** ([menu.rs](src/menu.rs), [gui.rs](src/gui.rs), [hid.rs](src/protocol/hid.rs)). With `panic = "abort"` in release, any of these kills the tray silently. Handle poisoned locks and `Result`s.

## Performance / Resources

- [ ] **(M) The tao event loop wakes every 100ms** ([gui.rs](src/gui.rs)) just to poll channels. Use `ControlFlow::Wait` with `EventLoopProxy` user events from the HID thread and menu handler, which brings idle CPU to about 0.
- [ ] **(L) Tray icon is re-rendered and set on every poll**, even when nothing changed. Skip `set_icon` and `set_tooltip` when level, charging state, and mode are unchanged.
- [ ] **(L) `eframe`/`egui` are linked into the tray binary** ([Cargo.toml](Cargo.toml)) just for the analyzer window. This hurts startup time and binary size despite `opt-level = "z"`. Consider a cargo feature (`analyzer`, default on) or a separate binary.

## UX

- [ ] **(M) Tooltip is minimal** ("Battery: 42%" / "N/A"). Include the device name, charging state, and last-updated time. Show a distinct "mouse asleep / dongle not found" state instead of generic N/A.
- [ ] **(M) Low-battery notification.** Add a configurable threshold (for example 20% and 10%) with a native notification, firing once per discharge cycle.
- [ ] **(M) Multiple devices.** Only a single mouse is tracked. Allow selecting among connected SteelSeries devices, or showing all of them in the menu.
- [ ] **(L) Charging icon and battery colour** (red below 20%, green when charging) in Icon mode, if not already done in [icon.rs](src/icon.rs). Also check HiDPI and dark/light menu bar contrast.
- [ ] **(L) Linux support.** `autostart.rs` has a no-op `not(windows/macos)` branch and `is_autostart_enabled` always returns false. Either add an XDG autostart `.desktop` entry or state "unsupported" in the readme.
- [ ] **(L) Show the app version in the tray menu.** The version string in [main.rs](src/main.rs) is hard-coded ("v2.6.1"). Use `env!("CARGO_PKG_VERSION")` so it can't drift from Cargo.toml.

## Code Quality / Architecture

- [ ] **(M) [main.rs](src/main.rs) is 244 lines, mostly an inlined `--record-fixture` implementation.** Move it into `protocol::recorder` (or a `cli` module). The same is probably true of the `--dump-hid` handling.
- [ ] **(M) Duplicated HID probe and retry loops** (the 50ms sleep and attempt loop appears in [hid.rs](src/protocol/hid.rs), [recorder.rs](src/protocol/recorder.rs), and [main.rs](src/main.rs)). Extract a shared helper.
- [ ] **(L) Thin re-export shims** ([hid.rs](src/hid.rs), [devices.rs](src/devices.rs)) with `#[allow(unused_imports)]`. Remove them and import from `protocol::` directly.
- [ ] **(L) Replace `println!` logging and the hand-rolled logger** with the `log` + `env_logger`/`fern` or `tracing` crate, with levels.
- [ ] **(L) `rivalcfg_devices.json` and the hand-written `protocol/devices.rs` (653 lines) overlap.** Document how they relate, or generate one from the other. Make adding a new mouse a data-only change.
- [ ] **(L) Clap `-r`, `-b`, `-a` short flags are cryptic and `Option<Option<PathBuf>>` is awkward.** Consider subcommands (`steelmouse record`, `analyze`, `dump-hid`).

## Testing / CI

- [ ] **(M) Only 23 tests, and mostly protocol/fixture parsing.** Add tests for config load/save and defaults, interval/backoff logic, and menu-state updates (extract pure functions to make them testable).
- [ ] **(M) CI runs `cargo test` only inside the release jobs (Windows).** Add a PR/push job on Linux/macOS/Windows running `cargo fmt --check`, `cargo clippy -- -D warnings`, and `cargo test`. Today, tests only run when a release is triggered.
- [ ] **(L) Pin or review the Actions versions** (`checkout@v7`, `upload-artifact@v7`, `download-artifact@v8`, `action-gh-release@v3`) against what actually exists. Also don't interpolate `github.event.head_commit.message` directly into a shell script (injection risk). Pass it via `env:`.
- [ ] **(L) macOS release is an unsigned bare binary.** Ship a signed and notarized `.app` bundle or dmg (also needed for a proper Info.plist with `LSUIElement`). Consider code-signing the Windows installer too.
- [ ] **(L) Dependabot or `cargo audit`** for dependency updates.

## Docs / Repo Hygiene

- [ ] **(M) [knownissues.md](knownissues.md) is stale.** It describes a Python `pillow` error from the old Python implementation. Replace it with current Rust-app issues (for example HID permission on macOS, dongle not detected, N/A battery).
- [ ] **(L) `time_delta.txt` is committed in the repo root** even though it is in `.gitignore` (legacy state file). Remove it from git (`git rm --cached`). Also drop the stale Python entries in `.gitignore`.
- [ ] **(L) [CHANGELOG.md](CHANGELOG.md) and [RELEASE_NOTES.md](RELEASE_NOTES.md) are both generated** by `scripts/generate_changelog.py`. Commit only one, or ignore the generated one.
- [ ] **(L) Add a "supported devices" table and a "my mouse isn't supported" guide** to the readme, linking to the `--analyze` flow.
- [ ] **(L) Add `rust-version` (MSRV) and `repository`/`license` fields to [Cargo.toml](Cargo.toml).** The `authors` value is a placeholder.
