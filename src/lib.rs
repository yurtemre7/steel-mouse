//! # SteelMouse Rust Library
//!
//! High-performance native Rust protocol engine for SteelSeries gaming mice.
//! Supports 78 SteelSeries Product IDs, HID buffer draining, multi-pass 2.4GHz wireless querying,
//! charging status detection, and battery discharge rate estimation.

pub mod analyzer;
pub mod autostart;
pub mod config;
pub mod devices;
pub mod hid;
pub mod icon;
pub mod log;
pub mod menu;
pub mod protocol;

pub use protocol::{
    analyze_response_bytes, format_github_issue_markdown, get_profile, open_file_in_file_manager,
    run_diagnostic, run_diagnostic_with_battery, save_diagnostic_file,
    save_diagnostic_file_with_battery, BatteryInfo, BatteryKind, BatterySample, BatteryTracker,
    CandidateMatch, MouseManager, MouseProfile,
};
