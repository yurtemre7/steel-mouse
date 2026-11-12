// src/log.rs - File-based logger for Windows (since windows_subsystem="windows" hides stdout)
use directories::ProjectDirs;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

/// Maximum log file size before rotation (1 MiB).
pub const MAX_LOG_SIZE: u64 = 1024 * 1024;

static LOG_FILE: Mutex<Option<std::fs::File>> = Mutex::new(None);

pub fn init() {
    // Drop any existing file handle before rotating/reopening
    if let Ok(mut guard) = LOG_FILE.lock() {
        *guard = None;
    }

    // Write log next to the exe / in the user data dir
    let path = log_path();
    let _ = rotate_if_large(&path, MAX_LOG_SIZE);

    if let Ok(f) = OpenOptions::new().create(true).append(true).open(&path) {
        if let Ok(mut guard) = LOG_FILE.lock() {
            *guard = Some(f);
        }
    }
    log(&format!("\n\n===== SteelMouse started {} =====", now_timestamp()));
    log(&format!("Log file: {}", path.display()));
}

pub fn log(msg: &str) {
    // Always try stdout (works on macOS / cargo run)
    println!("[LOG] {}", msg);

    // Also write to file (essential on Windows where stdout is hidden)
    if let Ok(mut guard) = LOG_FILE.lock() {
        if let Some(f) = guard.as_mut() {
            let _ = writeln!(f, "[{}] {}", now_timestamp(), msg);
            let _ = f.flush();
        }
    }
}

/// Returns the formatted local timestamp `YYYY-MM-DD HH:MM:SS`.
pub fn now_timestamp() -> String {
    format_timestamp(&chrono::Local::now())
}

/// Formats any DateTime with timezone into `YYYY-MM-DD HH:MM:SS`.
pub fn format_timestamp<T: chrono::TimeZone>(dt: &chrono::DateTime<T>) -> String
where
    T::Offset: std::fmt::Display,
{
    dt.format("%Y-%m-%d %H:%M:%S").to_string()
}

/// Resolves the log file path:
/// 1. `directories::ProjectDirs::from("de","yurtemre","SteelMouse")` data_local_dir/`steelmouse.log` (create dir)
/// 2. Fall back to the exe directory/`steelmouse.log`
/// 3. Fall back to relative `steelmouse.log`
pub fn log_path() -> PathBuf {
    let proj = ProjectDirs::from("de", "yurtemre", "SteelMouse");
    let proj_data_local = proj.as_ref().map(|p| p.data_local_dir());
    let exe = std::env::current_exe().ok();
    let exe_dir = exe.as_deref().and_then(|e| e.parent());
    resolve_log_path(proj_data_local, exe_dir)
}

/// Helper for path resolution with fallback chain.
pub fn resolve_log_path(preferred_dir: Option<&Path>, exe_dir: Option<&Path>) -> PathBuf {
    if let Some(dir) = preferred_dir {
        if std::fs::create_dir_all(dir).is_ok() {
            return dir.join("steelmouse.log");
        }
    }
    if let Some(dir) = exe_dir {
        return dir.join("steelmouse.log");
    }
    PathBuf::from("steelmouse.log")
}

/// Rotates the log file if its size exceeds `max_bytes`.
///
/// Renames the file to `steelmouse.log.1` (or `<filename>.1`), overwriting any existing backup.
pub fn rotate_if_large(path: &Path, max_bytes: u64) -> std::io::Result<bool> {
    if let Ok(metadata) = std::fs::metadata(path) {
        if metadata.is_file() && metadata.len() > max_bytes {
            let backup_path = rotated_path(path);
            if backup_path.exists() {
                let _ = std::fs::remove_file(&backup_path);
            }
            std::fs::rename(path, &backup_path)?;
            return Ok(true);
        }
    }
    Ok(false)
}

fn rotated_path(path: &Path) -> PathBuf {
    let file_name = path
        .file_name()
        .and_then(|f| f.to_str())
        .unwrap_or("steelmouse.log");
    if file_name == "steelmouse.log" {
        path.with_file_name("steelmouse.log.1")
    } else {
        path.with_file_name(format!("{}.1", file_name))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_timestamp_shape() {
        let now_str = now_timestamp();
        assert_eq!(now_str.len(), 19);
        let parsed = chrono::NaiveDateTime::parse_from_str(&now_str, "%Y-%m-%d %H:%M:%S");
        assert!(parsed.is_ok(), "Timestamp '{}' failed to parse", now_str);
    }

    #[test]
    fn test_format_timestamp_deterministic() {
        use chrono::TimeZone;
        let dt = chrono::Utc.with_ymd_and_hms(2026, 11, 12, 13, 14, 15).unwrap();
        assert_eq!(format_timestamp(&dt), "2026-11-12 13:14:15");
    }

    #[test]
    fn test_resolve_log_path_preferred() {
        let unique_id = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let temp_dir = std::env::temp_dir().join(format!("sm_test_pref_{}_{}", std::process::id(), unique_id));
        let resolved = resolve_log_path(Some(&temp_dir), None);
        assert_eq!(resolved, temp_dir.join("steelmouse.log"));
        let _ = std::fs::remove_dir_all(&temp_dir);
    }

    #[test]
    fn test_resolve_log_path_exe_fallback() {
        let exe_dir = Path::new("/some/exe/dir");
        let resolved = resolve_log_path(None, Some(exe_dir));
        assert_eq!(resolved, exe_dir.join("steelmouse.log"));
    }

    #[test]
    fn test_resolve_log_path_default_fallback() {
        let resolved = resolve_log_path(None, None);
        assert_eq!(resolved, PathBuf::from("steelmouse.log"));
    }

    #[test]
    fn test_rotate_if_large_nonexistent() {
        let temp_dir = std::env::temp_dir().join(format!("sm_test_nonexistent_{}", std::process::id()));
        let log_file = temp_dir.join("steelmouse.log");
        let rotated = rotate_if_large(&log_file, 1024);
        assert!(matches!(rotated, Ok(false)));
    }

    #[test]
    fn test_rotate_if_large_under_limit() {
        let unique_id = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let temp_dir = std::env::temp_dir().join(format!("sm_test_under_{}_{}", std::process::id(), unique_id));
        std::fs::create_dir_all(&temp_dir).unwrap();
        let log_file = temp_dir.join("steelmouse.log");
        std::fs::write(&log_file, "small log entry\n").unwrap();

        let rotated = rotate_if_large(&log_file, 1024).unwrap();
        assert!(!rotated, "Should not rotate file under size threshold");
        assert!(log_file.exists(), "Original file should still exist");
        assert!(!temp_dir.join("steelmouse.log.1").exists(), "Rotated file should not exist");

        let _ = std::fs::remove_dir_all(&temp_dir);
    }

    #[test]
    fn test_rotate_if_large_over_limit() {
        let unique_id = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let temp_dir = std::env::temp_dir().join(format!("sm_test_over_{}_{}", std::process::id(), unique_id));
        std::fs::create_dir_all(&temp_dir).unwrap();
        let log_file = temp_dir.join("steelmouse.log");
        let content = "a".repeat(100);
        std::fs::write(&log_file, &content).unwrap();

        let rotated = rotate_if_large(&log_file, 50).unwrap();
        assert!(rotated, "Should rotate file over size threshold");
        assert!(!log_file.exists(), "Original file should have been moved");
        let backup = temp_dir.join("steelmouse.log.1");
        assert!(backup.exists(), "Backup file should exist");
        assert_eq!(std::fs::read_to_string(&backup).unwrap(), content);

        let _ = std::fs::remove_dir_all(&temp_dir);
    }

    #[test]
    fn test_rotate_if_large_overwrites_existing_backup() {
        let unique_id = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let temp_dir = std::env::temp_dir().join(format!("sm_test_overwrite_{}_{}", std::process::id(), unique_id));
        std::fs::create_dir_all(&temp_dir).unwrap();
        let log_file = temp_dir.join("steelmouse.log");
        let backup_file = temp_dir.join("steelmouse.log.1");

        std::fs::write(&backup_file, "old backup content").unwrap();
        let new_content = "b".repeat(100);
        std::fs::write(&log_file, &new_content).unwrap();

        let rotated = rotate_if_large(&log_file, 50).unwrap();
        assert!(rotated);
        assert!(!log_file.exists());
        assert_eq!(std::fs::read_to_string(&backup_file).unwrap(), new_content);

        let _ = std::fs::remove_dir_all(&temp_dir);
    }

    #[test]
    fn test_log_path_ends_with_steelmouse_log() {
        let path = log_path();
        assert_eq!(
            path.file_name().and_then(|f| f.to_str()),
            Some("steelmouse.log")
        );
    }
}
