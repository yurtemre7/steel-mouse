use std::env;
use std::path::PathBuf;
use crate::log;

pub fn is_autostart_enabled() -> bool {
    #[cfg(target_os = "windows")]
    {
        let output = std::process::Command::new("reg")
            .args(&["query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "/v", "SteelMouse"])
            .output();
        if let Ok(out) = output {
            return out.status.success();
        }
        false
    }
    #[cfg(target_os = "macos")]
    {
        if let Some(home) = dirs_home() {
            let plist_path = home.join("Library/LaunchAgents/com.steelmouse.plist");
            return plist_path.exists();
        }
        false
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        false
    }
}

pub fn set_autostart(enable: bool) -> Result<(), String> {
    let current_exe = env::current_exe().map_err(|e| e.to_string())?;
    let exe_str = current_exe.to_string_lossy().to_string();

    log::log(&format!("set_autostart(enable={}, exe='{}')", enable, exe_str));

    #[cfg(target_os = "windows")]
    {
        if enable {
            let status = std::process::Command::new("reg")
                .args(&[
                    "add",
                    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                    "/v",
                    "SteelMouse",
                    "/t",
                    "REG_SZ",
                    "/d",
                    &format!("\"{}\"", exe_str),
                    "/f",
                ])
                .status()
                .map_err(|e| e.to_string())?;
            if !status.success() {
                return Err("Failed to write Windows registry autostart key".to_string());
            }
        } else {
            let _ = std::process::Command::new("reg")
                .args(&[
                    "delete",
                    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                    "/v",
                    "SteelMouse",
                    "/f",
                ])
                .status();
        }
    }

    #[cfg(target_os = "macos")]
    {
        if let Some(home) = dirs_home() {
            let launch_agents_dir = home.join("Library/LaunchAgents");
            let plist_path = launch_agents_dir.join("com.steelmouse.plist");
            if enable {
                std::fs::create_dir_all(&launch_agents_dir).map_err(|e| e.to_string())?;
                let content = plist_content(&exe_str);
                std::fs::write(&plist_path, content).map_err(|e| e.to_string())?;
            } else if plist_path.exists() {
                if let Err(e) = std::fs::remove_file(&plist_path) {
                    if e.kind() != std::io::ErrorKind::NotFound {
                        return Err(e.to_string());
                    }
                }
            }
        } else {
            return Err("Failed to determine user home directory".to_string());
        }
    }

    Ok(())
}

#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
fn xml_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
pub fn plist_content(exe: &str) -> String {
    let escaped_exe = xml_escape(exe);
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.steelmouse.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>{}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"#,
        escaped_exe
    )
}

#[cfg(target_os = "macos")]
fn dirs_home() -> Option<PathBuf> {
    directories::UserDirs::new().map(|u| u.home_dir().to_path_buf())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_xml_escape() {
        assert_eq!(xml_escape("plain"), "plain");
        assert_eq!(xml_escape("a & b"), "a &amp; b");
        assert_eq!(xml_escape("<tag>"), "&lt;tag&gt;");
        assert_eq!(xml_escape("&<>"), "&amp;&lt;&gt;");
        assert_eq!(xml_escape("a & < b > & c"), "a &amp; &lt; b &gt; &amp; c");
    }

    #[test]
    fn test_plist_content_plain_path() {
        let content = plist_content("/Applications/SteelMouse.app/Contents/MacOS/steelmouse");
        assert!(content.contains("<string>com.steelmouse.app</string>"));
        assert!(content.contains("<string>/Applications/SteelMouse.app/Contents/MacOS/steelmouse</string>"));
        assert!(content.contains("<key>RunAtLoad</key>"));
        assert!(content.contains("<true/>"));
        assert!(content.starts_with("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"));
    }

    #[test]
    fn test_plist_content_escapes_xml_special_characters() {
        let content = plist_content("/Applications/Foo & Bar <Tools>/mouse > app");
        assert!(content.contains("<string>/Applications/Foo &amp; Bar &lt;Tools&gt;/mouse &gt; app</string>"));
        assert!(!content.contains("Foo & Bar"));
        assert!(!content.contains("<Tools>"));
        assert!(!content.contains("mouse > app"));
    }

    #[test]
    fn test_plist_content_multiple_ampersands() {
        let content = plist_content("a & b & c");
        assert!(content.contains("<string>a &amp; b &amp; c</string>"));
    }
}
