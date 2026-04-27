#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s MATTER_ID [QUERY]\n' "$0" >&2
}

fail() {
  local message="$1"
  if [[ -n "${STATUS_PATH:-}" && -d "${EXPORTS_DIR:-}" ]]; then
    write_status "Error" "$message"
  fi
  printf 'error: %s\n' "$message" >&2
  exit 1
}

resolve_path() {
  realpath -m "$1"
}

assert_not_openclaw_repo_path() {
  local label="$1"
  local path="$2"
  local resolved
  resolved="$(resolve_path "$path")"
  case "$resolved" in
    /home/openclaw|/home/openclaw/*)
      fail "$label must not resolve inside /home/openclaw: $resolved"
      ;;
  esac
}

write_status() {
  local state="$1"
  local message="$2"
  mkdir -p "$EXPORTS_DIR"
  {
    printf '# OpenClaw Legal Primary Node Status\n\n'
    printf 'Status: %s\n\n' "$state"
    printf '%s\n\n' "$message"
    printf 'Matter ID: `%s`\n' "$MATTER_ID"
    printf 'Query: `%s`\n\n' "$QUERY"
    printf 'Output locations:\n'
    printf '%s\n' "- Reports: \`$EXPORTS_DIR/reports/\`"
    printf '%s\n' "- Review packets: \`$EXPORTS_DIR/review_packets/\`"
    printf '%s\n' "- Support diagnostics: \`$EXPORTS_DIR/support/\`"
    printf '%s\n\n' "- Alternative methods JSON: \`$EXPORTS_DIR/alternative_methods.json\`"
    printf 'Last updated: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } > "$STATUS_PATH"
}

copy_outputs() {
  mkdir -p "$EXPORTS_DIR/reports" "$EXPORTS_DIR/review_packets" "$EXPORTS_DIR/support"

  find "$EXPORTS_DIR/reports" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  find "$EXPORTS_DIR/review_packets" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  find "$EXPORTS_DIR/support" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

  shopt -s nullglob
  local report
  for report in "$MATTER_ROOT"/exports/*.md; do
    cp -a "$report" "$EXPORTS_DIR/reports/"
  done

  local packet
  for packet in "$MATTER_ROOT"/exports/review-packet-*; do
    if [[ -d "$packet" ]]; then
      cp -a "$packet" "$EXPORTS_DIR/review_packets/"
    fi
  done
  shopt -u nullglob

  if [[ -d "$MATTER_ROOT/support" ]]; then
    cp -a "$MATTER_ROOT/support/." "$EXPORTS_DIR/support/"
  fi
}

on_error() {
  local exit_code=$?
  if [[ $exit_code -ne 0 && "${STATUS_DONE:-0}" -ne 1 ]]; then
    write_status "Error" "Processing stopped before completion. No source text is written to this status file."
  fi
}
trap on_error EXIT

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 2
fi

MATTER_ID="$1"
QUERY="${2:-test}"
STATUS_DONE=0

if [[ ! "$MATTER_ID" =~ ^[A-Za-z0-9_-]+$ ]]; then
  fail "matter_id must contain only letters, numbers, underscores, and hyphens"
fi

VAULT_ROOT=/mnt/c/OpenClawLegalPrivate/vault
MATTER_ROOT="$VAULT_ROOT/$MATTER_ID"
STAGING_DIR=/mnt/c/OpenClawLegalPrivate/staging/$MATTER_ID
EXPORTS_DIR=/mnt/c/OpenClawLegalPrivate/exports/$MATTER_ID
STATUS_PATH="$EXPORTS_DIR/03_STATUS.md"
ALTERNATIVE_METHODS_PATH="$EXPORTS_DIR/alternative_methods.json"

assert_not_openclaw_repo_path "VAULT_ROOT" "$VAULT_ROOT"
assert_not_openclaw_repo_path "MATTER_ROOT" "$MATTER_ROOT"
assert_not_openclaw_repo_path "STAGING_DIR" "$STAGING_DIR"
assert_not_openclaw_repo_path "EXPORTS_DIR" "$EXPORTS_DIR"

mkdir -p "$VAULT_ROOT" "$STAGING_DIR" "$EXPORTS_DIR"
write_status "Processing" "Primary node processing started. Source filenames and source text are not listed here."

if [[ -f "$MATTER_ROOT/manifest.json" ]]; then
  :
elif [[ -e "$MATTER_ROOT" ]]; then
  fail "matter root exists but manifest.json is missing; refusing to continue"
else
  python3 -m legal.cli create-matter \
    --vault-root "$VAULT_ROOT" \
    --root "$MATTER_ROOT" \
    --matter-id "$MATTER_ID" \
    --display-name "$MATTER_ID" >/dev/null
fi

python3 -m legal.cli import-staging \
  --vault-root "$VAULT_ROOT" \
  --root "$MATTER_ROOT" \
  --staging-dir "$STAGING_DIR" \
  --lane real-matter >/dev/null

python3 -m legal.cli extract-all \
  --vault-root "$VAULT_ROOT" \
  --root "$MATTER_ROOT" >/dev/null

python3 -m legal.cli search \
  --vault-root "$VAULT_ROOT" \
  --root "$MATTER_ROOT" \
  --query "$QUERY" >/dev/null

python3 -m legal.cli report \
  --vault-root "$VAULT_ROOT" \
  --root "$MATTER_ROOT" \
  --query "$QUERY" >/dev/null

python3 -m legal.cli review-packet \
  --vault-root "$VAULT_ROOT" \
  --root "$MATTER_ROOT" >/dev/null

python3 -m legal.cli support-packet \
  --vault-root "$VAULT_ROOT" \
  --root "$MATTER_ROOT" >/dev/null

python3 -m legal.cli alternative-methods \
  --vault-root "$VAULT_ROOT" \
  --root "$MATTER_ROOT" > "$ALTERNATIVE_METHODS_PATH"

copy_outputs
write_status "Done" "Primary node processing complete. Review copied outputs from the workstation vault."
STATUS_DONE=1