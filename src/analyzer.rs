use eframe::egui;
use serde_json::Value;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use crate::log;
use crate::protocol::recorder::{
    format_github_issue_markdown, open_file_in_file_manager, save_diagnostic_file_with_battery,
};

fn url_encode(input: &str) -> String {
    let mut out = String::with_capacity(input.len() * 2);
    for b in input.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char);
            }
            b' ' => out.push_str("%20"),
            _ => out.push_str(&format!("%{:02X}", b)),
        }
    }
    out
}

struct AnalyzerApp {
    battery_input: String,
    scanning: bool,
    status_message: String,
    last_saved_path: Option<PathBuf>,
    last_report: Option<Value>,
    markdown_report: String,
    scan_result_slot: Arc<Mutex<Option<Result<(PathBuf, Value), String>>>>,
}

impl AnalyzerApp {
    fn new() -> Self {
        Self {
            battery_input: String::new(),
            scanning: false,
            status_message: "Enter the battery % currently shown in SteelSeries GG (optional, but helps pinpoint the exact byte), then click Scan & Analyze.".to_string(),
            last_saved_path: None,
            last_report: None,
            markdown_report: String::new(),
            scan_result_slot: Arc::new(Mutex::new(None)),
        }
    }

    fn parsed_battery(&self) -> Option<u8> {
        let trimmed = self.battery_input.trim().trim_end_matches('%').trim();
        if trimmed.is_empty() {
            return None;
        }
        trimmed.parse::<u8>().ok().filter(|&v| v <= 100)
    }

    fn start_scan(&mut self, ctx: egui::Context) {
        if self.scanning {
            return;
        }
        self.scanning = true;
        let known_batt = self.parsed_battery();
        self.status_message = match known_batt {
            Some(b) => format!("Scanning SteelSeries USB HID interfaces (matching against {}%)...", b),
            None => "Scanning SteelSeries USB HID interfaces...".to_string(),
        };

        let slot = self.scan_result_slot.clone();
        std::thread::spawn(move || {
            let res = save_diagnostic_file_with_battery(None, known_batt);
            if let Ok(mut guard) = slot.lock() {
                *guard = Some(res);
            }
            ctx.request_repaint();
        });
    }
}

impl eframe::App for AnalyzerApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        if self.scanning {
            if let Ok(mut guard) = self.scan_result_slot.lock() {
                if let Some(res) = guard.take() {
                    self.scanning = false;
                    match res {
                        Ok((path, report)) => {
                            self.markdown_report = format_github_issue_markdown(&report);
                            let dev_count = report
                                .get("devices_found")
                                .and_then(|v| v.as_u64())
                                .unwrap_or(0);
                            self.status_message = format!(
                                "Scan complete! Found {} SteelSeries HID interface(s). Saved JSON to {}",
                                dev_count,
                                path.display()
                            );
                            self.last_saved_path = Some(path);
                            self.last_report = Some(report);
                        }
                        Err(e) => {
                            self.status_message = format!("Scan failed: {}", e);
                        }
                    }
                }
            }
        }

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("🖱 SteelMouse — New Mouse Analyzer & Issue Generator");
            ui.add_space(6.0);
            ui.label(
                "Use this tool if your SteelSeries mouse is missing or showing the wrong battery percentage.",
            );
            ui.separator();

            ui.horizontal(|ui| {
                ui.label("Current Battery % in SteelSeries GG (0–100, optional):");
                let response = ui.add(
                    egui::TextEdit::singleline(&mut self.battery_input)
                        .desired_width(70.0)
                        .hint_text("e.g. 29"),
                );
                if response.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter)) {
                    self.start_scan(ctx.clone());
                }

                let btn = egui::Button::new(if self.scanning {
                    "⏳ Scanning..."
                } else {
                    "🔍 Scan & Analyze Mouse"
                });
                if ui.add_enabled(!self.scanning, btn).clicked() {
                    self.start_scan(ctx.clone());
                }
            });

            ui.add_space(6.0);
            ui.label(egui::RichText::new(&self.status_message).italics());

            if let Some(report) = &self.last_report {
                ui.separator();

                if let Some(rec) = report.get("recommended_profile").filter(|v| !v.is_null()) {
                    let prod_name = rec
                        .get("product_name")
                        .and_then(|v| v.as_str())
                        .unwrap_or("SteelSeries Mouse");
                    let pid = rec
                        .get("product_id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("?");
                    let ep = rec.get("endpoint").and_then(|v| v.as_i64()).unwrap_or(-1);
                    let lvl = rec
                        .get("decoded_level")
                        .and_then(|v| v.as_u64())
                        .unwrap_or(0);
                    let exact = rec
                        .get("exact_match_with_user_input")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);

                    ui.group(|ui| {
                        ui.label(
                            egui::RichText::new(format!(
                                "✅ Recommended Profile: {} (1038:{}, Endpoint {}) -> Decoded {}%{}",
                                prod_name,
                                pid,
                                ep,
                                lvl,
                                if exact { " [EXACT MATCH]" } else { "" }
                            ))
                            .strong(),
                        );
                        if let Some(code) = rec.get("rust_profile_code").and_then(|v| v.as_str()) {
                            ui.add(
                                egui::TextEdit::multiline(&mut code.to_string())
                                    .font(egui::TextStyle::Monospace)
                                    .desired_rows(6)
                                    .desired_width(f32::INFINITY),
                            );
                        }
                    });
                } else {
                    ui.colored_label(
                        egui::Color32::YELLOW,
                        "No automatic profile match found — the raw HID responses are included below so the developer can add support.",
                    );
                }

                ui.add_space(6.0);
                ui.horizontal(|ui| {
                    if ui.button("📋 Copy Issue Report to Clipboard").clicked() {
                        ctx.copy_text(self.markdown_report.clone());
                        self.status_message =
                            "✅ Copied Markdown report to clipboard! Ready to paste into GitHub.".to_string();
                    }

                    if let Some(path) = &self.last_saved_path {
                        if ui.button("📁 Reveal JSON File").clicked() {
                            open_file_in_file_manager(path);
                        }
                    }
                });

                ui.add_space(6.0);
                let title = report
                    .get("recommended_profile")
                    .and_then(|r| r.get("product_name"))
                    .and_then(|n| n.as_str())
                    .map(|n| format!("Support for {}", n))
                    .unwrap_or_else(|| "Support for new SteelSeries mouse".to_string());

                let issue_url = format!(
                    "https://github.com/yurtemre7/steel-mouse/issues/new?title={}&body={}",
                    url_encode(&title),
                    url_encode(&self.markdown_report)
                );

                ui.horizontal_wrapped(|ui| {
                    ui.label("🔗 Submit Issue in Browser:");
                    ui.hyperlink_to(
                        "https://github.com/yurtemre7/steel-mouse/issues/new (Click to open pre-filled issue)",
                        &issue_url,
                    );
                });

                ui.add_space(6.0);
                ui.label("GitHub Issue Preview (Markdown):");
                egui::ScrollArea::vertical()
                    .max_height(210.0)
                    .show(ui, |ui| {
                        ui.add(
                            egui::TextEdit::multiline(&mut self.markdown_report.as_str())
                                .font(egui::TextStyle::Monospace)
                                .desired_rows(10)
                                .desired_width(f32::INFINITY),
                        );
                    });
            }
        });
    }
}

pub fn run_analyzer_window() -> Result<(), String> {
    log::log("Launching SteelMouse Analyzer window...");
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([680.0, 560.0])
            .with_min_inner_size([560.0, 420.0]),
        ..Default::default()
    };

    eframe::run_native(
        "SteelMouse — Mouse Analyzer & Config Generator",
        options,
        Box::new(|_cc| Ok(Box::new(AnalyzerApp::new()))),
    )
    .map_err(|e| format!("Failed to launch analyzer window: {}", e))
}

pub fn spawn_analyzer_subprocess() {
    if let Ok(exe) = std::env::current_exe() {
        log::log(&format!(
            "Spawning analyzer subprocess: {} --analyze",
            exe.display()
        ));
        let _ = std::process::Command::new(exe).arg("--analyze").spawn();
    }
}
