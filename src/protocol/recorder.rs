use hidapi::HidApi;
use serde_json::{json, Value};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;
use chrono::Utc;
use crate::log;
use crate::protocol::devices;
use crate::protocol::hid::{get_interface_number, MouseManager};

#[derive(Debug, Clone)]
pub struct CandidateMatch {
    pub vendor_id: u16,
    pub product_id: u16,
    pub product_name: String,
    pub endpoint: i32,
    pub command_hex: String,
    pub command_byte: u8,
    pub battery_kind_rust: String,
    pub decoded_level: u8,
    pub decoded_charging: bool,
    pub exact_match: bool,
    pub delta_from_known: Option<u8>,
    pub raw_preview: Vec<u8>,
}

impl CandidateMatch {
    pub fn rust_profile_snippet(&self) -> String {
        let ep = if self.endpoint >= 0 { self.endpoint } else { 0 };
        let clean_name = if self.product_name.starts_with("SteelSeries") {
            self.product_name.clone()
        } else {
            format!("SteelSeries {}", self.product_name)
        };
        format!(
            "        (0x1038, 0x{:04x}) => Some(MouseProfile {{\n            name: \"{}\",\n            vendor_id: 0x1038,\n            product_id: 0x{:04x},\n            endpoint: {},\n            battery_kind: Some({}),\n        }}),",
            self.product_id, clean_name, self.product_id, ep, self.battery_kind_rust
        )
    }
}

pub fn analyze_response_bytes(
    cmd: u8,
    raw_bytes: &[u8],
    known_battery: Option<u8>,
) -> Vec<(String, u8, bool, bool, Option<u8>)> {
    let mut interpretations = Vec::new();
    if raw_bytes.len() < 2 || raw_bytes.iter().all(|&b| b == 0) {
        return interpretations;
    }

    let is_echo = raw_bytes[0] == cmd
        || (raw_bytes[0] == 0x00 && raw_bytes.len() >= 3 && raw_bytes[1] == cmd);

    if (cmd == 0xD2 || cmd == 0x92) && is_echo {
        if let Some((Some(lvl), chg)) = MouseManager::decode_direct_aerox_response(raw_bytes) {
            if lvl <= 100 {
                let delta = known_battery.map(|k| k.abs_diff(lvl));
                let exact = delta == Some(0);
                interpretations.push((
                    format!("BatteryKind::DirectAerox {{ command: 0x{:02X} }}", cmd),
                    lvl,
                    chg,
                    exact,
                    delta,
                ));
            }
        }
        if let Some((Some(lvl), chg)) = MouseManager::decode_aerox_prime_response(raw_bytes) {
            let battery_byte = if raw_bytes.len() >= 4 && raw_bytes[0] == 0x00 && raw_bytes[2] == 0x00 {
                raw_bytes[3]
            } else if raw_bytes.len() >= 3 && raw_bytes[1] == 0x00 {
                raw_bytes[2]
            } else if raw_bytes.len() >= 3 && raw_bytes[0] == 0x00 {
                raw_bytes[2]
            } else {
                raw_bytes[1]
            };
            let raw_val = battery_byte & !0x80;
            // Only propose AeroxPrime 1..21 scaling if raw_val is actually in 1..=21
            if (1..=21).contains(&raw_val) {
                let delta = known_battery.map(|k| k.abs_diff(lvl));
                let exact = delta == Some(0);
                interpretations.push((
                    format!("BatteryKind::AeroxPrime {{ command: 0x{:02X} }}", cmd),
                    lvl,
                    chg,
                    exact,
                    delta,
                ));
            }
        }
    } else if cmd == 0xAA {
        if let Some((Some(lvl), chg)) = MouseManager::decode_rival3_650_response(raw_bytes) {
            let delta = known_battery.map(|k| k.abs_diff(lvl));
            let exact = delta == Some(0);
            interpretations.push((
                "BatteryKind::Rival3Or650".to_string(),
                lvl,
                chg,
                exact,
                delta,
            ));
        }
    }

    interpretations
}

pub fn run_diagnostic(api: &mut HidApi) -> Value {
    run_diagnostic_with_battery(api, None)
}

pub fn run_diagnostic_with_battery(api: &mut HidApi, known_battery: Option<u8>) -> Value {
    log::log(&format!(
        "Running HID mouse diagnostic scan (known_battery={:?})...",
        known_battery
    ));
    let _ = api.refresh_devices();

    let mut device_records = Vec::new();
    let mut all_candidates: Vec<CandidateMatch> = Vec::new();
    let mut count = 0;

    for dev_info in api.device_list() {
        if dev_info.vendor_id() == 0x1038 {
            count += 1;
            let pid = dev_info.product_id();
            let raw_iface = dev_info.interface_number();
            let resolved_iface = get_interface_number(dev_info);
            let prod = dev_info
                .product_string()
                .unwrap_or("SteelSeries Device")
                .to_string();
            let path_str = dev_info.path().to_string_lossy().to_string();
            let existing_profile = devices::get_profile(0x1038, pid);

            log::log(&format!(
                "Diagnostic scan: found PID=0x{:04X} iface={} (raw={}) prod='{}'",
                pid, resolved_iface, raw_iface, prod
            ));

            let mut probed_commands = Vec::new();

            if let Ok(device) = dev_info.open_device(api) {
                for &cmd in &[0xD2u8, 0x92u8, 0xAAu8, 0xB2u8, 0x90u8] {
                    // Drain buffer prior to sending command
                    let mut drain = [0u8; 64];
                    while device.read_timeout(&mut drain, 0).unwrap_or(0) > 0 {}

                    let mut req = [0u8; 64];
                    req[0] = 0x00;
                    req[1] = cmd;
                    if cmd == 0xAA {
                        req[2] = 0x01;
                    }

                    let short_req: &[u8] = if cmd == 0xAA {
                        &[0x00, 0xAA, 0x01]
                    } else {
                        &[0x00, cmd]
                    };

                    let write_ok = device.write(short_req).is_ok()
                        || device.write(&req).is_ok()
                        || device.send_feature_report(short_req).is_ok();

                    let mut responses = Vec::new();
                    if write_ok {
                        for attempt in 0..5 {
                            let mut res = [0u8; 64];
                            match device.read_timeout(&mut res, 200) {
                                Ok(n) if n >= 2 => {
                                    let slice = &res[..n];
                                    let decoded_list =
                                        analyze_response_bytes(cmd, slice, known_battery);

                                    let mut decoded_json = Vec::new();
                                    for (kind_str, lvl, chg, exact, delta) in &decoded_list {
                                        decoded_json.push(json!({
                                            "battery_kind": kind_str,
                                            "level": lvl,
                                            "is_charging": chg,
                                            "matches_known_battery": exact,
                                            "delta_from_known": delta,
                                        }));

                                        if attempt == 0 {
                                            all_candidates.push(CandidateMatch {
                                                vendor_id: 0x1038,
                                                product_id: pid,
                                                product_name: prod.clone(),
                                                endpoint: resolved_iface,
                                                command_hex: format!("0x{:02X}", cmd),
                                                command_byte: cmd,
                                                battery_kind_rust: kind_str.clone(),
                                                decoded_level: *lvl,
                                                decoded_charging: *chg,
                                                exact_match: *exact,
                                                delta_from_known: *delta,
                                                raw_preview: slice[..n.min(12)].to_vec(),
                                            });
                                        }
                                    }

                                    // Also check if known_battery appears raw anywhere in the first 16 bytes
                                    let matching_byte_indices: Vec<usize> = if let Some(kb) = known_battery {
                                        slice
                                            .iter()
                                            .take(16)
                                            .enumerate()
                                            .filter_map(|(i, &b)| {
                                                let raw = b & !0x80;
                                                let scaled = if (1..=21).contains(&raw) {
                                                    Some((raw.saturating_sub(1)) * 5)
                                                } else {
                                                    None
                                                };
                                                if raw == kb || b == kb || scaled == Some(kb) {
                                                    Some(i)
                                                } else {
                                                    None
                                                }
                                            })
                                            .collect()
                                    } else {
                                        Vec::new()
                                    };

                                    responses.push(json!({
                                        "attempt": attempt,
                                        "length": n,
                                        "raw_bytes": slice,
                                        "raw_preview_hex": slice.iter().take(16).map(|b| format!("{:02X}", b)).collect::<Vec<_>>().join(" "),
                                        "decoded_candidates": decoded_json,
                                        "matching_byte_indices": matching_byte_indices,
                                    }));
                                }
                                _ => break,
                            }
                        }
                    }

                    probed_commands.push(json!({
                        "command": format!("0x{:02X}", cmd),
                        "write_success": write_ok,
                        "responses": responses
                    }));

                    std::thread::sleep(Duration::from_millis(50));
                }
            } else {
                log::log(&format!("  open_device failed for path={:?}", path_str));
            }

            device_records.push(json!({
                "vendor_id": "0x1038",
                "product_id": format!("0x{:04X}", pid),
                "product_id_decimal": pid,
                "product_name": prod,
                "interface": resolved_iface,
                "raw_interface": raw_iface,
                "already_supported": existing_profile.is_some(),
                "existing_profile_name": existing_profile.map(|p| p.name),
                "path": path_str,
                "probed_commands": probed_commands
            }));
        }
    }

    // Rank candidates:
    // 1. Exact match with user-supplied known_battery
    // 2. Smallest delta from known_battery (within <= 5% for 5%-step mice)
    // 3. Echoed 0xD2 / 0x92 commands on interfaces >= 2 over 0xAA
    all_candidates.sort_by(|a, b| {
        b.exact_match
            .cmp(&a.exact_match)
            .then_with(|| {
                let da = a.delta_from_known.unwrap_or(255);
                let db = b.delta_from_known.unwrap_or(255);
                da.cmp(&db)
            })
            .then_with(|| {
                let a_echo = a.command_byte == 0xD2 || a.command_byte == 0x92;
                let b_echo = b.command_byte == 0xD2 || b.command_byte == 0x92;
                b_echo.cmp(&a_echo)
            })
            .then_with(|| b.endpoint.cmp(&a.endpoint))
    });

    let best_candidate_json = all_candidates.first().map(|c| {
        json!({
            "product_id": format!("0x{:04X}", c.product_id),
            "product_name": c.product_name,
            "endpoint": c.endpoint,
            "command": c.command_hex,
            "battery_kind": c.battery_kind_rust,
            "decoded_level": c.decoded_level,
            "decoded_charging": c.decoded_charging,
            "exact_match_with_user_input": c.exact_match,
            "rust_profile_code": c.rust_profile_snippet(),
        })
    });

    let candidates_json: Vec<Value> = all_candidates
        .iter()
        .map(|c| {
            json!({
                "product_id": format!("0x{:04X}", c.product_id),
                "product_name": c.product_name,
                "endpoint": c.endpoint,
                "command": c.command_hex,
                "battery_kind": c.battery_kind_rust,
                "decoded_level": c.decoded_level,
                "decoded_charging": c.decoded_charging,
                "exact_match": c.exact_match,
                "delta_from_known": c.delta_from_known,
                "raw_preview": c.raw_preview,
                "rust_profile_code": c.rust_profile_snippet(),
            })
        })
        .collect();

    log::log(&format!(
        "Diagnostic scan complete. Scanned {} devices, {} candidate configurations.",
        count,
        all_candidates.len()
    ));

    json!({
        "steelmouse_version": env!("CARGO_PKG_VERSION"),
        "os": env::consts::OS,
        "arch": env::consts::ARCH,
        "timestamp": Utc::now().to_rfc3339(),
        "user_reported_battery_percent": known_battery,
        "devices_found": count,
        "recommended_profile": best_candidate_json,
        "all_candidate_profiles": candidates_json,
        "devices": device_records
    })
}

pub fn format_github_issue_markdown(report: &Value) -> String {
    let mut md = String::new();
    let version = report
        .get("steelmouse_version")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    let os = report.get("os").and_then(|v| v.as_str()).unwrap_or("unknown");
    let arch = report
        .get("arch")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    let user_batt = report
        .get("user_reported_battery_percent")
        .and_then(|v| v.as_u64());

    md.push_str("## 🖱️ New Mouse Support Request / Diagnostic Analysis\n\n");
    md.push_str(&format!("- **SteelMouse Version**: `v{}`\n", version));
    md.push_str(&format!("- **OS / Arch**: `{}` (`{}`)\n", os, arch));
    if let Some(b) = user_batt {
        md.push_str(&format!(
            "- **Battery % shown in SteelSeries GG**: `{}%`\n",
            b
        ));
    } else {
        md.push_str("- **Battery % shown in SteelSeries GG**: *(not specified)*\n");
    }

    if let Some(rec) = report.get("recommended_profile").filter(|v| !v.is_null()) {
        md.push_str("\n### ✅ Auto-Detected `src/protocol/devices.rs` Profile\n");
        if let Some(code) = rec.get("rust_profile_code").and_then(|c| c.as_str()) {
            md.push_str("```rust\n");
            md.push_str(code);
            md.push_str("\n```\n");
        }
        let lvl = rec.get("decoded_level").and_then(|l| l.as_u64()).unwrap_or(0);
        let chg = rec
            .get("decoded_charging")
            .and_then(|c| c.as_bool())
            .unwrap_or(false);
        let exact = rec
            .get("exact_match_with_user_input")
            .and_then(|e| e.as_bool())
            .unwrap_or(false);
        md.push_str(&format!(
            "- **Decoded Battery**: `{}%` (Charging: `{}`, Exact GG Match: `{}`)\n",
            lvl, chg, exact
        ));
    }

    md.push_str("\n### 🔍 Detected SteelSeries HID Interfaces\n");
    if let Some(devs) = report.get("devices").and_then(|d| d.as_array()) {
        for dev in devs {
            let pid = dev.get("product_id").and_then(|v| v.as_str()).unwrap_or("?");
            let name = dev
                .get("product_name")
                .and_then(|v| v.as_str())
                .unwrap_or("?");
            let iface = dev.get("interface").and_then(|v| v.as_i64()).unwrap_or(-1);
            md.push_str(&format!("- **`{}`** (`1038:{}`) — Interface `{}`\n", name, pid, iface));
            if let Some(cmds) = dev.get("probed_commands").and_then(|c| c.as_array()) {
                for c in cmds {
                    let cmd_str = c.get("command").and_then(|v| v.as_str()).unwrap_or("?");
                    if let Some(resps) = c.get("responses").and_then(|r| r.as_array()) {
                        if let Some(first) = resps.first() {
                            let hex = first
                                .get("raw_preview_hex")
                                .and_then(|v| v.as_str())
                                .unwrap_or("");
                            md.push_str(&format!("  - Cmd `{}` -> `[{}]`\n", cmd_str, hex));
                        }
                    }
                }
            }
        }
    }

    md
}

pub fn save_diagnostic_file(custom_path: Option<&Path>) -> Result<PathBuf, String> {
    save_diagnostic_file_with_battery(custom_path, None).map(|(path, _)| path)
}

pub fn save_diagnostic_file_with_battery(
    custom_path: Option<&Path>,
    known_battery: Option<u8>,
) -> Result<(PathBuf, Value), String> {
    let mut api = HidApi::new().map_err(|e| format!("Failed to init HidApi: {}", e))?;
    let report = run_diagnostic_with_battery(&mut api, known_battery);

    let target_path = match custom_path {
        Some(p) => p.to_path_buf(),
        None => {
            let filename = format!(
                "steelmouse_diagnostic_{}.json",
                Utc::now().format("%Y%m%d_%H%M%S")
            );
            if let Some(desktop) = directories::UserDirs::new()
                .and_then(|u| u.desktop_dir().map(|d| d.to_path_buf()))
            {
                desktop.join(filename)
            } else {
                PathBuf::from(filename)
            }
        }
    };

    let formatted_json = serde_json::to_string_pretty(&report).map_err(|e| e.to_string())?;
    if let Some(parent) = target_path.parent() {
        let _ = fs::create_dir_all(parent);
    }

    fs::write(&target_path, formatted_json)
        .map_err(|e| format!("Failed to write file {}: {}", target_path.display(), e))?;
    log::log(&format!(
        "Diagnostic report saved to {}",
        target_path.display()
    ));
    Ok((target_path, report))
}

pub fn open_file_in_file_manager(path: &Path) {
    let path_str = path.to_string_lossy();
    #[cfg(target_os = "windows")]
    {
        let _ = std::process::Command::new("explorer")
            .args(&["/select,", &path_str])
            .spawn();
    }
    #[cfg(target_os = "macos")]
    {
        let _ = std::process::Command::new("open")
            .args(&["-R", &path_str])
            .spawn();
    }
    #[cfg(target_os = "linux")]
    {
        if let Some(parent) = path.parent() {
            let _ = std::process::Command::new("xdg-open")
                .arg(parent)
                .spawn();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_diagnostic_report_json_schema() {
        if let Ok(mut api) = HidApi::new() {
            let report = run_diagnostic(&mut api);
            assert!(report.get("steelmouse_version").is_some());
            assert!(report.get("os").is_some());
            assert!(report.get("timestamp").is_some());
            assert!(report.get("devices").is_some());
        }
    }

    #[test]
    fn test_analyze_response_bytes_matches_known_battery() {
        // Rival Pro response: [0x92, 0x00, 29, 0x01, 100] with user supplying 29%
        let raw = [0x92u8, 0x00, 29, 0x01, 100];
        let results = analyze_response_bytes(0x92, &raw, Some(29));
        assert!(!results.is_empty());
        let (kind, lvl, chg, exact, delta) = &results[0];
        assert_eq!(kind, "BatteryKind::DirectAerox { command: 0x92 }");
        assert_eq!(*lvl, 29);
        assert_eq!(*chg, false);
        assert!(exact);
        assert_eq!(*delta, Some(0));

        // Aerox 3 Gen 1 response: [0xD2, 18, 0, 0] -> (18-1)*5 = 85%
        let raw_aerox = [0xD2u8, 18, 0, 0];
        let results_aerox = analyze_response_bytes(0xD2, &raw_aerox, Some(85));
        let aerox_match = results_aerox
            .iter()
            .find(|(_, _, _, exact, _)| *exact)
            .expect("Should find exact match for 85% on AeroxPrime scale");
        assert_eq!(aerox_match.0, "BatteryKind::AeroxPrime { command: 0xD2 }");
        assert_eq!(aerox_match.1, 85);
    }

    #[test]
    fn test_save_diagnostic_file_custom_path() {
        let temp_dir = std::env::temp_dir();
        let target_file = temp_dir.join("steelmouse_test_diag.json");
        if target_file.exists() {
            let _ = std::fs::remove_file(&target_file);
        }

        if let Ok(saved_path) = save_diagnostic_file(Some(&target_file)) {
            assert!(saved_path.exists());
            let content = std::fs::read_to_string(&saved_path).unwrap();
            assert!(content.contains("steelmouse_version"));
            let _ = std::fs::remove_file(saved_path);
        }
    }
}
