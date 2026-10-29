pub mod devices;
pub mod hid;
pub mod recorder;
pub mod tracker;

pub use devices::{get_profile, BatteryKind, MouseProfile};
pub use hid::{BatteryInfo, MouseManager};
pub use recorder::{
    analyze_response_bytes, format_github_issue_markdown, open_file_in_file_manager,
    run_diagnostic, run_diagnostic_with_battery, save_diagnostic_file,
    save_diagnostic_file_with_battery, CandidateMatch,
};
pub use tracker::{BatterySample, BatteryTracker};
