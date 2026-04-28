#!/usr/bin/env bash
set -euo pipefail

PRIVATE_ROOT="${OPENCLAW_LEGAL_PRIVATE_ROOT:-$HOME/OpenClawLegalPrivate}"
VAULT_DIR="$PRIVATE_ROOT/Matter_Alpha_Workspace"
DROP_DIR="$VAULT_DIR/01_DROP_FILES_HERE"
OUTPUTS_DIR="$VAULT_DIR/04_OUTPUTS"
CONFIG_DIR="$VAULT_DIR/.openclaw_config"
CONFIG_FILE="$CONFIG_DIR/matter_config.env"
STATUS_FILE="$VAULT_DIR/03_WORKSTATION_STATUS.md"
OLD_STATUS_FILE="$VAULT_DIR/03_STATUS.md"
SUPPORT_REVIEW_FILE="$VAULT_DIR/05_SUPPORT_PACKET_REVIEW.md"
START_FILE="$VAULT_DIR/00_START_HERE.md"
OUTPUT_GUIDE_FILE="$OUTPUTS_DIR/00_OPEN_THIS_FIRST.md"
RUN_COMMAND="$VAULT_DIR/Run_OpenClaw_Dry_Run.command"
RESET_COMMAND="$VAULT_DIR/Reset_Test_Run.command"
RESET_ALL_COMMAND="$VAULT_DIR/Reset_All_Test_State.command"

forbidden_path_reason() {
  local path="$1"
  case "$path" in
    *iCloud*|*Dropbox*|*OneDrive*|*"Google Drive"*|*OpenClaw_Watch*|*"Obsidian Sync"*)
      printf '%s\n' "cloud_or_watch_folder"
      return 0
      ;;
  esac
  case "$path" in
    /home/openclaw|/home/openclaw/*)
      printf '%s\n' "product_repo_home"
      return 0
      ;;
  esac
  return 1
}

write_output_guide() {
  cat > "$OUTPUT_GUIDE_FILE" <<'MARKDOWN'
# Open This First

This folder contains outputs copied back from the primary node after a dry run.

- `reports/` = search reports for the configured query.
- `review_packets/` = attorney-facing packets that may include source-derived content.
- `support/` = sanitized diagnostics candidates. Inspect locally before sharing.
- `alternative_methods.json` = guidance for unsupported, no-text, or failed sources.
- `PRIMARY_NODE_STATUS.md` = processing status generated on the primary node.

Do not paste reports or review packets into external chats. Treat them as private matter material until a lawyer decides otherwise.

Use `Reset_Test_Run.command` for local workstation cleanup. Use `Reset_All_Test_State.command` only before dummy bridge tests when old primary-node results appear. Do not use the full reset on real matters.
MARKDOWN
}

resolved_vault="$VAULT_DIR"
case "$resolved_vault" in
  /*) ;;
  *) resolved_vault="$PWD/$resolved_vault" ;;
esac
if reason="$(forbidden_path_reason "$resolved_vault")"; then
  printf 'Refusing to create Legal control vault at forbidden path (%s): %s\n' "$reason" "$resolved_vault" >&2
  exit 1
fi

mkdir -p "$DROP_DIR" "$OUTPUTS_DIR" "$CONFIG_DIR"

if [[ -f "$OLD_STATUS_FILE" ]] && grep -q '^# OpenClaw Legal Status' "$OLD_STATUS_FILE"; then
  rm -f "$OLD_STATUS_FILE"
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  cat > "$CONFIG_FILE" <<'CONFIG'
PC_SSH_TARGET=""
PC_REPO_ROOT=/home/openclaw
PC_VAULT_ROOT=/mnt/c/OpenClawLegalPrivate/vault
PC_STAGING_DIR=/mnt/c/OpenClawLegalPrivate/staging/matter_alpha
PC_EXPORTS_DIR=/mnt/c/OpenClawLegalPrivate/exports/matter_alpha
MATTER_ID=matter_alpha
DISPLAY_NAME="Matter Alpha"
QUERY=test
CONFIG
fi

cat > "$START_FILE" <<'MARKDOWN'
# OpenClaw Legal Matter Alpha

1. Put copied files in `01_DROP_FILES_HERE/`.
2. Edit `.openclaw_config/matter_config.env` and set `PC_SSH_TARGET`.
3. Double-click `Run_OpenClaw_Dry_Run.command`.
4. Read `03_WORKSTATION_STATUS.md`.
5. Open `04_OUTPUTS/00_OPEN_THIS_FIRST.md`.

For repeated dummy testing, double-click `Reset_Test_Run.command` before adding a fresh set of copied files. This clears only the Mac-side drop and output folders.

If old dummy results still appear because the primary node has accumulated test state, double-click `Reset_All_Test_State.command`. It is test-only, asks for confirmation, and clears the configured PC-side staging, test matter vault, and exports for the configured matter. Do not use the full reset on real matters.

This vault is for the private workstation control flow. Do not place it in iCloud, Dropbox, OneDrive, Google Drive, Obsidian Sync, or OpenClaw_Watch folders.
MARKDOWN

cat > "$STATUS_FILE" <<'MARKDOWN'
# OpenClaw Legal Workstation Status

Status: Ready

Drop copied files into `01_DROP_FILES_HERE/`, configure `PC_SSH_TARGET`, then run `Run_OpenClaw_Dry_Run.command`.
MARKDOWN

write_output_guide

cat > "$SUPPORT_REVIEW_FILE" <<'MARKDOWN'
# Support Packet Review

After a dry run, sanitized support diagnostics will be copied into `04_OUTPUTS/support/`.

Review support packets for status counts, file extensions, extractor names, and redacted reason categories. Source file contents and private absolute paths should not appear in support packet JSON.

Support packets are diagnostics candidates. Inspect them locally before sharing anywhere outside the firm-controlled environment.
MARKDOWN

cat > "$RUN_COMMAND" <<'COMMAND'
#!/usr/bin/env bash
set -euo pipefail

VAULT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
CONFIG_FILE="$VAULT_DIR/.openclaw_config/matter_config.env"
DROP_DIR="$VAULT_DIR/01_DROP_FILES_HERE"
STATUS_FILE="$VAULT_DIR/03_WORKSTATION_STATUS.md"
OUTPUTS_DIR="$VAULT_DIR/04_OUTPUTS"
OUTPUT_GUIDE_FILE="$OUTPUTS_DIR/00_OPEN_THIS_FIRST.md"
STATUS_FINAL=0

write_status() {
  local state="$1"
  local message="$2"
  local next_action="${3:-}"
  {
    printf '# OpenClaw Legal Workstation Status\n\n'
    printf 'Status: %s\n\n' "$state"
    printf '%s\n\n' "$message"
    if [[ -n "$next_action" ]]; then
      printf 'Next action: %s\n\n' "$next_action"
    fi
    printf 'Last updated: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } > "$STATUS_FILE"
}

write_output_guide() {
  mkdir -p "$OUTPUTS_DIR"
  cat > "$OUTPUT_GUIDE_FILE" <<'MARKDOWN'
# Open This First

This folder contains outputs copied back from the primary node after a dry run.

- `reports/` = search reports for the configured query.
- `review_packets/` = attorney-facing packets that may include source-derived content.
- `support/` = sanitized diagnostics candidates. Inspect locally before sharing.
- `alternative_methods.json` = guidance for unsupported, no-text, or failed sources.
- `PRIMARY_NODE_STATUS.md` = processing status generated on the primary node.

Do not paste reports or review packets into external chats. Treat them as private matter material until a lawyer decides otherwise.

Use `Reset_Test_Run.command` for local workstation cleanup. Use `Reset_All_Test_State.command` only before dummy bridge tests when old primary-node results appear. Do not use the full reset on real matters.
MARKDOWN
}

finish_error() {
  local exit_code=$?
  if [[ $exit_code -ne 0 && "$STATUS_FINAL" -ne 1 ]]; then
    write_status "Error" "Dry run stopped before completion." "Check SSH connectivity, PC_SSH_TARGET, and 04_OUTPUTS/PRIMARY_NODE_STATUS.md if it exists."
  fi
}
trap finish_error EXIT

fail_with_status() {
  local message="$1"
  local next_action="${2:-Review the message above, correct the workstation setup, then run again.}"
  write_status "Error" "$message" "$next_action"
  STATUS_FINAL=1
  exit 1
}

forbidden_path_reason() {
  local path="$1"
  case "$path" in
    *iCloud*|*Dropbox*|*OneDrive*|*"Google Drive"*|*OpenClaw_Watch*|*"Obsidian Sync"*)
      printf '%s\n' "cloud_or_watch_folder"
      return 0
      ;;
  esac
  return 1
}

shell_quote() {
  printf '%q' "$1"
}

if reason="$(forbidden_path_reason "$VAULT_DIR")"; then
  fail_with_status "Refusing to run because this vault appears to be in a forbidden folder: $reason." "Move it to ~/OpenClawLegalPrivate/Matter_Alpha_Workspace, then run again."
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  fail_with_status "Missing .openclaw_config/matter_config.env." "Re-run the scaffold launcher."
fi

write_status "Checking config" "Reading workstation and primary-node settings." "If this fails, review .openclaw_config/matter_config.env."

set -a
source "$CONFIG_FILE"
set +a

: "${PC_SSH_TARGET:=}"
: "${PC_REPO_ROOT:=/home/openclaw}"
: "${PC_STAGING_DIR:=/mnt/c/OpenClawLegalPrivate/staging/matter_alpha}"
: "${PC_EXPORTS_DIR:=/mnt/c/OpenClawLegalPrivate/exports/matter_alpha}"
: "${MATTER_ID:=matter_alpha}"
: "${QUERY:=test}"

if [[ -z "$PC_SSH_TARGET" ]]; then
  fail_with_status "PC_SSH_TARGET is not configured." "Edit .openclaw_config/matter_config.env and set PC_SSH_TARGET to a reachable SSH target such as user@pc-host."
fi
command -v rsync >/dev/null 2>&1 || fail_with_status "rsync is required on the Mac workstation." "Install rsync or run from a shell that can find it."
command -v ssh >/dev/null 2>&1 || fail_with_status "ssh is required on the Mac workstation." "Install or enable SSH client support."

file_count="$(find "$DROP_DIR" -type f | wc -l | tr -d ' ')"
if [[ "$file_count" -eq 0 ]]; then
  fail_with_status "No copied files were found in 01_DROP_FILES_HERE/." "Add copied dummy or matter files there, then run again."
fi

write_status "Files found" "$file_count copied file(s) are ready to send. File names and contents are not written to this status file." "Keep this window open until the run finishes."

remote_repo="$(shell_quote "$PC_REPO_ROOT")"
remote_staging="$(shell_quote "$PC_STAGING_DIR")"
remote_exports="$(shell_quote "$PC_EXPORTS_DIR")"
remote_matter="$(shell_quote "$MATTER_ID")"
remote_query="$(shell_quote "$QUERY")"

write_status "Sending files to primary node" "Copying the drop-folder contents to the primary node. File names and contents are not written to this status file." "Wait for processing to begin."
ssh "$PC_SSH_TARGET" "mkdir -p $remote_staging $remote_exports"
rsync -a --quiet "$DROP_DIR/" "${PC_SSH_TARGET}:${PC_STAGING_DIR%/}/"

write_status "Processing on primary node" "The primary node is importing, extracting, searching, and preparing outputs." "Wait for outputs to return."
ssh "$PC_SSH_TARGET" "cd $remote_repo && bash scripts/run_legal_pipeline_v0.sh $remote_matter $remote_query"

write_status "Pulling outputs back" "Copying generated reports, packets, and status files back to this vault." "After this step, open 04_OUTPUTS/00_OPEN_THIS_FIRST.md."
mkdir -p "$OUTPUTS_DIR"
rm -f "$OUTPUTS_DIR/03_STATUS.md" "$OUTPUTS_DIR/PRIMARY_NODE_STATUS.md"
rsync -a --quiet "${PC_SSH_TARGET}:${PC_EXPORTS_DIR%/}/" "$OUTPUTS_DIR/"
write_output_guide

write_status "Done" "Dry run complete. Outputs are back in 04_OUTPUTS/." "Open 04_OUTPUTS/00_OPEN_THIS_FIRST.md."
STATUS_FINAL=1
COMMAND

chmod 700 "$RUN_COMMAND"

cat > "$RESET_COMMAND" <<'COMMAND'
#!/usr/bin/env bash
set -euo pipefail

VAULT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
DROP_DIR="$VAULT_DIR/01_DROP_FILES_HERE"
OUTPUTS_DIR="$VAULT_DIR/04_OUTPUTS"
STATUS_FILE="$VAULT_DIR/03_WORKSTATION_STATUS.md"
OUTPUT_GUIDE_FILE="$OUTPUTS_DIR/00_OPEN_THIS_FIRST.md"

write_status() {
  local state="$1"
  local message="$2"
  local next_action="${3:-}"
  {
    printf '# OpenClaw Legal Workstation Status\n\n'
    printf 'Status: %s\n\n' "$state"
    printf '%s\n\n' "$message"
    if [[ -n "$next_action" ]]; then
      printf 'Next action: %s\n\n' "$next_action"
    fi
    printf 'Last updated: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } > "$STATUS_FILE"
}

write_output_guide() {
  mkdir -p "$OUTPUTS_DIR"
  cat > "$OUTPUT_GUIDE_FILE" <<'MARKDOWN'
# Open This First

This folder contains outputs copied back from the primary node after a dry run.

- `reports/` = search reports for the configured query.
- `review_packets/` = attorney-facing packets that may include source-derived content.
- `support/` = sanitized diagnostics candidates. Inspect locally before sharing.
- `alternative_methods.json` = guidance for unsupported, no-text, or failed sources.
- `PRIMARY_NODE_STATUS.md` = processing status generated on the primary node.

Do not paste reports or review packets into external chats. Treat them as private matter material until a lawyer decides otherwise.

Use `Reset_Test_Run.command` for local workstation cleanup. Use `Reset_All_Test_State.command` only before dummy bridge tests when old primary-node results appear. Do not use the full reset on real matters.
MARKDOWN
}

safe_clear_directory() {
  local target="$1"
  case "$target" in
    "$VAULT_DIR"/*) ;;
    *)
      write_status "Error" "Reset refused to clear a path outside this vault." "Re-run the scaffold if the vault layout looks wrong."
      exit 1
      ;;
  esac
  mkdir -p "$target"
  find "$target" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
}

safe_clear_directory "$DROP_DIR"
safe_clear_directory "$OUTPUTS_DIR"
write_output_guide
write_status "Ready" "Test run reset complete. Local drop-folder and returned outputs were cleared. The primary-node vault was not deleted." "Drop a fresh copied test set into 01_DROP_FILES_HERE/, then run Run_OpenClaw_Dry_Run.command."
COMMAND

chmod 700 "$RESET_COMMAND"

cat > "$RESET_ALL_COMMAND" <<'COMMAND'
#!/usr/bin/env bash
set -euo pipefail

VAULT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
CONFIG_FILE="$VAULT_DIR/.openclaw_config/matter_config.env"
DROP_DIR="$VAULT_DIR/01_DROP_FILES_HERE"
OUTPUTS_DIR="$VAULT_DIR/04_OUTPUTS"
STATUS_FILE="$VAULT_DIR/03_WORKSTATION_STATUS.md"
OUTPUT_GUIDE_FILE="$OUTPUTS_DIR/00_OPEN_THIS_FIRST.md"
STATUS_FINAL=0

write_status() {
  local state="$1"
  local message="$2"
  local next_action="${3:-}"
  {
    printf '# OpenClaw Legal Workstation Status\n\n'
    printf 'Status: %s\n\n' "$state"
    printf '%s\n\n' "$message"
    if [[ -n "$next_action" ]]; then
      printf 'Next action: %s\n\n' "$next_action"
    fi
    printf 'Last updated: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } > "$STATUS_FILE"
}

write_output_guide() {
  mkdir -p "$OUTPUTS_DIR"
  cat > "$OUTPUT_GUIDE_FILE" <<'MARKDOWN'
# Open This First

This folder contains outputs copied back from the primary node after a dry run.

- `reports/` = search reports for the configured query.
- `review_packets/` = attorney-facing packets that may include source-derived content.
- `support/` = sanitized diagnostics candidates. Inspect locally before sharing.
- `alternative_methods.json` = guidance for unsupported, no-text, or failed sources.
- `PRIMARY_NODE_STATUS.md` = processing status generated on the primary node.

Do not paste reports or review packets into external chats. Treat them as private matter material until a lawyer decides otherwise.

Use `Reset_Test_Run.command` for local workstation cleanup. Use `Reset_All_Test_State.command` only before dummy bridge tests when old primary-node results appear. Do not use the full reset on real matters.
MARKDOWN
}

finish_error() {
  local exit_code=$?
  if [[ $exit_code -ne 0 && "$STATUS_FINAL" -ne 1 ]]; then
    write_status "Error" "Full test reset stopped before completion." "Check PC_SSH_TARGET, the configured matter ID, and the configured PC private paths."
  fi
}
trap finish_error EXIT

fail_with_status() {
  local message="$1"
  local next_action="${2:-Full reset did not run. Review the message above, correct the test reset setup, then run again.}"
  write_status "Error" "$message" "$next_action"
  STATUS_FINAL=1
  exit 1
}

shell_quote() {
  printf '%q' "$1"
}

is_safe_test_matter_id() {
  local matter_id_lower
  matter_id_lower="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$matter_id_lower" in
    matter_alpha|*test*|*dummy*|*synthetic*|*proof*|*fixture*|bridge_*)
      return 0
      ;;
  esac
  return 1
}

validate_pc_path_string() {
  local label="$1"
  local path="$2"
  if [[ -z "$path" ]]; then
    fail_with_status "$label is empty." "Full reset did not run. Restore the default /mnt/c/OpenClawLegalPrivate/... test paths or re-run the scaffold."
  fi
  case "$path" in
    /home/openclaw|/home/openclaw/*)
      fail_with_status "$label points inside /home/openclaw, which is code-only for this flow." "Full reset did not run. Use /mnt/c/OpenClawLegalPrivate/... private test paths."
      ;;
  esac
  case "$path" in
    /mnt/c/OpenClawLegalPrivate/*) ;;
    *)
      fail_with_status "$label must start with /mnt/c/OpenClawLegalPrivate/." "Full reset did not run. Use only the private WSL test root."
      ;;
  esac
  case "$path" in
    *'/../'*|*'/..'|*'/.'|*'/./'*)
      fail_with_status "$label contains traversal-like path components." "Full reset did not run. Use plain /mnt/c/OpenClawLegalPrivate/... paths."
      ;;
  esac
}

safe_clear_local_directory() {
  local target="$1"
  case "$target" in
    "$VAULT_DIR"/*) ;;
    *)
      fail_with_status "Local reset refused to clear a path outside this vault." "Re-run the scaffold if the vault layout looks wrong."
      ;;
  esac
  mkdir -p "$target"
  find "$target" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
}

confirm_full_reset() {
  if [[ "${OPENCLAW_CONFIRM_TEST_RESET:-}" == "RESET_TEST_STATE" ]]; then
    return 0
  fi
  printf '\nWARNING: This deletes PC-side test state for matter %s.\n' "$MATTER_ID"
  printf 'It clears configured staging, test matter vault, and exports on the primary node.\n'
  printf 'Do not use this on real matters. Type RESET to continue: '
  local answer=""
  read -r answer
  if [[ "$answer" != "RESET" ]]; then
    fail_with_status "Full test reset was cancelled." "No PC-side reset was performed."
  fi
}

if [[ ! -f "$CONFIG_FILE" ]]; then
  fail_with_status "Missing .openclaw_config/matter_config.env." "Re-run the scaffold launcher."
fi

write_status "Checking config" "Preparing full test reset. This command is for dummy bridge testing only." "Do not use this reset on real matters."

set -a
source "$CONFIG_FILE"
set +a

PC_SSH_TARGET="${PC_SSH_TARGET-}"
PC_VAULT_ROOT="${PC_VAULT_ROOT-}"
PC_STAGING_DIR="${PC_STAGING_DIR-}"
PC_EXPORTS_DIR="${PC_EXPORTS_DIR-}"
MATTER_ID="${MATTER_ID-}"

if [[ -z "$MATTER_ID" ]]; then
  fail_with_status "MATTER_ID is empty." "Full reset did not run. Set MATTER_ID to matter_alpha or another clearly dummy/test matter ID."
fi
if [[ ! "$MATTER_ID" =~ ^[A-Za-z0-9_-]+$ ]]; then
  fail_with_status "MATTER_ID contains unsafe characters." "Full reset did not run. Use only letters, numbers, underscores, and hyphens."
fi
if ! is_safe_test_matter_id "$MATTER_ID"; then
  if [[ "${OPENCLAW_CONFIRM_UNSAFE_TEST_RESET:-}" != "RESET_UNSAFE_TEST_STATE" ]]; then
    fail_with_status "MATTER_ID does not look like dummy/test state." "Full reset did not run. Use matter_alpha or a matter ID containing test, dummy, synthetic, proof, fixture, or bridge_."
  fi
fi
if [[ -z "$PC_SSH_TARGET" ]]; then
  fail_with_status "PC_SSH_TARGET is not configured." "Edit .openclaw_config/matter_config.env and set PC_SSH_TARGET to a reachable SSH target before full reset."
fi

PC_MATTER_ROOT="${PC_VAULT_ROOT%/}/$MATTER_ID"
validate_pc_path_string "PC_STAGING_DIR" "$PC_STAGING_DIR"
validate_pc_path_string "PC_VAULT_ROOT" "$PC_VAULT_ROOT"
validate_pc_path_string "PC matter root" "$PC_MATTER_ROOT"
validate_pc_path_string "PC_EXPORTS_DIR" "$PC_EXPORTS_DIR"
command -v ssh >/dev/null 2>&1 || fail_with_status "ssh is required on the Mac workstation." "Install or enable SSH client support."

confirm_full_reset

write_status "Resetting test state" "Clearing local drop/output folders and configured PC-side dummy test state. File names and contents are not written to this status file." "Wait for the reset to finish."
safe_clear_local_directory "$DROP_DIR"
safe_clear_local_directory "$OUTPUTS_DIR"
write_output_guide

remote_matter="$(shell_quote "$MATTER_ID")"
remote_staging="$(shell_quote "$PC_STAGING_DIR")"
remote_vault="$(shell_quote "$PC_VAULT_ROOT")"
remote_exports="$(shell_quote "$PC_EXPORTS_DIR")"

ssh "$PC_SSH_TARGET" "MATTER_ID=$remote_matter PC_STAGING_DIR=$remote_staging PC_VAULT_ROOT=$remote_vault PC_EXPORTS_DIR=$remote_exports bash -s" <<'REMOTE'
set -euo pipefail

fail_remote() {
  printf 'remote reset refused\n' >&2
  exit 70
}

validate_remote_path() {
  local path="$1"
  [[ -n "$path" ]] || fail_remote
  local resolved
  resolved="$(realpath -m "$path")"
  case "$resolved" in
    /home/openclaw|/home/openclaw/*)
      fail_remote
      ;;
  esac
  case "$resolved" in
    /mnt/c/OpenClawLegalPrivate/*) ;;
    *) fail_remote ;;
  esac
}

[[ -n "$MATTER_ID" ]] || fail_remote
[[ "$MATTER_ID" =~ ^[A-Za-z0-9_-]+$ ]] || fail_remote
PC_MATTER_ROOT="${PC_VAULT_ROOT%/}/$MATTER_ID"
validate_remote_path "$PC_STAGING_DIR"
validate_remote_path "$PC_VAULT_ROOT"
validate_remote_path "$PC_MATTER_ROOT"
validate_remote_path "$PC_EXPORTS_DIR"

rm -rf -- "$PC_STAGING_DIR" "$PC_MATTER_ROOT" "$PC_EXPORTS_DIR"
mkdir -p "$PC_STAGING_DIR" "$PC_EXPORTS_DIR"
REMOTE

write_output_guide
write_status "Ready" "Full test reset complete. Local drop/output folders and configured PC-side dummy test state were cleared." "Drop a fresh copied test set into 01_DROP_FILES_HERE/, then run Run_OpenClaw_Dry_Run.command."
STATUS_FINAL=1
COMMAND

chmod 700 "$RESET_ALL_COMMAND"

DESKTOP_DIR="${OPENCLAW_DESKTOP_DIR:-$HOME/Desktop}"
SHORTCUT_PATH="$DESKTOP_DIR/OpenClaw Legal Matter Alpha"
mkdir -p "$DESKTOP_DIR"
if [[ ! -e "$SHORTCUT_PATH" ]]; then
  ln -s "$VAULT_DIR" "$SHORTCUT_PATH"
fi

printf 'OpenClaw Legal vault ready: %s\n' "$VAULT_DIR"
printf 'Desktop shortcut path: %s\n' "$SHORTCUT_PATH"