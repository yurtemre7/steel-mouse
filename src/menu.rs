use muda::{
    CheckMenuItem, Menu, MenuItem, PredefinedMenuItem, Submenu,
};
use std::collections::HashMap;
use crate::config::DisplayMode;
use crate::hid::BatteryInfo;
use crate::log;

pub struct TrayMenu {
    pub menu: Menu,
    pub name_item: MenuItem,
    pub battery_item: MenuItem,
    pub status_item: MenuItem,
    pub last_update_item: MenuItem,
    pub refresh_item: MenuItem,
    pub interval_submenu: Submenu,
    pub interval_items: HashMap<u64, CheckMenuItem>,
    pub mode_submenu: Submenu,
    pub mode_hover_item: CheckMenuItem,
    pub mode_icon_item: CheckMenuItem,
    pub autostart_item: CheckMenuItem,
    pub export_diag_item: MenuItem,
    pub quit_item: MenuItem,
}

impl TrayMenu {
    pub fn new(
        battery_info: Option<&BatteryInfo>,
        last_updated: Option<&str>,
        time_delta: u64,
        display_mode: DisplayMode,
    ) -> Self {
        let menu = Menu::new();

        // 1. Status Information Labels (Disabled)
        let name_text = battery_info
            .map(|b| format!("Name: {}", b.name))
            .unwrap_or_else(|| "Name: N/A".to_string());
        let name_item = MenuItem::new(&name_text, false, None);

        let battery_text = battery_info
            .and_then(|b| b.level)
            .map(|l| format!("Battery: {}%", l))
            .unwrap_or_else(|| "Battery: N/A".to_string());
        let battery_item = MenuItem::new(&battery_text, false, None);

        let status_text = battery_info
            .map(|b| {
                if b.is_charging {
                    "Status: Charging"
                } else {
                    "Status: Discharging"
                }
            })
            .unwrap_or("Status: Discharging");
        let status_item = MenuItem::new(status_text, false, None);

        let last_update_text = format!(
            "Last updated: {}",
            last_updated.unwrap_or("--:--:--")
        );
        let last_update_item = MenuItem::new(&last_update_text, false, None);

        // 2. Refresh Action Button
        let refresh_item = MenuItem::new("🔄 Refresh Now", true, None);

        // 3. Refresh Interval Selection Submenu
        let interval_submenu = Submenu::new("⏱ Background Refresh Interval", true);
        let intervals = vec![
            (60, "1 Minute"),
            (300, "5 Minutes"),
            (600, "10 Minutes"),
            (1800, "30 Minutes"),
            (3600, "1 Hour"),
        ];

        let mut interval_items = HashMap::new();
        for (secs, label) in intervals {
            let item = CheckMenuItem::new(label, true, secs == time_delta, None);
            if let Err(e) = interval_submenu.append(&item) {
                log::log(&format!("Failed to append interval item to submenu: {}", e));
            }
            interval_items.insert(secs, item);
        }

        // 4. Display Mode Selection Submenu
        let mode_submenu = Submenu::new("⚙ Tray Icon Mode", true);
        let mode_hover_item = CheckMenuItem::new(
            "Hover Tooltip Only",
            true,
            display_mode == DisplayMode::Hover,
            None,
        );
        let mode_icon_item = CheckMenuItem::new(
            "Render Percentage Number on Icon",
            true,
            display_mode == DisplayMode::Icon,
            None,
        );

        if let Err(e) = mode_submenu.append(&mode_hover_item) {
            log::log(&format!("Failed to append hover item to submenu: {}", e));
        }
        if let Err(e) = mode_submenu.append(&mode_icon_item) {
            log::log(&format!("Failed to append icon item to submenu: {}", e));
        }

        // 5. Autostart Option Toggle
        let is_autostart = crate::autostart::is_autostart_enabled();
        let autostart_item = CheckMenuItem::new("Start Automatically on Login", true, is_autostart, None);

        // 6. Diagnostic & Analyzer Option
        let export_diag_item = MenuItem::new("🔍 Analyze / Report Unsupported Mouse...", true, None);

        // 7. Quit Option
        let quit_item = MenuItem::new("Quit", true, None);

        // Build Menu Hierarchy
        if let Err(e) = menu.append(&name_item) {
            log::log(&format!("Failed to append name item to menu: {}", e));
        }
        if let Err(e) = menu.append(&battery_item) {
            log::log(&format!("Failed to append battery item to menu: {}", e));
        }
        if let Err(e) = menu.append(&status_item) {
            log::log(&format!("Failed to append status item to menu: {}", e));
        }
        if let Err(e) = menu.append(&last_update_item) {
            log::log(&format!("Failed to append last update item to menu: {}", e));
        }
        if let Err(e) = menu.append(&refresh_item) {
            log::log(&format!("Failed to append refresh item to menu: {}", e));
        }
        if let Err(e) = menu.append(&PredefinedMenuItem::separator()) {
            log::log(&format!("Failed to append separator to menu: {}", e));
        }
        if let Err(e) = menu.append(&interval_submenu) {
            log::log(&format!("Failed to append interval submenu to menu: {}", e));
        }
        if let Err(e) = menu.append(&mode_submenu) {
            log::log(&format!("Failed to append mode submenu to menu: {}", e));
        }
        if let Err(e) = menu.append(&autostart_item) {
            log::log(&format!("Failed to append autostart item to menu: {}", e));
        }
        if let Err(e) = menu.append(&export_diag_item) {
            log::log(&format!("Failed to append export diag item to menu: {}", e));
        }
        if let Err(e) = menu.append(&PredefinedMenuItem::separator()) {
            log::log(&format!("Failed to append separator to menu: {}", e));
        }
        if let Err(e) = menu.append(&quit_item) {
            log::log(&format!("Failed to append quit item to menu: {}", e));
        }

        Self {
            menu,
            name_item,
            battery_item,
            status_item,
            last_update_item,
            refresh_item,
            interval_submenu,
            interval_items,
            mode_submenu,
            mode_hover_item,
            mode_icon_item,
            autostart_item,
            export_diag_item,
            quit_item,
        }
    }

    pub fn update(
        &self,
        battery_info: Option<&BatteryInfo>,
        last_updated: Option<&str>,
        time_delta: u64,
        display_mode: DisplayMode,
    ) {
        let name_text = battery_info
            .map(|b| format!("Name: {}", b.name))
            .unwrap_or_else(|| "Name: N/A".to_string());
        self.name_item.set_text(&name_text);

        let battery_text = battery_info
            .and_then(|b| b.level)
            .map(|l| format!("Battery: {}%", l))
            .unwrap_or_else(|| "Battery: N/A".to_string());
        self.battery_item.set_text(&battery_text);

        let status_text = battery_info
            .map(|b| {
                if b.is_charging {
                    "Status: Charging"
                } else {
                    "Status: Discharging"
                }
            })
            .unwrap_or("Status: Discharging");
        self.status_item.set_text(status_text);

        self.last_update_item.set_text(&format!(
            "Last updated: {}",
            last_updated.unwrap_or("--:--:--")
        ));

        // Re-enable interactive items & submenus
        self.refresh_item.set_enabled(true);
        self.interval_submenu.set_enabled(true);
        self.mode_submenu.set_enabled(true);

        for (&seconds, item) in &self.interval_items {
            item.set_enabled(true);
            item.set_checked(seconds == time_delta);
        }

        self.mode_hover_item.set_enabled(true);
        self.mode_hover_item.set_checked(display_mode == DisplayMode::Hover);

        self.mode_icon_item.set_enabled(true);
        self.mode_icon_item.set_checked(display_mode == DisplayMode::Icon);
    }
}
