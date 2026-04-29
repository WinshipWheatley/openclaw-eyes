use serde::Serialize;
use std::{
    env,
    fs::{self, OpenOptions},
    io::{ErrorKind, Read, Write},
    path::{Component, Path, PathBuf},
};

const PRODUCT_REPO_ROOT: &str = "/home/openclaw";
const INTAKE_FOLDER_PATH: &str = "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE";
const VAULT_ROOT_SUFFIX: &str = "OpenClawLegalPrivate/Matter_Alpha_Workspace";
const INTAKE_FOLDER_SUFFIX: &str = "OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE";
const SYNTHETIC_FILENAME: &str = "openclaw_synthetic_dummy_test_file.txt";
const SYNTHETIC_CONTENT: &str =
    "OpenClaw Legal synthetic dummy test file. Query token: test. This is not matter data.";

#[derive(Debug, Serialize)]
pub struct SyntheticTestFileResult {
    created: bool,
    already_present: bool,
    target: String,
    synthetic_filename: String,
    boundary_state: String,
    warnings: Vec<String>,
    errors: Vec<String>,
}

#[tauri::command]
pub fn create_synthetic_test_file() -> SyntheticTestFileResult {
    let os = current_os();
    if os != "macos" {
        return blocked_result("unsupported_os");
    }

    let intake_folder = match validate_intake_folder() {
        Ok(path) => path,
        Err(error) => return blocked_result(error),
    };
    let synthetic_file = intake_folder.join(SYNTHETIC_FILENAME);

    match OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&synthetic_file)
    {
        Ok(mut file) => {
            if file.write_all(SYNTHETIC_CONTENT.as_bytes()).is_err() {
                return blocked_result("synthetic_file_write_failed");
            }

            SyntheticTestFileResult {
                created: true,
                already_present: false,
                target: "intake_folder".to_string(),
                synthetic_filename: SYNTHETIC_FILENAME.to_string(),
                boundary_state: "safe".to_string(),
                warnings: Vec::new(),
                errors: Vec::new(),
            }
        }
        Err(error) if error.kind() == ErrorKind::AlreadyExists => {
            match existing_synthetic_matches(&synthetic_file) {
                Ok(true) => SyntheticTestFileResult {
                    created: false,
                    already_present: true,
                    target: "intake_folder".to_string(),
                    synthetic_filename: SYNTHETIC_FILENAME.to_string(),
                    boundary_state: "warning".to_string(),
                    warnings: vec!["synthetic_file_already_present".to_string()],
                    errors: Vec::new(),
                },
                Ok(false) => {
                    blocked_result("synthetic_file_already_exists_with_unexpected_content")
                }
                Err(error) => blocked_result(error),
            }
        }
        Err(_) => blocked_result("synthetic_file_create_failed"),
    }
}

fn blocked_result(error: &str) -> SyntheticTestFileResult {
    SyntheticTestFileResult {
        created: false,
        already_present: false,
        target: "intake_folder".to_string(),
        synthetic_filename: SYNTHETIC_FILENAME.to_string(),
        boundary_state: "error".to_string(),
        warnings: Vec::new(),
        errors: vec![error.to_string()],
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

fn existing_synthetic_matches(path: &Path) -> Result<bool, &'static str> {
    let metadata = fs::metadata(path).map_err(|_| "synthetic_file_metadata_failed")?;
    if !metadata.is_file() {
        return Err("synthetic_target_not_file");
    }

    if metadata.len() != SYNTHETIC_CONTENT.len() as u64 {
        return Ok(false);
    }

    let mut file = fs::File::open(path).map_err(|_| "synthetic_file_read_failed")?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)
        .map_err(|_| "synthetic_file_read_failed")?;

    Ok(bytes == SYNTHETIC_CONTENT.as_bytes())
}

fn validate_intake_folder() -> Result<PathBuf, &'static str> {
    let home = home_dir()?;
    let expanded = expand_home(INTAKE_FOLDER_PATH, &home)?;

    if has_traversal_component(&expanded) {
        return Err("path_traversal_rejected");
    }
    if !expanded.ends_with(Path::new(INTAKE_FOLDER_SUFFIX)) {
        return Err("fixed_path_mismatch");
    }
    reject_forbidden_path(&expanded)?;

    if !expanded.exists() {
        return Err("intake_folder_missing");
    }

    reject_fixed_path_symlinks(&home)?;

    let metadata = fs::metadata(&expanded).map_err(|_| "path_canonicalize_failed")?;
    if !metadata.is_dir() {
        return Err("intake_target_not_directory");
    }

    let vault_root = home.join(VAULT_ROOT_SUFFIX);
    let canonical_vault_root =
        fs::canonicalize(&vault_root).map_err(|_| "path_canonicalize_failed")?;
    let canonical_intake = fs::canonicalize(&expanded).map_err(|_| "path_canonicalize_failed")?;

    reject_forbidden_path(&canonical_vault_root)?;
    reject_forbidden_path(&canonical_intake)?;
    if !canonical_intake.starts_with(&canonical_vault_root) {
        return Err("fixed_path_mismatch");
    }

    Ok(canonical_intake)
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
        home.join(INTAKE_FOLDER_SUFFIX),
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
    fn keeps_synthetic_filename_fixed() {
        assert_eq!(SYNTHETIC_FILENAME, "openclaw_synthetic_dummy_test_file.txt");
    }

    #[test]
    fn keeps_synthetic_content_fixed() {
        assert_eq!(
            SYNTHETIC_CONTENT,
            "OpenClaw Legal synthetic dummy test file. Query token: test. This is not matter data."
        );
    }

    #[test]
    fn detects_traversal_components() {
        assert!(has_traversal_component(Path::new(
            "/tmp/../OpenClawLegalPrivate"
        )));
    }

    #[test]
    fn keeps_intake_suffix_exact() {
        let path = Path::new(
            "/Users/example/OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE",
        );

        assert!(path.ends_with(Path::new(INTAKE_FOLDER_SUFFIX)));
    }
}
