#!/usr/bin/env bash
set -u

warn_count=0
fail_count=0

report() {
  local level="$1"
  local code="$2"
  shift 2

  printf '%s  %s %s\n' "$level" "$code" "$*"

  case "$level" in
    WARN)
      warn_count=$((warn_count + 1))
      ;;
    FAIL)
      fail_count=$((fail_count + 1))
      ;;
  esac
}

path_error() {
  printf 'ERROR path_error %s\n' "$*" >&2
  exit 2
}

resolve_repo_root() {
  if [[ -n "${OPENCLAW_REPO_ROOT:-}" ]]; then
    printf '%s\n' "$OPENCLAW_REPO_ROOT"
    return 0
  fi

  local script_dir
  local from_script
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)" || return 1
  from_script="$(cd -- "$script_dir/.." >/dev/null 2>&1 && pwd)" || return 1

  if [[ -d "$from_script/systemd/user" || -d "$from_script/.config/systemd/user" ]]; then
    printf '%s\n' "$from_script"
    return 0
  fi

  printf '/home/openclaw\n'
}

repo_root="$(resolve_repo_root)" || path_error "could not resolve repo root"
if [[ ! -d "$repo_root" ]]; then
  path_error "repo root does not exist: $repo_root"
fi
repo_root="$(cd -- "$repo_root" >/dev/null 2>&1 && pwd)" || path_error "could not normalize repo root: $repo_root"

template_dir="$repo_root/systemd/user"
installed_dir="$repo_root/.config/systemd/user"

if [[ ! -d "$template_dir" ]]; then
  path_error "missing template directory: systemd/user"
fi
if [[ ! -d "$installed_dir" ]]; then
  path_error "missing installed unit directory: .config/systemd/user"
fi

render_template() {
  local template_path="$1"
  local replacement="$repo_root"
  replacement="${replacement//\\/\\\\}"
  replacement="${replacement//&/\\&}"
  sed "s|@REPO_ROOT@|$replacement|g" "$template_path"
}

is_known_installed_only() {
  case "$1" in
    openclaw-gateway.service|openclaw-drift-control-scan.service|openclaw-drift-control-scan.timer)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_openclaw_unit() {
  case "$1" in
    *.bak)
      return 1
      ;;
    openclaw-*|chief-*|cassandra-*|hermes-gateway.service)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

declare -A template_units=()
shopt -s nullglob

template_paths=("$template_dir"/*.in)
if (( ${#template_paths[@]} == 0 )); then
  report FAIL missing_templates "no repo templates found under systemd/user/*.in"
fi

for template_path in "${template_paths[@]}"; do
  unit_name="${template_path##*/}"
  unit_name="${unit_name%.in}"
  template_units["$unit_name"]="$template_path"
  installed_path="$installed_dir/$unit_name"

  report INFO template_found "$unit_name"

  if [[ ! -e "$installed_path" ]]; then
    report FAIL missing_installed "$unit_name template has no installed unit"
    continue
  fi

  if render_template "$template_path" | cmp -s - "$installed_path"; then
    report INFO template_matches_installed "$unit_name"
  elif [[ "$unit_name" == "hermes-gateway.service" ]]; then
    report WARN known_mismatch "$unit_name installed unit differs from rendered template"
  else
    report FAIL unexpected_mismatch "$unit_name installed unit differs from rendered template"
  fi
done

for installed_path in "$installed_dir"/*; do
  [[ -f "$installed_path" || -L "$installed_path" ]] || continue
  unit_name="${installed_path##*/}"

  is_openclaw_unit "$unit_name" || continue

  if [[ -n "${template_units[$unit_name]+present}" ]]; then
    continue
  fi

  if is_known_installed_only "$unit_name"; then
    report WARN installed_only "$unit_name has installed unit but no repo template"
  else
    report FAIL installed_without_template "$unit_name has installed unit but no repo template"
  fi
done

check_wants_dir() {
  local rel_dir="$1"
  local wants_dir="$installed_dir/$rel_dir"
  local entry
  local unit_name

  if [[ ! -d "$wants_dir" ]]; then
    report WARN missing_wants_dir "$rel_dir is absent"
    return 0
  fi

  for entry in "$wants_dir"/*; do
    [[ -e "$entry" || -L "$entry" ]] || continue
    unit_name="${entry##*/}"
    [[ "$unit_name" == *.bak ]] && continue

    report INFO wants_entry "$rel_dir/$unit_name"

    if [[ ! -e "$installed_dir/$unit_name" ]]; then
      report FAIL broken_wants "$rel_dir/$unit_name points to missing installed unit"
    fi
  done
}

check_wants_dir "openclaw-stack.target.wants"
check_wants_dir "default.target.wants"
check_wants_dir "timers.target.wants"

for frozen_path in \
  "scripts/start_all.sh" \
  "start_chief.sh" \
  "start_openclaw_brains.sh" \
  "scripts/install_openclaw_stack.sh"; do
  if [[ -e "$repo_root/$frozen_path" ]]; then
    report WARN frozen_control "$frozen_path is present and frozen until cleanup"
  fi
done

cron_jobs="$repo_root/.openclaw/cron/jobs.json"
has_drift_cron=false
if [[ -f "$cron_jobs" ]]; then
  if grep -Eq 'drift-control-scan|drift_control_scanner\.py' "$cron_jobs"; then
    has_drift_cron=true
    report WARN drift_cron_registry ".openclaw/cron/jobs.json contains drift-control scheduling"
  else
    report INFO drift_cron_registry ".openclaw/cron/jobs.json has no drift-control scheduling"
  fi
else
  report INFO drift_cron_registry ".openclaw/cron/jobs.json is absent"
fi

timer_wants="$installed_dir/timers.target.wants/openclaw-drift-control-scan.timer"
if [[ "$has_drift_cron" == true && ( -e "$timer_wants" || -L "$timer_wants" ) ]]; then
  report WARN dual_scheduler_risk "drift-control cron entry and systemd timer want are both present"
fi

if command -v systemctl >/dev/null 2>&1; then
  if systemctl --user list-unit-files 'openclaw*' 'chief*' 'cassandra*' 'hermes*' --no-pager 2>/dev/null; then
    report INFO systemctl_unit_files "listed read-only user unit-file statuses"
  else
    report WARN systemctl_unavailable "systemctl user unit-file status query failed"
  fi
else
  report WARN systemctl_unavailable "systemctl is not available"
fi

report INFO summary "warnings=$warn_count failures=$fail_count"

if (( fail_count > 0 )); then
  exit 1
fi

exit 0