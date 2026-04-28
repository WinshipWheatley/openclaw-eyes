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

For repeated dummy testing, double-click `Reset_Test_Run.command` before adding a fresh set of copied files.

This vault is for the private workstation control flow. Do not place it in iCloud, Dropbox, OneDrive, Google Drive, Obsidian Sync, or OpenClaw_Watch folders.
MARKDOWN

cat > "$STATUS_FILE" <<'MARKDOWN'
# OpenClaw Legal Status

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

DESKTOP_DIR="${OPENCLAW_DESKTOP_DIR:-$HOME/Desktop}"
SHORTCUT_PATH="$DESKTOP_DIR/OpenClaw Legal Matter Alpha"
mkdir -p "$DESKTOP_DIR"
if [[ ! -e "$SHORTCUT_PATH" ]]; then
  ln -s "$VAULT_DIR" "$SHORTCUT_PATH"
fi

printf 'OpenClaw Legal vault ready: %s\n' "$VAULT_DIR"
printf 'Desktop shortcut path: %s\n' "$SHORTCUT_PATH"