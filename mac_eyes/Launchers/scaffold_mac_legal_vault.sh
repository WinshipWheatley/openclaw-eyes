#!/usr/bin/env bash
set -euo pipefail

PRIVATE_ROOT="${OPENCLAW_LEGAL_PRIVATE_ROOT:-$HOME/OpenClawLegalPrivate}"
VAULT_DIR="$PRIVATE_ROOT/Matter_Alpha_Workspace"
DROP_DIR="$VAULT_DIR/01_DROP_FILES_HERE"
OUTPUTS_DIR="$VAULT_DIR/04_OUTPUTS"
CONFIG_DIR="$VAULT_DIR/.openclaw_config"
CONFIG_FILE="$CONFIG_DIR/matter_config.env"
STATUS_FILE="$VAULT_DIR/03_STATUS.md"
SUPPORT_REVIEW_FILE="$VAULT_DIR/05_SUPPORT_PACKET_REVIEW.md"
START_FILE="$VAULT_DIR/00_START_HERE.md"
RUN_COMMAND="$VAULT_DIR/Run_OpenClaw_Dry_Run.command"

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

1. Put copied test files in `01_DROP_FILES_HERE/`.
2. Edit `.openclaw_config/matter_config.env` and set `PC_SSH_TARGET`.
3. Double-click `Run_OpenClaw_Dry_Run.command`.
4. Read `03_STATUS.md` and review returned files in `04_OUTPUTS/`.

This vault is for the private workstation control flow. Do not place it in iCloud, Dropbox, OneDrive, Google Drive, Obsidian Sync, or OpenClaw_Watch folders.
MARKDOWN

cat > "$STATUS_FILE" <<'MARKDOWN'
# OpenClaw Legal Status

Status: Ready

Drop copied files into `01_DROP_FILES_HERE/`, configure `PC_SSH_TARGET`, then run `Run_OpenClaw_Dry_Run.command`.
MARKDOWN

cat > "$SUPPORT_REVIEW_FILE" <<'MARKDOWN'
# Support Packet Review

After a dry run, sanitized support diagnostics will be copied into `04_OUTPUTS/support/`.

Review support packets for status counts, file extensions, extractor names, and redacted reason categories. Source file contents and private absolute paths should not appear in support packet JSON.
MARKDOWN

cat > "$RUN_COMMAND" <<'COMMAND'
#!/usr/bin/env bash
set -euo pipefail

VAULT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
CONFIG_FILE="$VAULT_DIR/.openclaw_config/matter_config.env"
DROP_DIR="$VAULT_DIR/01_DROP_FILES_HERE"
STATUS_FILE="$VAULT_DIR/03_STATUS.md"
OUTPUTS_DIR="$VAULT_DIR/04_OUTPUTS"
STATUS_FINAL=0

write_status() {
  local state="$1"
  local message="$2"
  {
    printf '# OpenClaw Legal Status\n\n'
    printf 'Status: %s\n\n' "$state"
    printf '%s\n\n' "$message"
    printf 'Last updated: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } > "$STATUS_FILE"
}

finish_error() {
  local exit_code=$?
  if [[ $exit_code -ne 0 && "$STATUS_FINAL" -ne 1 ]]; then
    write_status "Error" "Dry run stopped before completion. Check SSH connectivity and the PC runner status."
  fi
}
trap finish_error EXIT

fail_with_status() {
  local message="$1"
  write_status "Error" "$message"
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
  fail_with_status "Refusing to run because this vault appears to be in a forbidden folder: $reason. Move it to ~/OpenClawLegalPrivate/Matter_Alpha_Workspace."
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  fail_with_status "Missing .openclaw_config/matter_config.env. Re-run the scaffold launcher."
fi

set -a
source "$CONFIG_FILE"
set +a

: "${PC_SSH_TARGET:=}"
: "${PC_REPO_ROOT:=/home/openclaw}"
: "${PC_STAGING_DIR:=/mnt/c/OpenClawLegalPrivate/staging/matter_alpha}"
: "${PC_EXPORTS_DIR:=/mnt/c/OpenClawLegalPrivate/exports/matter_alpha}"
: "${MATTER_ID:=matter_alpha}"
: "${QUERY:=test}"

write_status "Ready" "Configuration loaded. Preparing to transfer copied files."

if [[ -z "$PC_SSH_TARGET" ]]; then
  fail_with_status "PC_SSH_TARGET is not configured. Edit .openclaw_config/matter_config.env and set it to a reachable SSH target such as user@pc-host."
fi
command -v rsync >/dev/null 2>&1 || fail_with_status "rsync is required on the Mac workstation."
command -v ssh >/dev/null 2>&1 || fail_with_status "ssh is required on the Mac workstation."

remote_repo="$(shell_quote "$PC_REPO_ROOT")"
remote_staging="$(shell_quote "$PC_STAGING_DIR")"
remote_exports="$(shell_quote "$PC_EXPORTS_DIR")"
remote_matter="$(shell_quote "$MATTER_ID")"
remote_query="$(shell_quote "$QUERY")"

write_status "Transferring" "Copying the drop-folder contents to the primary node. File names and contents are not written to this status file."
ssh "$PC_SSH_TARGET" "mkdir -p $remote_staging $remote_exports"
rsync -a --quiet "$DROP_DIR/" "${PC_SSH_TARGET}:${PC_STAGING_DIR%/}/"

write_status "Processing" "The primary node is importing, extracting, searching, and preparing outputs."
ssh "$PC_SSH_TARGET" "cd $remote_repo && bash scripts/run_legal_pipeline_v0.sh $remote_matter $remote_query"

write_status "Pulling outputs" "Copying generated reports, packets, and status files back to this vault."
mkdir -p "$OUTPUTS_DIR"
rsync -a --quiet "${PC_SSH_TARGET}:${PC_EXPORTS_DIR%/}/" "$OUTPUTS_DIR/"

write_status "Done" "Dry run complete. Review returned files in 04_OUTPUTS/."
STATUS_FINAL=1
COMMAND

chmod 700 "$RUN_COMMAND"

DESKTOP_DIR="${OPENCLAW_DESKTOP_DIR:-$HOME/Desktop}"
SHORTCUT_PATH="$DESKTOP_DIR/OpenClaw Legal Matter Alpha"
mkdir -p "$DESKTOP_DIR"
if [[ ! -e "$SHORTCUT_PATH" ]]; then
  ln -s "$VAULT_DIR" "$SHORTCUT_PATH"
fi

printf 'OpenClaw Legal vault ready: %s\n' "$VAULT_DIR"
printf 'Desktop shortcut path: %s\n' "$SHORTCUT_PATH"