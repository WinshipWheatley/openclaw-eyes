use serde::Serialize;
use std::{
    env, fs,
    path::{Component, Path, PathBuf},
    process::{Command, Stdio},
};

const PRODUCT_REPO_ROOT: &str = "/home/openclaw";
const MAX_CONFIG_BYTES: u64 = 16 * 1024;

const WORKSTATION_VAULT_PATH: &str = "~/OpenClawLegalPrivate/Matter_Alpha_Workspace";
const RUN_COMMAND_PATH: &str =
    "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/Run_OpenClaw_Dry_Run.command";
const CONFIG_FILE_PATH: &str =
    "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/.openclaw_config/matter_config.env";

const WORKSTATION_VAULT_SUFFIX: &str = "OpenClawLegalPrivate/Matter_Alpha_Workspace";
const RUN_COMMAND_SUFFIX: &str =
    "OpenClawLegalPrivate/Matter_Alpha_Workspace/Run_OpenClaw_Dry_Run.command";
const CONFIG_FILE_SUFFIX: &str =
    "OpenClawLegalPrivate/Matter_Alpha_Workspace/.openclaw_config/matter_config.env";

const BRIDGE_MODE: &str = "synthetic_only";
const FIXED_SYNTHETIC_MATTER_ID: &str = "bridge_synthetic_proof_20260430";
const FIXED_SYNTHETIC_QUERY: &str = "stress-omega-77";
const FIXED_PC_REPO_ROOT: &str = "/home/openclaw";
const FIXED_PC_VAULT_ROOT: &str = "/mnt/c/OpenClawLegalPrivate/vault";
const FIXED_PC_STAGING_DIR: &str =
    "/mnt/c/OpenClawLegalPrivate/staging/bridge_synthetic_proof_20260430";
const FIXED_PC_EXPORTS_DIR: &str =
    "/mnt/c/OpenClawLegalPrivate/exports/bridge_synthetic_proof_20260430";

#[derive(Debug, Serialize)]
pub struct SyntheticDryRunResult {
    started: bool,
    status: String,
    exit_code: Option<i32>,
    bridge_mode: String,
    boundary_state: String,
    warnings: Vec<String>,
    errors: Vec<String>,
}

#[derive(Debug)]
struct BridgePaths {
    vault_dir: PathBuf,
    run_command: PathBuf,
    config_file: PathBuf,
}

#[derive(Default)]
struct SyntheticBridgeConfig {
    pc_ssh_target: Option<String>,
    pc_repo_root: Option<String>,
    pc_vault_root: Option<String>,
    pc_staging_dir: Option<String>,
    pc_exports_dir: Option<String>,
    matter_id: Option<String>,
    query: Option<String>,
}

#[tauri::command]
pub fn run_synthetic_dry_run() -> SyntheticDryRunResult {
    let os = current_os();
    if os != "macos" {
        return failed_result(false, None, Vec::new(), vec!["unsupported_os".to_string()]);
    }

    let bridge_paths = match validate_bridge_paths() {
        Ok(paths) => paths,
        Err(error) => return failed_result(false, None, Vec::new(), vec![error.to_string()]),
    };

    let config_errors = validate_synthetic_config(&bridge_paths.config_file);
    if !config_errors.is_empty() {
        return failed_result(false, None, Vec::new(), config_errors);
    }

    let output = Command::new(&bridge_paths.run_command)
        .current_dir(&bridge_paths.vault_dir)
        .env("OPENCLAW_LEGAL_BRIDGE_MODE", BRIDGE_MODE)
        .env("MATTER_ID", FIXED_SYNTHETIC_MATTER_ID)
        .env("QUERY", FIXED_SYNTHETIC_QUERY)
        .env("PC_STAGING_DIR", FIXED_PC_STAGING_DIR)
        .env("PC_EXPORTS_DIR", FIXED_PC_EXPORTS_DIR)
        .stdin(Stdio::null())
        .output();

    let output = match output {
        Ok(output) => output,
        Err(_) => {
            return failed_result(
                false,
                None,
                Vec::new(),
                vec!["bridge_start_failed".to_string()],
            )
        }
    };

    let warnings = vec!["bridge_process_text_suppressed".to_string()];

    let exit_code = output.status.code();
    if output.status.success() {
        SyntheticDryRunResult {
            started: true,
            status: "succeeded".to_string(),
            exit_code,
            bridge_mode: BRIDGE_MODE.to_string(),
            boundary_state: "safe".to_string(),
            warnings,
            errors: Vec::new(),
        }
    } else {
        failed_result(
            true,
            exit_code,
            warnings,
            vec!["bridge_command_failed".to_string()],
        )
    }
}

fn failed_result(
    started: bool,
    exit_code: Option<i32>,
    warnings: Vec<String>,
    errors: Vec<String>,
) -> SyntheticDryRunResult {
    SyntheticDryRunResult {
        started,
        status: "failed".to_string(),
        exit_code,
        bridge_mode: BRIDGE_MODE.to_string(),
        boundary_state: "error".to_string(),
        warnings,
        errors,
    }
}

fn current_os() -> &'static str {
    if cfg!(target_os = "macos") {
        "macos"
    } else if cfg!(target_os = "windows") {
        "windows"
    } else if cfg!(target_os = "linux") {
        "linux"
    } else {
        "unsupported"
    }
}

fn validate_bridge_paths() -> Result<BridgePaths, &'static str> {
    let home = home_dir()?;
    let vault_dir = expand_home(WORKSTATION_VAULT_PATH, &home)?;
    let run_command = expand_home(RUN_COMMAND_PATH, &home)?;
    let config_file = expand_home(CONFIG_FILE_PATH, &home)?;

    validate_fixed_path(&vault_dir, WORKSTATION_VAULT_SUFFIX)?;
    validate_fixed_path(&run_command, RUN_COMMAND_SUFFIX)?;
    validate_fixed_path(&config_file, CONFIG_FILE_SUFFIX)?;
    reject_fixed_path_symlinks(&home)?;

    if !vault_dir.exists() {
        return Err("synthetic_bridge_vault_missing");
    }
    if !run_command.exists() {
        return Err("synthetic_bridge_command_missing");
    }
    if !config_file.exists() {
        return Err("synthetic_bridge_config_missing");
    }

    let vault_metadata = fs::metadata(&vault_dir).map_err(|_| "path_canonicalize_failed")?;
    if !vault_metadata.is_dir() {
        return Err("synthetic_bridge_vault_not_directory");
    }

    let command_metadata = fs::metadata(&run_command).map_err(|_| "path_canonicalize_failed")?;
    if !command_metadata.is_file() {
        return Err("synthetic_bridge_command_not_file");
    }

    let config_metadata = fs::metadata(&config_file).map_err(|_| "path_canonicalize_failed")?;
    if !config_metadata.is_file() {
        return Err("synthetic_bridge_config_not_file");
    }

    let canonical_vault = fs::canonicalize(&vault_dir).map_err(|_| "path_canonicalize_failed")?;
    let canonical_command =
        fs::canonicalize(&run_command).map_err(|_| "path_canonicalize_failed")?;
    let canonical_config =
        fs::canonicalize(&config_file).map_err(|_| "path_canonicalize_failed")?;

    reject_forbidden_path(&canonical_vault)?;
    reject_forbidden_path(&canonical_command)?;
    reject_forbidden_path(&canonical_config)?;
    if !canonical_command.starts_with(&canonical_vault)
        || !canonical_config.starts_with(&canonical_vault)
    {
        return Err("fixed_path_mismatch");
    }

    Ok(BridgePaths {
        vault_dir,
        run_command,
        config_file,
    })
}

fn validate_synthetic_config(config_file: &Path) -> Vec<String> {
    let metadata = match fs::metadata(config_file) {
        Ok(metadata) => metadata,
        Err(_) => return vec!["synthetic_bridge_config_read_failed".to_string()],
    };

    if metadata.len() > MAX_CONFIG_BYTES {
        return vec!["synthetic_bridge_config_too_large".to_string()];
    }

    let content = match fs::read_to_string(config_file) {
        Ok(content) => content,
        Err(_) => return vec!["synthetic_bridge_config_read_failed".to_string()],
    };
    let config = parse_synthetic_config(&content);
    let mut errors = Vec::new();

    if config
        .pc_ssh_target
        .as_deref()
        .map(str::trim)
        .unwrap_or("")
        .is_empty()
    {
        errors.push("pc_ssh_target_missing".to_string());
    }
    if config.pc_repo_root.as_deref() != Some(FIXED_PC_REPO_ROOT) {
        errors.push("pc_repo_root_mismatch".to_string());
    }
    if config.pc_vault_root.as_deref() != Some(FIXED_PC_VAULT_ROOT) {
        errors.push("pc_vault_root_mismatch".to_string());
    }
    if config.pc_staging_dir.as_deref() != Some(FIXED_PC_STAGING_DIR) {
        errors.push("synthetic_staging_path_mismatch".to_string());
    }
    if config.pc_exports_dir.as_deref() != Some(FIXED_PC_EXPORTS_DIR) {
        errors.push("synthetic_exports_path_mismatch".to_string());
    }
    if config.matter_id.as_deref() != Some(FIXED_SYNTHETIC_MATTER_ID) {
        errors.push("synthetic_matter_id_mismatch".to_string());
    }
    if config.query.as_deref() != Some(FIXED_SYNTHETIC_QUERY) {
        errors.push("synthetic_query_mismatch".to_string());
    }

    errors
}

fn parse_synthetic_config(content: &str) -> SyntheticBridgeConfig {
    let mut config = SyntheticBridgeConfig::default();

    for raw_line in content.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        let normalized_value = normalize_config_value(value);

        match key.trim() {
            "PC_SSH_TARGET" => config.pc_ssh_target = Some(normalized_value),
            "PC_REPO_ROOT" => config.pc_repo_root = Some(normalized_value),
            "PC_VAULT_ROOT" => config.pc_vault_root = Some(normalized_value),
            "PC_STAGING_DIR" => config.pc_staging_dir = Some(normalized_value),
            "PC_EXPORTS_DIR" => config.pc_exports_dir = Some(normalized_value),
            "MATTER_ID" => config.matter_id = Some(normalized_value),
            "QUERY" => config.query = Some(normalized_value),
            _ => {}
        }
    }

    config
}

fn normalize_config_value(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.len() >= 2
        && ((trimmed.starts_with('"') && trimmed.ends_with('"'))
            || (trimmed.starts_with('\'') && trimmed.ends_with('\'')))
    {
        trimmed[1..trimmed.len() - 1].to_string()
    } else {
        trimmed.to_string()
    }
}

fn validate_fixed_path(path: &Path, suffix: &str) -> Result<(), &'static str> {
    if has_traversal_component(path) {
        return Err("path_traversal_rejected");
    }
    if !path.ends_with(Path::new(suffix)) {
        return Err("fixed_path_mismatch");
    }
    reject_forbidden_path(path)
}

fn expand_home(raw_path: &str, home: &Path) -> Result<PathBuf, &'static str> {
    if let Some(rest) = raw_path.strip_prefix("~/") {
        return Ok(home.join(rest));
    }

    Err("fixed_path_mismatch")
}

fn home_dir() -> Result<PathBuf, &'static str> {
    env::var_os("HOME")
        .filter(|home| !home.is_empty())
        .map(PathBuf::from)
        .ok_or("home_not_available")
}

fn reject_fixed_path_symlinks(home: &Path) -> Result<(), &'static str> {
    for path in [
        home.join("OpenClawLegalPrivate"),
        home.join("OpenClawLegalPrivate/Matter_Alpha_Workspace"),
        home.join(RUN_COMMAND_SUFFIX),
        home.join(CONFIG_FILE_SUFFIX),
    ] {
        let metadata = fs::symlink_metadata(path).map_err(|_| "path_canonicalize_failed")?;
        if metadata.file_type().is_symlink() {
            return Err("path_symlink_rejected");
        }
    }

    Ok(())
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_fixed_synthetic_config_values() {
        let config = parse_synthetic_config(
            r#"
PC_SSH_TARGET="local-primary"
PC_REPO_ROOT=/home/openclaw
PC_VAULT_ROOT=/mnt/c/OpenClawLegalPrivate/vault
PC_STAGING_DIR=/mnt/c/OpenClawLegalPrivate/staging/bridge_synthetic_proof_20260430
PC_EXPORTS_DIR=/mnt/c/OpenClawLegalPrivate/exports/bridge_synthetic_proof_20260430
MATTER_ID=bridge_synthetic_proof_20260430
QUERY=stress-omega-77
"#,
        );

        assert_eq!(config.matter_id.as_deref(), Some(FIXED_SYNTHETIC_MATTER_ID));
        assert_eq!(config.query.as_deref(), Some(FIXED_SYNTHETIC_QUERY));
        assert_eq!(config.pc_staging_dir.as_deref(), Some(FIXED_PC_STAGING_DIR));
        assert_eq!(config.pc_exports_dir.as_deref(), Some(FIXED_PC_EXPORTS_DIR));
    }

    #[test]
    fn keeps_run_command_suffix_fixed() {
        let path = Path::new(
            "/Users/example/OpenClawLegalPrivate/Matter_Alpha_Workspace/Run_OpenClaw_Dry_Run.command",
        );

        assert!(path.ends_with(Path::new(RUN_COMMAND_SUFFIX)));
    }

    #[test]
    fn detects_traversal_components() {
        assert!(has_traversal_component(Path::new(
            "/tmp/../OpenClawLegalPrivate"
        )));
    }
}
