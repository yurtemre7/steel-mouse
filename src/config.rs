use directories::ProjectDirs;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

use crate::log;

pub const MIN_TIME_DELTA: u64 = 5;

/// Clamp `time_delta` to a minimum of 5 seconds to prevent busy-loop polling.
pub fn clamp_time_delta(time_delta: u64) -> u64 {
    time_delta.max(MIN_TIME_DELTA)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DisplayMode {
    #[default]
    Hover,
    Icon,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AppConfig {
    pub time_delta: u64,
    pub display_mode: DisplayMode,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            time_delta: 300, // 5 minutes default
            display_mode: DisplayMode::Hover,
        }
    }
}

impl AppConfig {
    fn get_config_path() -> Option<PathBuf> {
        let proj_dirs = ProjectDirs::from("de", "yurtemre", "SteelMouse")?;
        let config_dir = proj_dirs.config_dir();
        fs::create_dir_all(config_dir).ok()?;
        Some(config_dir.join("config.json"))
    }

    /// Parse configuration JSON and clamp `time_delta` to minimum threshold.
    pub fn parse_and_clamp(content: &str) -> Result<Self, serde_json::Error> {
        let mut config = serde_json::from_str::<AppConfig>(content)?;
        config.time_delta = clamp_time_delta(config.time_delta);
        Ok(config)
    }

    pub fn load() -> Self {
        if let Some(path) = Self::get_config_path() {
            if path.exists() {
                match fs::read_to_string(&path) {
                    Ok(content) => {
                        match Self::parse_and_clamp(&content) {
                            Ok(config) => return config,
                            Err(e) => {
                                log::log(&format!(
                                    "Failed to parse config file {:?}: {}. Using default config.",
                                    path, e
                                ));
                            }
                        }
                    }
                    Err(e) => {
                        log::log(&format!(
                            "Failed to read config file {:?}: {}. Using default config.",
                            path, e
                        ));
                    }
                }
            }
        }
        Self::default()
    }

    /// Save configuration atomically to `path` by writing to `.tmp` first, then renaming.
    pub fn save_to_path(&self, path: &Path) -> Result<(), std::io::Error> {
        let tmp_path = path.with_file_name("config.json.tmp");
        let mut to_save = self.clone();
        to_save.time_delta = clamp_time_delta(to_save.time_delta);
        let content = serde_json::to_string_pretty(&to_save)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;

        fs::write(&tmp_path, content)?;
        if let Err(e) = fs::rename(&tmp_path, path) {
            let _ = fs::remove_file(&tmp_path);
            return Err(e);
        }
        Ok(())
    }

    pub fn save(&self) {
        if let Some(path) = Self::get_config_path() {
            if let Err(e) = self.save_to_path(&path) {
                log::log(&format!("Failed to save config to {:?}: {}", path, e));
            }
        } else {
            log::log("Failed to resolve config directory for saving");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clamp_time_delta() {
        assert_eq!(clamp_time_delta(0), 5);
        assert_eq!(clamp_time_delta(1), 5);
        assert_eq!(clamp_time_delta(4), 5);
        assert_eq!(clamp_time_delta(5), 5);
        assert_eq!(clamp_time_delta(6), 6);
        assert_eq!(clamp_time_delta(300), 300);
    }

    #[test]
    fn test_parse_and_clamp_valid() {
        let json = r#"{"time_delta": 0, "display_mode": "hover"}"#;
        let config = AppConfig::parse_and_clamp(json).expect("should parse");
        assert_eq!(config.time_delta, 5);
        assert_eq!(config.display_mode, DisplayMode::Hover);

        let json_normal = r#"{"time_delta": 60, "display_mode": "icon"}"#;
        let config_normal = AppConfig::parse_and_clamp(json_normal).expect("should parse");
        assert_eq!(config_normal.time_delta, 60);
        assert_eq!(config_normal.display_mode, DisplayMode::Icon);
    }

    #[test]
    fn test_parse_and_clamp_invalid() {
        let json = r#"{"time_delta": "invalid"}"#;
        assert!(AppConfig::parse_and_clamp(json).is_err());
    }

    #[test]
    fn test_save_and_load_atomic() {
        let unique_id = format!(
            "steelmouse_test_cfg_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique_id);
        let _ = fs::create_dir_all(&dir);
        let path = dir.join("config.json");
        let tmp_path = dir.join("config.json.tmp");

        let cfg = AppConfig {
            time_delta: 120,
            display_mode: DisplayMode::Icon,
        };

        cfg.save_to_path(&path).expect("save should succeed");
        assert!(path.exists());
        assert!(!tmp_path.exists());

        let content = fs::read_to_string(&path).expect("read content");
        let loaded = AppConfig::parse_and_clamp(&content).expect("parse content");
        assert_eq!(loaded.time_delta, 120);
        assert_eq!(loaded.display_mode, DisplayMode::Icon);

        // Test overwrite with small time_delta
        let cfg2 = AppConfig {
            time_delta: 2, // will be clamped to 5
            display_mode: DisplayMode::Hover,
        };
        cfg2.save_to_path(&path).expect("overwrite save should succeed");
        assert!(path.exists());
        assert!(!tmp_path.exists());

        let content2 = fs::read_to_string(&path).expect("read content 2");
        let loaded2 = AppConfig::parse_and_clamp(&content2).expect("parse content 2");
        assert_eq!(loaded2.time_delta, 5);
        assert_eq!(loaded2.display_mode, DisplayMode::Hover);

        let _ = fs::remove_file(&path);
        let _ = fs::remove_dir(&dir);
    }
}
