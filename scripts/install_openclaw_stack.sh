#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: scripts/install_openclaw_stack.sh [--dry-run] [--apply] [--enable] [--start] [--request-response-only] [--ancillary-repair-only] [--gpu-health-only] [--keepwarm-only] [--codex-note-watch-only]

Modes:
  no args     Report what would happen. No files are written and no services are changed.
  --dry-run   Report what would happen. Cannot be combined with mutation flags.
  --apply     Render/install repo-owned units and run systemctl --user daemon-reload only.
  --enable    Enable only repo-owned OpenClaw units rendered by this script. Requires --apply.
  --start     Enable/start openclaw-stack.target, or only openclaw-request-response.service with --request-response-only. Requires --apply and --enable.
  --request-response-only
              Limit render/enable/start to the Mission Control request-response bridge.
  --ancillary-repair-only
              Render only the three known ancillary units with Python placeholders.
              This repair slice refuses --enable and --start.
  --gpu-health-only
              Render only the passive GPU health service and timer. With --enable,
              enable and start exactly that timer. This slice refuses --start.
  --keepwarm-only
              Render only the governed interactive 8B keep-warm service and timer.
              With --enable, enable and start exactly that timer. This slice refuses --start.
  --codex-note-watch-only
              Render only the event-driven Codex note wake service and path unit.
              With --enable, prime history and start exactly that path. This slice refuses --start.

Unknown or ambiguous flag combinations fail closed.
USAGE
}

apply_changes=0
enable_units=0
start_target=0
dry_run=0
request_response_only=0
ancillary_repair_only=0
gpu_health_only=0
keepwarm_only=0
codex_note_watch_only=0

if (($# == 0)); then
    dry_run=1
fi

while (($#)); do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        --apply)
            apply_changes=1
            ;;
        --enable)
            enable_units=1
            ;;
        --start)
            start_target=1
            ;;
        --request-response-only)
            request_response_only=1
            ;;
        --ancillary-repair-only)
            ancillary_repair_only=1
            ;;
        --gpu-health-only)
            gpu_health_only=1
            ;;
        --keepwarm-only)
            keepwarm_only=1
            ;;
        --codex-note-watch-only)
            codex_note_watch_only=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'ERROR: unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

if (( dry_run && (apply_changes || enable_units || start_target) )); then
    printf 'ERROR: --dry-run cannot be combined with --apply, --enable, or --start.\n' >&2
    usage >&2
    exit 2
fi

if (( gpu_health_only && (request_response_only || ancillary_repair_only) )); then
    printf 'ERROR: --gpu-health-only cannot be combined with another scoped mode.\n' >&2
    usage >&2
    exit 2
fi

if (( keepwarm_only && (request_response_only || ancillary_repair_only || gpu_health_only) )); then
    printf 'ERROR: --keepwarm-only cannot be combined with another scoped mode.\n' >&2
    usage >&2
    exit 2
fi

if (( codex_note_watch_only && (request_response_only || ancillary_repair_only || gpu_health_only || keepwarm_only) )); then
    printf 'ERROR: --codex-note-watch-only cannot be combined with another scoped mode.\n' >&2
    usage >&2
    exit 2
fi

if (( gpu_health_only && start_target )); then
    printf 'ERROR: --gpu-health-only cannot be combined with --start; --enable starts only its timer.\n' >&2
    usage >&2
    exit 2
fi

if (( keepwarm_only && start_target )); then
    printf 'ERROR: --keepwarm-only cannot be combined with --start; --enable starts only its timer.\n' >&2
    usage >&2
    exit 2
fi

if (( codex_note_watch_only && start_target )); then
    printf 'ERROR: --codex-note-watch-only cannot be combined with --start; --enable starts only its path unit.\n' >&2
    usage >&2
    exit 2
fi

if (( ancillary_repair_only && request_response_only )); then
    printf 'ERROR: --ancillary-repair-only cannot be combined with --request-response-only.\n' >&2
    usage >&2
    exit 2
fi

if (( ancillary_repair_only && (enable_units || start_target) )); then
    printf 'ERROR: --ancillary-repair-only cannot be combined with --enable or --start.\n' >&2
    usage >&2
    exit 2
fi

if (( enable_units && ! apply_changes )); then
    printf 'ERROR: --enable requires --apply.\n' >&2
    usage >&2
    exit 2
fi

if (( start_target && (! apply_changes || ! enable_units) )); then
    printf 'ERROR: --start requires --apply and --enable.\n' >&2
    usage >&2
    exit 2
fi

if (( ! dry_run && ! apply_changes )); then
    printf 'ERROR: mutation requires --apply; use --dry-run to inspect a scoped mode.\n' >&2
    usage >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_DIR="${REPO_ROOT}/systemd/user"
USER_UNIT_DIR="${HOME}/.config/systemd/user"
TARGET_NAME="openclaw-stack.target"
REQUEST_RESPONSE_SERVICE_NAME="openclaw-request-response.service"
PYTHON_BIN="${REPO_ROOT}/chief_env/bin/python"
GPU_MODEL_HEALTH_SERVICE_NAME="openclaw-gpu-model-health.service"
GPU_MODEL_HEALTH_TIMER_NAME="openclaw-gpu-model-health.timer"
GPU_HEALTH_UNIT_NAMES=(
    "${GPU_MODEL_HEALTH_SERVICE_NAME}"
    "${GPU_MODEL_HEALTH_TIMER_NAME}"
)
KEEPWARM_SERVICE_NAME="openclaw-8b-keepwarm.service"
KEEPWARM_TIMER_NAME="openclaw-8b-keepwarm.timer"
KEEPWARM_UNIT_NAMES=(
    "${KEEPWARM_SERVICE_NAME}"
    "${KEEPWARM_TIMER_NAME}"
)
CODEX_NOTE_WATCH_SERVICE_NAME="openclaw-codex-note-wake.service"
CODEX_NOTE_WATCH_PATH_NAME="openclaw-codex-note-wake.path"
CODEX_NOTE_WATCH_UNIT_NAMES=(
    "${CODEX_NOTE_WATCH_SERVICE_NAME}"
    "${CODEX_NOTE_WATCH_PATH_NAME}"
)
ANCILLARY_REPAIR_UNIT_NAMES=(
    "guardian-approval-notifier.service"
    "self-knowledge-crawl.service"
    "openclaw-read-model-auto-refresh.service"
)

repo_owned_unit_names=()
repo_owned_service_names=()
repo_owned_timer_names=()
repo_owned_path_names=()

collect_template() {
    local template="$1"
    local unit_name
    if [[ ! -e "${template}" ]]; then
        return
    fi
    unit_name="$(basename "${template}" .in)"
    if skip_keepwarm_in_broad_mode "${unit_name}"; then
        return
    fi
    if skip_codex_note_watch_in_broad_mode "${unit_name}"; then
        return
    fi
    repo_owned_unit_names+=("${unit_name}")
    if [[ "${unit_name}" == *.service \
        && "${unit_name}" != "hermes-gateway.service" \
        && "${unit_name}" != "${GPU_MODEL_HEALTH_SERVICE_NAME}" \
        && "${unit_name}" != "${KEEPWARM_SERVICE_NAME}" \
        && "${unit_name}" != "${CODEX_NOTE_WATCH_SERVICE_NAME}" ]]; then
        repo_owned_service_names+=("${unit_name}")
    elif [[ "${unit_name}" == "${GPU_MODEL_HEALTH_TIMER_NAME}" \
        || "${unit_name}" == "${KEEPWARM_TIMER_NAME}" ]]; then
        repo_owned_timer_names+=("${unit_name}")
    elif [[ "${unit_name}" == "${CODEX_NOTE_WATCH_PATH_NAME}" ]]; then
        repo_owned_path_names+=("${unit_name}")
    fi
}

skip_keepwarm_in_broad_mode() {
    local unit_name="$1"
    (( keepwarm_only )) && return 1
    [[ "${unit_name}" == "${KEEPWARM_SERVICE_NAME}" \
        || "${unit_name}" == "${KEEPWARM_TIMER_NAME}" ]]
}

skip_codex_note_watch_in_broad_mode() {
    local unit_name="$1"
    (( codex_note_watch_only )) && return 1
    [[ "${unit_name}" == "${CODEX_NOTE_WATCH_SERVICE_NAME}" \
        || "${unit_name}" == "${CODEX_NOTE_WATCH_PATH_NAME}" ]]
}

if (( request_response_only )); then
    collect_template "${TEMPLATE_DIR}/${REQUEST_RESPONSE_SERVICE_NAME}.in"
elif (( ancillary_repair_only )); then
    for unit_name in "${ANCILLARY_REPAIR_UNIT_NAMES[@]}"; do
        collect_template "${TEMPLATE_DIR}/${unit_name}.in"
    done
elif (( gpu_health_only )); then
    for unit_name in "${GPU_HEALTH_UNIT_NAMES[@]}"; do
        collect_template "${TEMPLATE_DIR}/${unit_name}.in"
    done
elif (( keepwarm_only )); then
    for unit_name in "${KEEPWARM_UNIT_NAMES[@]}"; do
        collect_template "${TEMPLATE_DIR}/${unit_name}.in"
    done
elif (( codex_note_watch_only )); then
    for unit_name in "${CODEX_NOTE_WATCH_UNIT_NAMES[@]}"; do
        collect_template "${TEMPLATE_DIR}/${unit_name}.in"
    done
else
    for template in "${TEMPLATE_DIR}"/*.in; do
        collect_template "${template}"
    done
fi

print_units() {
    local heading="$1"
    shift
    local unit

    printf '%s\n' "${heading}"
    if (($# == 0)); then
        printf '  none\n'
        return
    fi
    for unit in "$@"; do
        printf '  %s\n' "${unit}"
    done
}

report_plan() {
    printf 'OpenClaw stack installer dry run from %s\n' "${REPO_ROOT}"
    printf 'No files will be written and no service commands will be run.\n'
    print_units 'Repo-owned units that --apply would render/install:' "${repo_owned_unit_names[@]}"
    printf 'With --apply: would render/install those units into %s and run systemctl --user daemon-reload.\n' "${USER_UNIT_DIR}"
    if (( ancillary_repair_only )); then
        printf 'With --apply --ancillary-repair-only: would render only the named ancillary units; enable/start are refused.\n'
    elif (( gpu_health_only )); then
        print_units 'Repo-owned timers that --apply --enable would enable and start:' "${repo_owned_timer_names[@]}"
        printf 'With --apply --enable --gpu-health-only: would start only the passive GPU health timer.\n'
    elif (( keepwarm_only )); then
        print_units 'Repo-owned timers that --apply --enable would enable and start:' "${repo_owned_timer_names[@]}"
        printf 'With --apply --enable --keepwarm-only: would start only the governed interactive 8B keep-warm timer.\n'
    elif (( codex_note_watch_only )); then
        print_units 'Repo-owned paths that --apply --enable would enable and start:' "${repo_owned_path_names[@]}"
        printf 'With --apply --enable --codex-note-watch-only: would prime history and start only the event-driven Codex note path.\n'
    else
        print_units 'Repo-owned non-Hermes services that --apply --enable would enable:' "${repo_owned_service_names[@]}"
        print_units 'Repo-owned timers that --apply --enable would enable and start:' "${repo_owned_timer_names[@]}"
        if (( request_response_only )); then
            printf 'With --apply --enable --start --request-response-only: would enable/start only %s.\n' "${REQUEST_RESPONSE_SERVICE_NAME}"
        else
            printf 'With --apply --enable --start: would enable/start only %s.\n' "${TARGET_NAME}"
        fi
    fi
    printf 'Hermes gateway remains managed by scripts/install_hermes_gateway_service.sh and is not enabled here.\n'
}

if (( dry_run )); then
    report_plan
    exit 0
fi

if ((${#repo_owned_unit_names[@]} == 0)); then
    printf 'ERROR: no repo-owned unit templates found in %s\n' "${TEMPLATE_DIR}" >&2
    exit 1
fi

render_unit() {
    local template_path="$1"
    local unit_name
    local rendered_path
    unit_name="$(basename "${template_path}" .in)"
    rendered_path="$(mktemp "${USER_UNIT_DIR}/.${unit_name}.XXXXXX")"
    sed \
        -e "s|@REPO_ROOT@|${REPO_ROOT}|g" \
        -e "s|@PYTHON@|${PYTHON_BIN}|g" \
        "${template_path}" > "${rendered_path}"
    if grep -Eq '@[A-Z][A-Z0-9_]*@' "${rendered_path}"; then
        printf 'ERROR: unresolved template placeholder in %s\n' "${template_path}" >&2
        rm -f "${rendered_path}"
        return 1
    fi
    chmod 0644 "${rendered_path}"
    mv -f "${rendered_path}" "${USER_UNIT_DIR}/${unit_name}"
    printf 'Installed repo-owned unit: %s\n' "${unit_name}"
}

printf 'Applying OpenClaw stack installer from %s\n' "${REPO_ROOT}"
mkdir -p "${USER_UNIT_DIR}"

if (( request_response_only )); then
    render_unit "${TEMPLATE_DIR}/${REQUEST_RESPONSE_SERVICE_NAME}.in"
elif (( ancillary_repair_only )); then
    for unit_name in "${ANCILLARY_REPAIR_UNIT_NAMES[@]}"; do
        render_unit "${TEMPLATE_DIR}/${unit_name}.in"
    done
elif (( gpu_health_only )); then
    for unit_name in "${GPU_HEALTH_UNIT_NAMES[@]}"; do
        render_unit "${TEMPLATE_DIR}/${unit_name}.in"
    done
elif (( keepwarm_only )); then
    for unit_name in "${KEEPWARM_UNIT_NAMES[@]}"; do
        render_unit "${TEMPLATE_DIR}/${unit_name}.in"
    done
elif (( codex_note_watch_only )); then
    for unit_name in "${CODEX_NOTE_WATCH_UNIT_NAMES[@]}"; do
        render_unit "${TEMPLATE_DIR}/${unit_name}.in"
    done
else
    for template in "${TEMPLATE_DIR}"/*.in; do
        if [[ ! -e "${template}" ]]; then
            continue
        fi
        render_unit "${template}"
    done
fi

systemctl --user daemon-reload
printf 'Ran systemctl --user daemon-reload after rendering repo-owned units.\n'

if (( codex_note_watch_only )); then
    PYTHONDONTWRITEBYTECODE=1 "${PYTHON_BIN}" "${REPO_ROOT}/codex_note_event_wake.py" --prime
    printf 'Primed existing Codex coordination notes as historical before path activation.\n'
fi

if (( enable_units )); then
    print_units 'Enabling repo-owned non-Hermes OpenClaw services:' "${repo_owned_service_names[@]}"
    for service_name in "${repo_owned_service_names[@]}"; do
        systemctl --user enable "${service_name}"
        printf 'Enabled repo-owned service: %s\n' "${service_name}"
    done
    print_units 'Enabling and starting repo-owned OpenClaw timers:' "${repo_owned_timer_names[@]}"
    for timer_name in "${repo_owned_timer_names[@]}"; do
        systemctl --user enable --now "${timer_name}"
        printf 'Enabled and started repo-owned timer: %s\n' "${timer_name}"
    done
    print_units 'Enabling and starting repo-owned OpenClaw paths:' "${repo_owned_path_names[@]}"
    for path_name in "${repo_owned_path_names[@]}"; do
        systemctl --user enable --now "${path_name}"
        printf 'Enabled and started repo-owned path: %s\n' "${path_name}"
    done
else
    printf 'Did not enable units; pass --enable with --apply to enable repo-owned non-Hermes services and tracked timers.\n'
fi

if (( start_target )); then
    if (( request_response_only )); then
        systemctl --user enable --now "${REQUEST_RESPONSE_SERVICE_NAME}"
        printf 'Enabled and started only %s.\n' "${REQUEST_RESPONSE_SERVICE_NAME}"
    else
        systemctl --user enable --now "${TARGET_NAME}"
        printf 'Enabled and started only %s.\n' "${TARGET_NAME}"
    fi
else
    if (( request_response_only )); then
        printf 'Did not start %s; pass --start with --apply --enable --request-response-only to start the bridge.\n' "${REQUEST_RESPONSE_SERVICE_NAME}"
    else
        printf 'Did not start %s; pass --start with --apply --enable to start the target.\n' "${TARGET_NAME}"
    fi
fi

printf 'OpenClaw stack installer finished with explicit apply=%s enable=%s start=%s request_response_only=%s ancillary_repair_only=%s gpu_health_only=%s keepwarm_only=%s codex_note_watch_only=%s.\n' "${apply_changes}" "${enable_units}" "${start_target}" "${request_response_only}" "${ancillary_repair_only}" "${gpu_health_only}" "${keepwarm_only}" "${codex_note_watch_only}"
