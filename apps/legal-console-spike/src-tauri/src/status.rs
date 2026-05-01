use serde::Serialize;
use std::{
    env, fs,
    path::{Component, Path, PathBuf},
};

const PRODUCT_REPO_ROOT: &str = "/home/openclaw";
const MAX_STATUS_BYTES: u64 = 32 * 1024;

const WORKSTATION_STATUS_PATH: &str =
    "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/03_WORKSTATION_STATUS.md";
const PRIMARY_STATUS_PATH: &str =
    "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/PRIMARY_NODE_STATUS.md";
const INTAKE_FOLDER_PATH: &str = "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE";
const OUTPUT_GUIDE_PATH: &str =
    "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/00_OPEN_THIS_FIRST.md";

const WORKSTATION_STATUS_SUFFIX: &str =
    "OpenClawLegalPrivate/Matter_Alpha_Workspace/03_WORKSTATION_STATUS.md";
const PRIMARY_STATUS_SUFFIX: &str =
    "OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/PRIMARY_NODE_STATUS.md";
const INTAKE_FOLDER_SUFFIX: &str = "OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE";
const OUTPUT_GUIDE_SUFFIX: &str =
    "OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/00_OPEN_THIS_FIRST.md";

const WORKSTATION_STATES: &[&str] = &[
    "Ready",
    "Checking config",
    "Files found",
    "Sending files to primary node",
    "Processing on primary node",
    "Pulling outputs back",
    "Done",
    "Error",
];

const PRIMARY_STATES: &[&str] = &["Processing", "Done", "Error"];

#[derive(Debug, Serialize)]
pub struct StatusSnapshot {
    workstation_status_present: bool,
    workstation_state: String,
    workstation_last_updated: Option<String>,
    primary_status_present: bool,
    primary_state: String,
    primary_last_updated: Option<String>,
    intake_folder_present: bool,
    intake_target_kind: String,
    outputs_guide_present: bool,
    scaffold_ready: bool,
    processing_state: String,
    gui_bridge_state: String,
    boundary_state: String,
    warnings: Vec<String>,
    errors: Vec<String>,
}

#[derive(Debug)]
struct ParsedStatus {
    present: bool,
    state: String,
    last_updated: Option<String>,
    warnings: Vec<String>,
    errors: Vec<String>,
}

#[derive(Debug)]
struct FixedTargetStatus {
    present: bool,
    target_kind: String,
    warnings: Vec<String>,
    errors: Vec<String>,
}

#[tauri::command]
pub fn get_status_snapshot() -> StatusSnapshot {
    let workstation = read_status_file(
        "workstation",
        WORKSTATION_STATUS_PATH,
        WORKSTATION_STATUS_SUFFIX,
        WORKSTATION_STATES,
    );
    let primary = read_status_file(
        "primary",
        PRIMARY_STATUS_PATH,
        PRIMARY_STATUS_SUFFIX,
        PRIMARY_STATES,
    );
    let intake = check_fixed_directory("intake", INTAKE_FOLDER_PATH, INTAKE_FOLDER_SUFFIX);
    let guide = check_output_guide();

    let mut warnings = Vec::new();
    warnings.extend(workstation.warnings.clone());
    warnings.extend(primary.warnings.clone());
    warnings.extend(intake.warnings.clone());
    warnings.extend(guide.1);

    let mut errors = Vec::new();
    errors.extend(workstation.errors.clone());
    errors.extend(primary.errors.clone());
    errors.extend(intake.errors.clone());
    errors.extend(guide.2);

    let has_errors = !errors.is_empty();
    let scaffold_ready = workstation.present
        && intake.present
        && intake.target_kind == "directory"
        && guide.0
        && !has_errors;
    let processing_state = derive_processing_state(&workstation, &primary, has_errors);

    let boundary_state = if has_errors {
        "error"
    } else if !warnings.is_empty() {
        "warning"
    } else {
        "safe"
    };

    StatusSnapshot {
        workstation_status_present: workstation.present,
        workstation_state: workstation.state,
        workstation_last_updated: workstation.last_updated,
        primary_status_present: primary.present,
        primary_state: primary.state,
        primary_last_updated: primary.last_updated,
        intake_folder_present: intake.present,
        intake_target_kind: intake.target_kind,
        outputs_guide_present: guide.0,
        scaffold_ready,
        processing_state,
        gui_bridge_state: "synthetic_only".to_string(),
        boundary_state: boundary_state.to_string(),
        warnings,
        errors,
    }
}

fn check_fixed_directory(label: &str, raw_path: &str, suffix: &str) -> FixedTargetStatus {
    let mut warnings = Vec::new();
    let mut errors = Vec::new();

    let path = match validate_fixed_path(raw_path, suffix) {
        Ok(path) => path,
        Err(error) => {
            errors.push(format!("{label}_{error}"));
            return FixedTargetStatus {
                present: false,
                target_kind: "unknown".to_string(),
                warnings,
                errors,
            };
        }
    };

    if !path.exists() {
        warnings.push(format!("{label}_folder_missing"));
        return FixedTargetStatus {
            present: false,
            target_kind: "missing".to_string(),
            warnings,
            errors,
        };
    }

    match fs::metadata(&path) {
        Ok(metadata) if metadata.is_dir() => FixedTargetStatus {
            present: true,
            target_kind: "directory".to_string(),
            warnings,
            errors,
        },
        Ok(_) => {
            errors.push(format!("{label}_folder_not_directory"));
            FixedTargetStatus {
                present: true,
                target_kind: "not_directory".to_string(),
                warnings,
                errors,
            }
        }
        Err(_) => {
            errors.push(format!("{label}_folder_metadata_failed"));
            FixedTargetStatus {
                present: true,
                target_kind: "unknown".to_string(),
                warnings,
                errors,
            }
        }
    }
}

fn read_status_file(
    label: &str,
    raw_path: &str,
    suffix: &str,
    allowed_states: &[&str],
) -> ParsedStatus {
    let mut warnings = Vec::new();
    let mut errors = Vec::new();

    let path = match validate_fixed_path(raw_path, suffix) {
        Ok(path) => path,
        Err(error) => {
            errors.push(format!("{label}_{error}"));
            return ParsedStatus {
                present: false,
                state: "Unknown".to_string(),
                last_updated: None,
                warnings,
                errors,
            };
        }
    };

    if !path.exists() {
        warnings.push(format!("{label}_status_file_missing"));
        return ParsedStatus {
            present: false,
            state: "Unknown".to_string(),
            last_updated: None,
            warnings,
            errors,
        };
    }

    let metadata = match fs::metadata(&path) {
        Ok(metadata) => metadata,
        Err(_) => {
            errors.push(format!("{label}_status_metadata_failed"));
            return ParsedStatus {
                present: true,
                state: "Unknown".to_string(),
                last_updated: None,
                warnings,
                errors,
            };
        }
    };

    if !metadata.is_file() {
        errors.push(format!("{label}_status_not_a_file"));
        return ParsedStatus {
            present: true,
            state: "Unknown".to_string(),
            last_updated: None,
            warnings,
            errors,
        };
    }

    if metadata.len() > MAX_STATUS_BYTES {
        errors.push(format!("{label}_status_file_too_large"));
        return ParsedStatus {
            present: true,
            state: "Unknown".to_string(),
            last_updated: None,
            warnings,
            errors,
        };
    }

    let content = match fs::read_to_string(&path) {
        Ok(content) => content,
        Err(_) => {
            errors.push(format!("{label}_status_read_failed"));
            return ParsedStatus {
                present: true,
                state: "Unknown".to_string(),
                last_updated: None,
                warnings,
                errors,
            };
        }
    };

    let (state, last_updated) = parse_status_lines(&content, allowed_states);
    if state == "Unknown" {
        warnings.push(format!("{label}_status_unknown"));
    }

    ParsedStatus {
        present: true,
        state,
        last_updated,
        warnings,
        errors,
    }
}

fn check_output_guide() -> (bool, Vec<String>, Vec<String>) {
    let mut warnings = Vec::new();
    let mut errors = Vec::new();

    let path = match validate_fixed_path(OUTPUT_GUIDE_PATH, OUTPUT_GUIDE_SUFFIX) {
        Ok(path) => path,
        Err(error) => {
            errors.push(format!("outputs_guide_{error}"));
            return (false, warnings, errors);
        }
    };

    if !path.exists() {
        warnings.push("outputs_guide_missing".to_string());
        return (false, warnings, errors);
    }

    match fs::metadata(&path) {
        Ok(metadata) if metadata.is_file() => (true, warnings, errors),
        Ok(_) => {
            errors.push("outputs_guide_not_a_file".to_string());
            (false, warnings, errors)
        }
        Err(_) => {
            errors.push("outputs_guide_metadata_failed".to_string());
            (false, warnings, errors)
        }
    }
}

fn derive_processing_state(
    workstation: &ParsedStatus,
    primary: &ParsedStatus,
    has_errors: bool,
) -> String {
    if has_errors || workstation.state == "Error" || primary.state == "Error" {
        return "error".to_string();
    }

    if primary.present {
        return "primary_returned".to_string();
    }

    match workstation.state.as_str() {
        "Ready" => "not_run".to_string(),
        "Checking config"
        | "Files found"
        | "Sending files to primary node"
        | "Processing on primary node"
        | "Pulling outputs back" => "workstation_progress".to_string(),
        "Error" => "error".to_string(),
        _ => "unknown".to_string(),
    }
}

fn validate_fixed_path(raw_path: &str, suffix: &str) -> Result<PathBuf, &'static str> {
    let expanded = expand_home(raw_path)?;

    if has_traversal_component(&expanded) {
        return Err("path_traversal_rejected");
    }
    if !expanded.ends_with(Path::new(suffix)) {
        return Err("fixed_path_mismatch");
    }
    reject_forbidden_path(&expanded)?;

    let resolved = if expanded.exists() {
        fs::canonicalize(&expanded).map_err(|_| "path_canonicalize_failed")?
    } else {
        canonicalize_existing_ancestor(&expanded)?
    };
    reject_forbidden_path(&resolved)?;

    Ok(expanded)
}

fn expand_home(raw_path: &str) -> Result<PathBuf, &'static str> {
    if raw_path == "~" {
        return home_dir();
    }

    if let Some(rest) = raw_path.strip_prefix("~/") {
        return Ok(home_dir()?.join(rest));
    }

    Ok(PathBuf::from(raw_path))
}

fn home_dir() -> Result<PathBuf, &'static str> {
    env::var_os("HOME")
        .filter(|home| !home.is_empty())
        .map(PathBuf::from)
        .ok_or("home_not_available")
}

fn canonicalize_existing_ancestor(path: &Path) -> Result<PathBuf, &'static str> {
    let mut current = path.parent().ok_or("path_parent_missing")?;

    loop {
        if current.exists() {
            return fs::canonicalize(current).map_err(|_| "path_canonicalize_failed");
        }

        current = current.parent().ok_or("path_existing_parent_missing")?;
    }
}

fn has_traversal_component(path: &Path) -> bool {
    path.components()
        .any(|component| matches!(component, Component::ParentDir | Component::CurDir))
}

fn reject_forbidden_path(path: &Path) -> Result<(), &'static str> {
    if path.starts_with(PRODUCT_REPO_ROOT) {
        return Err("path_inside_product_repo");
    }

    let rendered = path.to_string_lossy();
    for marker in [
        "iCloud",
        "Dropbox",
        "OneDrive",
        "Google Drive",
        "OpenClaw_Watch",
        "Obsidian Sync",
    ] {
        if rendered.contains(marker) {
            return Err("cloud_or_watch_path_rejected");
        }
    }

    Ok(())
}

fn parse_status_lines(content: &str, allowed_states: &[&str]) -> (String, Option<String>) {
    let mut status = "Unknown".to_string();
    let mut last_updated = None;

    for line in content.lines() {
        if let Some(value) = line.strip_prefix("Status:") {
            status = normalize_state(value.trim(), allowed_states);
        } else if let Some(value) = line.strip_prefix("Last updated:") {
            last_updated = sanitize_last_updated(value.trim());
        }
    }

    (status, last_updated)
}

fn normalize_state(value: &str, allowed_states: &[&str]) -> String {
    allowed_states
        .iter()
        .find(|state| **state == value)
        .copied()
        .unwrap_or("Unknown")
        .to_string()
}

fn sanitize_last_updated(value: &str) -> Option<String> {
    if value.is_empty() || value.len() > 80 {
        return None;
    }

    let allowed = value.chars().all(|character| {
        character.is_ascii_alphanumeric()
            || matches!(character, '-' | ':' | 'T' | 'Z' | '.' | '+' | ' ')
    });

    allowed.then(|| value.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_only_known_status_and_timestamp_lines() {
        let content = "# Title\nStatus: Ready\nMatter ID: should-not-leak\nLast updated: 2026-04-28T12:00:00Z\n";

        let parsed = parse_status_lines(content, WORKSTATION_STATES);

        assert_eq!(parsed.0, "Ready");
        assert_eq!(parsed.1.as_deref(), Some("2026-04-28T12:00:00Z"));
    }

    #[test]
    fn unknown_status_is_sanitized() {
        let parsed = parse_status_lines("Status: Contains private details\n", WORKSTATION_STATES);

        assert_eq!(parsed.0, "Unknown");
        assert_eq!(parsed.1, None);
    }

    #[test]
    fn rejects_traversal_components() {
        assert!(has_traversal_component(Path::new("/tmp/../openclaw")));
    }

    #[test]
    fn derives_not_run_from_ready_without_primary_status() {
        let workstation = ParsedStatus {
            present: true,
            state: "Ready".to_string(),
            last_updated: None,
            warnings: Vec::new(),
            errors: Vec::new(),
        };
        let primary = ParsedStatus {
            present: false,
            state: "Unknown".to_string(),
            last_updated: None,
            warnings: Vec::new(),
            errors: Vec::new(),
        };

        assert_eq!(
            derive_processing_state(&workstation, &primary, false),
            "not_run"
        );
    }

    #[test]
    fn derives_primary_returned_from_primary_status_presence() {
        let workstation = ParsedStatus {
            present: true,
            state: "Done".to_string(),
            last_updated: None,
            warnings: Vec::new(),
            errors: Vec::new(),
        };
        let primary = ParsedStatus {
            present: true,
            state: "Done".to_string(),
            last_updated: None,
            warnings: Vec::new(),
            errors: Vec::new(),
        };

        assert_eq!(
            derive_processing_state(&workstation, &primary, false),
            "primary_returned"
        );
    }
}
