use chrono::Local;
use std::sync::mpsc::channel;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tao::event_loop::{ControlFlow, EventLoopBuilder};
use tray_icon::TrayIconBuilder;
use muda::MenuEvent;

use crate::config::{AppConfig, DisplayMode};
use crate::hid::{BatteryInfo, MouseManager};
use crate::icon::create_tray_icon;
use crate::log;
use crate::menu::TrayMenu;

enum AppMessage {
    BatteryUpdated(Result<BatteryInfo, String>, String),
}

enum HidCommand {
    Wake,
    ReleaseDevice,
}

/// Calculate next error retry delay based on consecutive failures (12s -> 30s -> 60s cap).
pub fn next_error_delay(consecutive_failures: u32) -> u64 {
    match consecutive_failures {
        0 | 1 => 12,
        2 => 30,
        _ => 60,
    }
}

/// Check if tray icon or tooltip needs updating based on previous and current states.
pub fn should_update_tray_icon(
    last_state: Option<(Option<u8>, bool, DisplayMode)>,
    current_state: (Option<u8>, bool, DisplayMode),
) -> bool {
    last_state != Some(current_state)
}

#[cfg(target_os = "macos")]
fn set_macos_activation_policy(accessory: bool) {
    if let Some(mtm) = objc2_foundation::MainThreadMarker::new() {
        use objc2::ClassType;
        use objc2_app_kit::{NSApplication, NSApplicationActivationPolicy, NSImage};
        use objc2_foundation::NSData;

        let app = NSApplication::sharedApplication(mtm);
        let policy = if accessory {
            NSApplicationActivationPolicy::Accessory
        } else {
            NSApplicationActivationPolicy::Regular
        };
        let _ = app.setActivationPolicy(policy);

        let icon_bytes = include_bytes!("../assets/logo.png");
        let ns_data = NSData::with_bytes(icon_bytes);
        if let Some(ns_image) = NSImage::initWithData(NSImage::alloc(), &ns_data) {
            unsafe {
                app.setApplicationIconImage(Some(&ns_image));
            }
        }
    }
}

pub fn run_tray_app(mock_mode: bool) {
    log::log("run_tray_app: starting native tao event loop");

    #[cfg(target_os = "macos")]
    set_macos_activation_policy(true);

    let event_loop = EventLoopBuilder::new().build();

    let config = AppConfig::load();
    let current_config = Arc::new(Mutex::new(config.clone()));
    let config_for_hid = current_config.clone();

    let (tx, rx) = channel::<AppMessage>();
    let (wake_tx, wake_rx) = channel::<HidCommand>();

    // --- Build tray icon & menu ---
    let initial_icon = create_tray_icon(None, false, config.display_mode);
    let tray_menu = Arc::new(Mutex::new(TrayMenu::new(
        None,
        None,
        config.time_delta,
        config.display_mode,
    )));

    let mut tray_icon = {
        let menu_lock = tray_menu.lock().unwrap();
        TrayIconBuilder::new()
            .with_menu(Box::new(menu_lock.menu.clone()))
            .with_tooltip("SteelMouse: Initializing...")
            .with_icon(initial_icon)
            .build()
            .ok()
    };

    // --- Thread: HID battery polling worker ---
    {
        let tx2 = tx;
        thread::spawn(move || {
            log::log("HID worker thread started");
            let mut mouse_manager = MouseManager::new(mock_mode);
            let mut consecutive_failures = 0u32;
            loop {
                log::log("HID worker: calling fetch_battery");
                let result = mouse_manager.fetch_battery();
                log::log(&format!("HID worker: result={}", if result.is_ok() { "Ok" } else { "Err" }));
                let timestamp = Local::now().format("%H:%M:%S").to_string();
                let is_error = result.is_err();
                let _ = tx2.send(AppMessage::BatteryUpdated(result, timestamp));
                log::log("HID worker: message sent, sleeping");

                let user_delta = config_for_hid.lock().unwrap().time_delta;
                let sleep_secs = if is_error {
                    consecutive_failures = consecutive_failures.saturating_add(1);
                    next_error_delay(consecutive_failures).min(user_delta)
                } else {
                    consecutive_failures = 0;
                    user_delta
                };

                let mut elapsed = 0u64;
                while elapsed < sleep_secs {
                    match wake_rx.recv_timeout(Duration::from_secs(1)) {
                        Ok(HidCommand::Wake) => break,
                        Ok(HidCommand::ReleaseDevice) => {
                            log::log("HID worker: releasing cached device handle for analyzer");
                            mouse_manager.clear_cache();
                        }
                        Err(_) => {}
                    }
                    elapsed += 1;
                    if elapsed >= config_for_hid.lock().unwrap().time_delta {
                        break;
                    }
                }
            }
        });
    }

    let menu_rx = MenuEvent::receiver();
    let tray_menu_ids = {
        let m = tray_menu.lock().unwrap();
        (
            m.quit_item.id().clone(),
            m.refresh_item.id().clone(),
            m.mode_hover_item.id().clone(),
            m.mode_icon_item.id().clone(),
            m.autostart_item.id().clone(),
            m.export_diag_item.id().clone(),
            m.interval_items.iter().map(|(&s, i)| (s, i.id().clone())).collect::<Vec<_>>(),
        )
    };

    let (quit_id, refresh_id, hover_id, icon_id, autostart_id, export_diag_id, interval_ids) = tray_menu_ids;

    let mut last_tray_state: Option<(Option<u8>, bool, DisplayMode)> = None;

    event_loop.run(move |_event, _, control_flow| {
        *control_flow = ControlFlow::WaitUntil(
            std::time::Instant::now() + Duration::from_millis(100),
        );

        // 1. Process incoming battery updates from HID worker
        while let Ok(AppMessage::BatteryUpdated(battery_res, timestamp)) = rx.try_recv() {
            log::log(&format!("tray loop: received BatteryUpdated at {}", timestamp));
            let (info_opt, is_charging, level_opt) = match &battery_res {
                Ok(info) => {
                    log::log(&format!("  -> Ok: name='{}' level={:?} charging={}", info.name, info.level, info.is_charging));
                    (Some(info.clone()), info.is_charging, info.level)
                }
                Err(err) => {
                    log::log(&format!("  -> Err: {}", err));
                    (None, false, None)
                }
            };

            let cfg = current_config.lock().unwrap().clone();
            let current_state = (level_opt, is_charging, cfg.display_mode);

            if should_update_tray_icon(last_tray_state, current_state) {
                log::log("tray loop: updating tray icon and tooltip (state changed)");
                let new_icon = create_tray_icon(level_opt, is_charging, cfg.display_mode);

                if let Some(tray) = tray_icon.as_mut() {
                    let _ = tray.set_icon(Some(new_icon));
                    let tooltip = level_opt
                        .map(|l| format!("Battery: {}%", l))
                        .unwrap_or_else(|| "SteelMouse: N/A".to_string());
                    let _ = tray.set_tooltip(Some(tooltip));
                }

                last_tray_state = Some(current_state);
            }

            let menu = tray_menu.lock().unwrap();
            menu.update(info_opt.as_ref(), Some(&timestamp), cfg.time_delta, cfg.display_mode);
        }

        // 2. Process system tray menu click events
        while let Ok(event) = menu_rx.try_recv() {
            log::log(&format!("tray event: id={:?}", event.id));
            if event.id == quit_id {
                log::log("Quit clicked - dropping tray icon and calling exit(0)");
                drop(tray_icon.take());
                std::process::exit(0);
            } else if event.id == refresh_id {
                log::log("Refresh clicked");
                let _ = wake_tx.send(HidCommand::Wake);
            } else if event.id == autostart_id {
                let m = tray_menu.lock().unwrap();
                let is_checked = m.autostart_item.is_checked();
                let target_state = !is_checked;
                log::log(&format!("Autostart toggled -> {}", target_state));
                match crate::autostart::set_autostart(target_state) {
                    Ok(_) => {
                        m.autostart_item.set_checked(target_state);
                    }
                    Err(e) => {
                        log::log(&format!("Failed to set autostart to {}: {}", target_state, e));
                    }
                }
            } else if event.id == export_diag_id {
                log::log("Analyze / Export Diagnostics clicked");
                let _ = wake_tx.send(HidCommand::ReleaseDevice);
                crate::analyzer::spawn_analyzer_subprocess();
            } else {
                let mut cfg = current_config.lock().unwrap().clone();
                let mut changed = false;
                if event.id == hover_id {
                    cfg.display_mode = DisplayMode::Hover;
                    changed = true;
                } else if event.id == icon_id {
                    cfg.display_mode = DisplayMode::Icon;
                    changed = true;
                } else {
                    for (secs, id) in &interval_ids {
                        if event.id == *id {
                            cfg.time_delta = *secs;
                            changed = true;
                            break;
                        }
                    }
                }
                if changed {
                    log::log(&format!("Config changed: mode={:?} interval={}s", cfg.display_mode, cfg.time_delta));
                    cfg.save();
                    *current_config.lock().unwrap() = cfg;
                    let _ = wake_tx.send(HidCommand::Wake);
                }
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_next_error_delay_backoff_progression() {
        assert_eq!(next_error_delay(0), 12);
        assert_eq!(next_error_delay(1), 12);
        assert_eq!(next_error_delay(2), 30);
        assert_eq!(next_error_delay(3), 60);
        assert_eq!(next_error_delay(4), 60);
        assert_eq!(next_error_delay(100), 60);
    }

    #[test]
    fn test_should_update_tray_icon() {
        let initial = (Some(85), false, DisplayMode::Hover);
        // Initially, no previous state -> should update
        assert!(should_update_tray_icon(None, initial));

        // Same state -> should skip update
        assert!(!should_update_tray_icon(Some(initial), initial));

        // Battery level changed -> should update
        let changed_level = (Some(84), false, DisplayMode::Hover);
        assert!(should_update_tray_icon(Some(initial), changed_level));

        // Charging state changed -> should update
        let changed_charging = (Some(85), true, DisplayMode::Hover);
        assert!(should_update_tray_icon(Some(initial), changed_charging));

        // Display mode changed -> should update
        let changed_mode = (Some(85), false, DisplayMode::Icon);
        assert!(should_update_tray_icon(Some(initial), changed_mode));

        // Error state transition (level Some -> None) -> should update
        let error_state = (None, false, DisplayMode::Hover);
        assert!(should_update_tray_icon(Some(initial), error_state));

        // Repeated error state -> should skip update
        assert!(!should_update_tray_icon(Some(error_state), error_state));
    }
}
